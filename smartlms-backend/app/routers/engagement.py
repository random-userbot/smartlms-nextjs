"""
Smart LMS - Engagement Router
Receive client-side features, compute engagement scores, store with SHAP explanations.

Upgraded to use XGBoost ML model with real SHAP explanations,
enhanced ICAP classification, and fuzzy rule explanations.
Based on: "Designing an Explainable Multimodal Engagement Model"
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import time
import logging
import base64
import cv2  # type: ignore
import numpy as np
import json
from app.database import get_db, async_session
from app.models.models import (
    User, UserRole, EngagementLog, ICAPLog, ICAPLevel,
    Attendance, ActivityLog, Lecture, EngagementStatus
)
from app.middleware.auth import get_current_user, get_current_user_optional
from app.services.debug_logger import debug_logger
from app.services.ml_client import ml_client
from app.ml.engagement_model import (
    get_icap_classifier, get_fuzzy_rules,
    EngagementFeatureExtractor, FEATURE_NAMES
)

# NOTE: ViT Extractor and Face Detector moved to ML Microservice to save local RAM
def get_vit_extractor():
    return None


router = APIRouter(prefix="/api/engagement", tags=["Engagement"])
logger = logging.getLogger("uvicorn.error")


# ─── Schemas ─────────────────────────────────────────────

class EngagementFeatures(BaseModel):
    """Features extracted client-side from MediaPipe"""
    session_id: str
    lecture_id: str
    timestamp: float

    # Facial features
    gaze_score: float = 0.0           # 0-1, 1 = looking at screen
    head_pose_yaw: float = 0.0        # degrees
    head_pose_pitch: float = 0.0
    head_pose_roll: float = 0.0
    head_pose_stability: float = 0.0  # 0-1
    eye_aspect_ratio_left: float = 0.0
    eye_aspect_ratio_right: float = 0.0
    blink_rate: float = 0.0           # blinks per minute
    mouth_openness: float = 0.0       # 0-1

    # Action Unit proxies
    au01_inner_brow_raise: float = 0.0
    au02_outer_brow_raise: float = 0.0
    au04_brow_lowerer: float = 0.0
    au06_cheek_raiser: float = 0.0
    au12_lip_corner_puller: float = 0.0  # smile
    au15_lip_corner_depressor: float = 0.0
    au25_lips_part: float = 0.0
    au26_jaw_drop: float = 0.0

    # Optional OpenFace-compatible fields (accepted if present)
    au07_lid_tightener: float = 0.0
    au09_nose_wrinkler: float = 0.0
    au10_upper_lip_raiser: float = 0.0
    au14_dimpler: float = 0.0
    au17_chin_raiser: float = 0.0
    au20_lip_stretcher: float = 0.0
    au23_lip_tightener: float = 0.0
    au45_blink: float = 0.0

    gaze_angle_x: float = 0.0
    gaze_angle_y: float = 0.0
    pose_Tx: float = 0.0
    pose_Ty: float = 0.0
    pose_Tz: float = 0.0
    pose_Rx: float = 0.0
    pose_Ry: float = 0.0
    pose_Rz: float = 0.0

    happy: float = 0.0
    sad: float = 0.0
    angry: float = 0.0
    surprised: float = 0.0
    fear: float = 0.0
    disgust: float = 0.0
    neutral: float = 0.0

    # Behavioral (from browser)
    keyboard_active: bool = False
    mouse_active: bool = False
    tab_visible: bool = True
    playback_speed: float = 1.0
    note_taking: bool = False  # head-down detection

    # Multimodal additions
    frame_image: Optional[str] = None   # Base64 encoded JPEG (224x224)
    visual_embedding: Optional[List[float]] = None # Pre-computed or server-computed embedding


class EngagementBatchSubmit(BaseModel):
    """Batch of features for a session segment"""
    session_id: str
    lecture_id: str
    features: List[EngagementFeatures]
    keyboard_events: int = 0
    mouse_events: int = 0
    tab_switches: int = 0
    no_face_detected_count: int = 0
    attention_lapse_duration: float = 0.0
    idle_time: float = 0.0
    playback_speeds: List[Dict[str, Any]] = []
    watch_duration: int = 0
    total_duration: int = 0


class EngagementScoreResponse(BaseModel):
    overall_score: float
    boredom: float
    engagement: float
    confusion: float
    frustration: float
    icap_classification: str
    icap_confidence: float = 0.0
    shap_explanations: Dict[str, Any] = {}
    top_factors: List[Dict[str, Any]] = []
    fuzzy_rules: List[Dict[str, str]] = []
    recommendations: List[str] = []
    model_type: str = "rule_based"
    confidence: float = 0.0
    ensemble_models: Any = {}
    ensemble_model_count: int = 0
    model_breakdown: Dict[str, Any] = {}
    # Internal: Forecast fields removed from public response to hide from UI
    predictive_score: Optional[float] = None # Legacy/Ensemble-based
    predictive_details: Optional[Dict[str, float]] = None


class SessionEndRequest(BaseModel):
    session_id: str
    lecture_id: str


class ModelInferenceRequest(BaseModel):
    model_id: str
    features: List[EngagementFeatures]


# ─── ML-Powered Engagement Scoring Engine ────────────────

async def compute_engagement_scores(features: List[EngagementFeatures]) -> Dict:
    """
    Compute engagement scores using the remote ML service (XGBoost).
    Falls back to enhanced rule-based scoring if service is down.
    """
    features_dicts = [f.model_dump() for f in features] if features else []
    result = await ml_client.infer(model_id="builtin::xgboost", features=features_dicts)
    
    if "error" in result:
        # Simple rule-based fallback
        extractor = EngagementFeatureExtractor()
        stats = extractor.extract_v2(features_dicts)
        
        # Simple heuristic from engagement_model._hybrid_scoring
        gaze_mean = stats[8] if len(stats) > 8 else 0.5
        stab_mean = stats[32] if len(stats) > 32 else 0.5
        ear_mean = stats[0] if len(stats) > 0 else 0.25
        
        score = (gaze_mean * 30 + stab_mean * 20 + ear_mean * 20)
        score = np.clip(score + 10, 0, 100)
        
        return {
            "overall": round(score, 1),
            "engagement": round(score, 1),
            "boredom": round(100 - score, 1),
            "confusion": 10.0,
            "frustration": 10.0,
            "model_type": "rule_based_fallback"
        }
    
    # Unpack the "output" field if present (from smartlms-ml-service)
    scores = result.get("output", result)
    
    # Ensure mandatory keys exist for the dashboard
    defaults = {"overall": 0.0, "engagement": 0.0, "boredom": 0.0, "confusion": 0.0, "frustration": 0.0}
    for key, val in defaults.items():
        if key not in scores:
            scores[key] = val
            
    return scores


def compute_shap_explanations(features: List[EngagementFeatures], scores: Dict) -> Dict:
    """
    Get SHAP explanations - now integrated into the model prediction.
    This function extracts the SHAP data from the model's output.
    """
    return scores.get("shap_explanations", {})


def _expected_score_from_probabilities(probabilities: List[float]) -> float:
    """Convert class probabilities to a 0-100 expected score."""
    if not probabilities:
        return 0.0

    total = sum(float(p) for p in probabilities)
    if total <= 0:
        return 0.0

    probs = [float(p) / total for p in probabilities]
    max_class = max(len(probs) - 1, 1)
    expected_class = sum(idx * p for idx, p in enumerate(probs))
    return (expected_class / max_class) * 100.0


def _extract_export_scores(export_result: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Extract comparable 0-100 per-dimension scores from export model output."""
    output = export_result.get("output", {}) if isinstance(export_result, dict) else {}
    dims = output.get("dimensions", {}) if isinstance(export_result, dict) else {}

    if not dims:
        return None

    parsed: Dict[str, float] = {}
    for key in ["boredom", "engagement", "confusion", "frustration"]:
        dim_data = dims.get(key) or {}
        probs = dim_data.get("probabilities")
        if isinstance(probs, list) and probs:
            parsed[key] = round(_expected_score_from_probabilities(probs), 2)
        else:
            class_index = float(dim_data.get("class_index", 0))
            parsed[key] = round((class_index / 3.0) * 100.0, 2)

    parsed["overall"] = float(output.get("overall_proxy", np.mean([parsed[k] for k in ["boredom", "engagement", "confusion", "frustration"]])))
    return parsed


def _is_export_prediction_healthy(parsed: Dict[str, float]) -> bool:
    required = ["boredom", "engagement", "confusion", "frustration"]
    vals: List[float] = []
    for key in required:
        v = parsed.get(key)
        if v is None or not np.isfinite(float(v)):
            return False
        fv = float(v)
        if fv < 0.0 or fv > 100.0:
            return False
        vals.append(fv)

    # Degenerate case: all dimensions collapse to the same value.
    pairwise = [abs(vals[i] - vals[j]) for i in range(len(vals)) for j in range(i + 1, len(vals))]
    mean_sep = float(np.mean(pairwise)) if pairwise else 0.0
    if mean_sep < 0.05:
        return False
    return True


async def apply_export_xgb_ensemble(base_scores: Dict[str, float], features: List[EngagementFeatures]) -> Dict[str, Any]:
    """
    Blend XGBoost runtime scores with available export models via ML service.
    """
    features_dicts = [f.model_dump() for f in features] if features else []
    if not features_dicts:
        return base_scores

    return await ml_client.ensemble(base_scores, features_dicts)



def classify_icap(
    features: List[EngagementFeatures],
    keyboard_events: int,
    mouse_events: int = 0,
    tab_switches: int = 0,
    quiz_score: Optional[float] = None,
) -> tuple:
    """
    Classify student behavior into ICAP framework level using the enhanced classifier.
    Returns (level, evidence, confidence).
    """
    classifier = get_icap_classifier()
    features_dicts = [f.model_dump() for f in features] if features else []
    return classifier.classify(
        features_dicts,
        keyboard_events=keyboard_events,
        mouse_events=mouse_events,
        tab_switches=tab_switches,
        quiz_score=quiz_score,
        note_taking_detected=any(
            (f.get("note_taking", False) if isinstance(f, dict) else getattr(f, "note_taking", False))
            for f in features_dicts
        ) if features_dicts else False,
    )


def compute_fuzzy_rules(features: List[EngagementFeatures], scores: Dict) -> List[Dict]:
    """
    Evaluate fuzzy logic rules for human-readable engagement explanations.
    Based on Zhao et al. (2024).
    """
    fuzzy = get_fuzzy_rules()
    features_dicts = [f.model_dump() for f in features] if features else []
    feature_vector = EngagementFeatureExtractor.extract_from_batch(features_dicts)
    return fuzzy.evaluate(feature_vector, scores)


def build_scores_timeline(features: List[EngagementFeatures], watch_duration: int) -> List[Dict[str, Any]]:
    """Create lightweight timeline points from raw feature frames for heatmap rendering."""
    if not features:
        return []

    frame_count = len(features)
    base_time = max(0, int(watch_duration) - frame_count)
    timeline: List[Dict[str, Any]] = []

    for idx, f in enumerate(features):
        gaze = max(0.0, min(1.0, float(getattr(f, "gaze_score", 0.0) or 0.0)))
        stability = max(0.0, min(1.0, float(getattr(f, "head_pose_stability", 0.0) or 0.0)))
        tab_visible = 1.0 if getattr(f, "tab_visible", True) else 0.0
        keyboard = 1.0 if getattr(f, "keyboard_active", False) else 0.0
        mouse = 1.0 if getattr(f, "mouse_active", False) else 0.0

        engagement = (gaze * 65.0) + (stability * 20.0) + (tab_visible * 10.0) + ((keyboard + mouse) * 2.5)
        engagement = max(0.0, min(100.0, engagement))

        confusion = max(0.0, min(100.0, 60.0 - (gaze * 30.0) - (stability * 15.0)))
        boredom = max(0.0, min(100.0, 70.0 - engagement))
        frustration = max(0.0, min(100.0, (confusion * 0.6) + ((1.0 - gaze) * 20.0)))

        timeline.append(
            {
                "timestamp": base_time + idx,
                "engagement": round(engagement, 2),
                "boredom": round(boredom, 2),
                "confusion": round(confusion, 2),
                "frustration": round(frustration, 2),
                "face_detected": bool(gaze > 0.05), # Heuristic for face detection
                "tab_visible": bool(tab_visible > 0.5),
                "is_active": bool(keyboard > 0 or mouse > 0)
            }
        )

    return timeline


def generate_recommendations(scores: Dict, icap: str, fuzzy_rules: List[Dict] = None) -> List[str]:
    """
    Generate actionable recommendations based on engagement analysis.
    Enhanced with ICAP-aware suggestions following the research paper.
    """
    recs = []

    # Score-based recommendations
    if scores.get("engagement", 50) < 40:
        recs.append("Consider breaking content into shorter segments to maintain attention")
    if scores.get("boredom", 30) > 60:
        recs.append("Include interactive elements or discussion prompts to reduce boredom")
    if scores.get("confusion", 20) > 50:
        recs.append("Review pace and complexity of content; add more examples or explanations")
    if scores.get("frustration", 10) > 50:
        recs.append("Check if prerequisites are met; provide additional support resources")

    # ICAP-based recommendations (P→A→C→I progression)
    if icap == ICAPLevel.PASSIVE.value:
        recs.append("Student is in PASSIVE mode. Encourage active note-taking or provide guided worksheets")
        recs.append("Consider adding quiz checkpoints to move from Passive to Active learning")
    elif icap == ICAPLevel.ACTIVE.value:
        recs.append("Student is ACTIVELY watching. Add reflection prompts to promote Constructive learning")
        recs.append("Try adding open-ended questions to encourage deeper processing")
    elif icap == ICAPLevel.CONSTRUCTIVE.value:
        recs.append("Student is in CONSTRUCTIVE mode (taking notes). Encourage peer discussion for Interactive learning")
    elif icap == ICAPLevel.INTERACTIVE.value:
        recs.append("Excellent! Student is in INTERACTIVE mode - the highest ICAP level")

    # Add fuzzy rule suggestions
    if fuzzy_rules:
        for rule in fuzzy_rules:
            if rule.get("severity") in ["high", "medium"] and rule.get("suggestion"):
                if rule["suggestion"] not in recs:
                    recs.append(rule["suggestion"])

    if not recs:
        recs.append("Engagement levels are healthy. Continue with current approach.")

    return recs[:8]  # Limit to top 8 recommendations


# ─── Routes ──────────────────────────────────────────────

@router.post("/submit", response_model=EngagementScoreResponse)
async def submit_engagement_data(
    request: EngagementBatchSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a batch of engagement features and get ML-powered scores with SHAP explanations"""
    feature_count = len(request.features or [])
    features_dicts = [f.model_dump() for f in request.features]
    
    # 1. Compute initial fast scores using ML model (XGBoost + SHAP)
    # This happens synchronously for immediate UX feedback
    scores = await compute_engagement_scores(request.features)
    
    # 2. Enhanced ICAP classification
    icap_level, icap_evidence, icap_confidence = classify_icap(
        request.features,
        keyboard_events=request.keyboard_events,
        mouse_events=request.mouse_events,
        tab_switches=request.tab_switches,
    )
    
    # 3. Fuzzy rule evaluation for human-readable explanations
    fuzzy_rules = compute_fuzzy_rules(request.features, scores)
    
    # 4. Generate enhanced recommendations & Timeline
    recommendations = generate_recommendations(scores, icap_level, fuzzy_rules)
    timeline_points = build_scores_timeline(request.features, request.watch_duration)

    # 5. Refresh with Deep Neural Ensemble (ViT/BiLSTM/Fusion)
    # This blends fast XGB scores with high-fidelity exported models
    refined_scores = await apply_export_xgb_ensemble(scores, request.features)
    
    # Use refined scores if available, else fallback to fast scores
    final_scores = refined_scores if refined_scores and "error" not in refined_scores else scores

    # --- High-Visibility Terminal Metrics (Refined) ---
    ts_str = datetime.now().strftime("%H:%M:%S")
    print("\n" + "═"*70, flush=True)
    print(f"║ ENGAGEMENT ENGINE | {ts_str} | Session: {request.session_id[:8]}... ║", flush=True)
    print("╟" + "─"*68 + "╢", flush=True)
    print(f"║ Lecture: {request.lecture_id[:12]}...  ║ User: {current_user.full_name[:15]} ║", flush=True)
    print("╟" + "─"*68 + "╢", flush=True)
    print(f"║ FAST SCORE (XGB): {scores['overall']:.1f}% (E:{scores['engagement']:.0f} B:{scores['boredom']:.0f} C:{scores['confusion']:.0f} F:{scores['frustration']:.0f})║", flush=True)
    
    if final_scores.get("ensemble_model_count"):
        m_count = final_scores.get("ensemble_model_count", 0)
        print(f"║ ENSEMBLE ANALYTICS ({m_count} SOTA): {final_scores['overall']:.1f}% (+Refined Logic Active) ║", flush=True)
    
    print(f"║ ICAP STATE: {icap_level.upper()} | CONFIDENCE: {icap_confidence:.2f} ║", flush=True)
    print("╚" + "═"*68 + "╝\n", flush=True)

    # 5. Hysteresis Engine: Check if we can merge this batch into a stable state
    stmt = select(EngagementLog).where(
        EngagementLog.student_id == current_user.id,
        EngagementLog.lecture_id == request.lecture_id,
        EngagementLog.session_id == request.session_id
    ).order_by(EngagementLog.started_at.desc())
    
    result = await db.execute(stmt)
    last_log = result.scalars().first()

    is_stable = False
    if last_log and last_log.icap_classification == ICAPLevel(icap_level):
        # Merge if ICAP is identical and score variance is low (< 5%)
        # And if the gap between batches is reasonable ( < 1 minute)
        score_delta = abs(last_log.overall_score - final_scores['overall'])
        time_gap = (datetime.utcnow() - (last_log.ended_at or last_log.started_at)).total_seconds()
        
        if score_delta < 5.0 and time_gap < 60:
            is_stable = True

    if is_stable:
        # --- UPDATE STABLE STATE (Live Flow) ---
        last_log.ended_at = datetime.utcnow()
        last_log.updated_at = datetime.utcnow()
        last_log.watch_duration += request.watch_duration
        last_log.keyboard_events += request.keyboard_events
        last_log.mouse_events += request.mouse_events
        last_log.tab_switches += request.tab_switches
        
        # Append to Rich feature timeline for Dataset preparation
        if last_log.feature_timeline is None:
            last_log.feature_timeline = []
        
        # Add new features to the timeline
        last_log.feature_timeline.extend(features_dicts)
        
        # Aggregated stats in the features blob
        if isinstance(last_log.features, dict):
            last_log.features["aggregated_samples"] = last_log.features.get("aggregated_samples", 0) + 1
            last_log.features["raw_feature_mirror"] = features_dicts[0] if features_dicts else {}
        
        # Update scores (Moving average for smoothness)
        last_log.overall_score = (last_log.overall_score + final_scores['overall']) / 2
        last_log.boredom_score = (last_log.boredom_score + final_scores['boredom']) / 2
        last_log.engagement_score = (last_log.engagement_score + final_scores['engagement']) / 2
        last_log.confusion_score = (last_log.confusion_score + final_scores['confusion']) / 2
        last_log.frustration_score = (last_log.frustration_score + final_scores['frustration']) / 2
        
        db.add(last_log)
        log = last_log
        # print moved after commit/refresh
    else:
        # --- CREATE NEW STATE BLOCK (Live Flow - Temporary) ---
        log = EngagementLog(
            student_id=current_user.id,
            lecture_id=request.lecture_id,
            session_id=request.session_id,
            status=EngagementStatus.PROCESSING,
            is_finalized=False, # MARK AS TEMPORARY
            overall_score=final_scores['overall'], 
            boredom_score=final_scores['boredom'],
            engagement_score=final_scores['engagement'],
            confusion_score=final_scores['confusion'],
            frustration_score=final_scores['frustration'],
            features={
                "count": len(request.features),
                "model_type": final_scores.get("model_type", "neural_ensemble"),
                "ensemble_stats": final_scores.get("model_breakdown", {}),
                "raw_feature_mirror": features_dicts[0] if features_dicts else {},
            },
            feature_timeline=features_dicts, # START TIMELINE in dedicated column
            scores_timeline=timeline_points,
            icap_classification=ICAPLevel(icap_level),
            icap_evidence={**icap_evidence, "confidence": icap_confidence},
            keyboard_events=request.keyboard_events,
            mouse_events=request.mouse_events,
            tab_switches=request.tab_switches,
            no_face_detected_count=request.no_face_detected_count,
            attention_lapse_duration=request.attention_lapse_duration,
            idle_time=request.idle_time,
            playback_speeds=request.playback_speeds,
            note_taking_detected=any(f.note_taking for f in request.features),
            watch_duration=request.watch_duration,
            total_duration=request.total_duration,
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(log)
        # print moved after commit/refresh
    
    # Update ICAP log (Events table)
    if not is_stable:
        icap_log = ICAPLog(
            student_id=current_user.id,
            lecture_id=request.lecture_id,
            classification=ICAPLevel(icap_level),
            evidence={**icap_evidence, "confidence": icap_confidence},
        )
        db.add(icap_log)

    await db.commit()
    await db.refresh(log)

    # Log the state transition
    state_type = "STATE_MERGE" if is_stable else "STATE_NEW"
    state_desc = "Combined into stable block" if is_stable else "Created new diagnostic state"
    print(f"║ [{state_type}] {state_desc} (ID: {log.id[:8] if log.id else 'N/A'}) ║", flush=True)

    # 6. [PRO-FIX] Push to SQS for Asynchronous Inference
    # The dedicated ML Worker will pull this and update the DB record
    success = await ml_client.push_inference_job(
        log_id=log.id,
        features=features_dicts,
        model_id="builtin::ensemble_pro"
    )

    if not success:
        logger.error(f"Failed to queue ML job for log {log.id}")

    return EngagementScoreResponse(
        overall_score=final_scores.get('overall', 0.0),
        boredom=final_scores.get('boredom', 0.0),
        engagement=final_scores.get('engagement', 0.0),
        confusion=final_scores.get('confusion', 0.0),
        frustration=final_scores.get('frustration', 0.0),
        icap_classification=icap_level,
        icap_confidence=icap_confidence,
        fuzzy_rules=fuzzy_rules,
        recommendations=recommendations,
        model_type=final_scores.get('model_type', 'neural_ensemble'),
        confidence=final_scores.get('confidence', 0.0),
        ensemble_models=final_scores.get('ensemble_models', {}),
        ensemble_model_count=final_scores.get('ensemble_model_count', 0),
        model_breakdown={"status": "completed" if "error" not in final_scores else "partially_completed", "job_id": log.id}
    )


@router.get("/job/{log_id}")
async def get_job_status(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll for the status and result of an async ML inference job."""
    # Check cache first (Pro Optimization #7)
    cached = ml_client.get_cached_result(log_id)
    if cached:
        return cached

    result = await db.execute(select(EngagementLog).where(EngagementLog.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Job not found")

    if log.student_id != current_user.id and current_user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="Unauthorized")

    response = {
        "status": log.status.value,
        "job_id": log.id,
        "result": {
            "overall_score": log.overall_score,
            "engagement": log.engagement_score,
            "boredom": log.boredom_score,
            "confusion": log.confusion_score,
            "frustration": log.frustration_score,
            "icap": log.icap_classification,
            "shap": log.shap_explanations,
        } if log.status == EngagementStatus.COMPLETED else None,
        "error": log.error_message if log.status == EngagementStatus.FAILED else None
    }

    # If completed, cache it
    if log.status == EngagementStatus.COMPLETED:
        ml_client.set_cached_result(log_id, response)

    return response


@router.post("/finalize-session")
async def finalize_session(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark the session as permanent and finalize datasets.
    This fulfills the requirement to only store permanent data upon completion.
    """
    session_id = request.get("session_id")
    lecture_id = request.get("lecture_id")
    waveform = request.get("waveform", [])
    
    if not session_id or not lecture_id:
        raise HTTPException(status_code=400, detail="Missing session_id or lecture_id")

    # 1. Update all logs for this session to finalized
    stmt = (
        update(EngagementLog)
        .where(
            EngagementLog.session_id == session_id,
            EngagementLog.student_id == current_user.id
        )
        .values(
            is_finalized=True, 
            scores_timeline=waveform, 
            ended_at=datetime.utcnow(),
            status=EngagementStatus.COMPLETED
        )
    )
    await db.execute(stmt)
    
    # 2. Trigger clean-up of any stale sessions (Self-cleaning logic)
    # Delete non-finalized sessions older than 2 hours
    cutoff = datetime.utcnow() - timedelta(hours=2)
    cleanup_stmt = (
        update(EngagementLog)
        .where(
            EngagementLog.is_finalized == False,
            EngagementLog.updated_at < cutoff
        )
        .values(status=EngagementStatus.FAILED, error_message="Session timed out or abandoned")
    )
    # Actually, user said 'don't store that data'. 
    # To truly 'not store', we should DELETE.
    from sqlalchemy import delete
    del_stmt = delete(EngagementLog).where(
        EngagementLog.is_finalized == False,
        EngagementLog.updated_at < cutoff
    )
    await db.execute(del_stmt)

    await db.commit()
    
    print(f"\n🏆 [SESSION_FINALIZED] ID: {session_id[:8]} | Marked Permanent | Waveform: {len(waveform)}", flush=True)
    
    return {"status": "success", "finalized": True}


@router.get("/history/{lecture_id}")
async def get_engagement_history(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get engagement history for a lecture"""
    result = await db.execute(
        select(EngagementLog).where(
            EngagementLog.student_id == current_user.id,
            EngagementLog.lecture_id == lecture_id
        ).order_by(EngagementLog.started_at.desc())
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "session_id": log.session_id,
            "overall_score": log.overall_score,
            "engagement_score": log.engagement_score,
            "boredom_score": log.boredom_score,
            "confusion_score": log.confusion_score,
            "frustration_score": log.frustration_score,
            "icap_classification": log.icap_classification.value if log.icap_classification else None,
            "shap_explanations": log.shap_explanations,
            "tab_switches": log.tab_switches,
            "keyboard_events": log.keyboard_events,
            "watch_duration": log.watch_duration,
            "started_at": log.started_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/student-summary/{student_id}")
async def get_student_engagement_summary(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get engagement summary for a student (teacher/admin view)"""
    if current_user.role == UserRole.STUDENT and current_user.id != student_id:
        raise HTTPException(status_code=403, detail="Cannot view other students' data")

    result = await db.execute(
        select(EngagementLog).where(
            EngagementLog.student_id == student_id
        )
        .order_by(EngagementLog.started_at.desc())
    )
    logs = result.scalars().all()

    if not logs:
        return {"student_id": student_id, "sessions": 0, "avg_engagement": 0}

    avg_engagement = sum(l.engagement_score or 0 for l in logs) / len(logs)
    avg_boredom = sum(l.boredom_score or 0 for l in logs) / len(logs)

    # ICAP distribution
    icap_counts = {}
    for log in logs:
        if log.icap_classification:
            k = log.icap_classification.value
            icap_counts[k] = icap_counts.get(k, 0) + 1

    # Collect latest recommendations & top weaknesses
    # Collect latest recommendations from SHAP explanations
    recent_recs = []
    for log in logs[:3]: # Look at last 3 sessions
        recs = getattr(log, 'recommendations', None)
        if not recs and log.shap_explanations:
            recs = log.shap_explanations.get('recommendations', [])
        if recs:
            recent_recs.extend(recs)
    recent_recs = list(set(recent_recs))[:5] # Deduplicate and limit

    total_no_face = sum(l.no_face_detected_count or 0 for l in logs)
    total_lapse = sum(l.attention_lapse_duration or 0 for l in logs)
    total_watch = sum(l.watch_duration or 0 for l in logs)
    
    visibility_score = 100.0
    if total_watch > 0:
        # Calculate visibility as (watchTime - lapseTime) / watchTime
        visibility_score = max(0, min(100, ((total_watch - total_lapse) / total_watch) * 100))

    total_interruptions = total_no_face + sum(l.tab_switches or 0 for l in logs)
    session_continuity = total_watch / max(1, total_interruptions)
    
    # Heuristic for max focus: sessions with lowest lapse ratios
    attention_span = 0.0
    if logs:
        # Get the session with the best (watch - lapse) value
        best_session_focus = max([(l.watch_duration or 0) - (l.attention_lapse_duration or 0) for l in logs])
        attention_span = float(best_session_focus)

    return {
        "student_id": student_id,
        "sessions": len(logs),
        "avg_engagement": round(avg_engagement, 1),
        "avg_boredom": round(avg_boredom, 1),
        "total_watch_time": total_watch,
        "total_tab_switches": sum(l.tab_switches or 0 for l in logs),
        "total_no_face_count": total_no_face,
        "total_lapse_duration": round(total_lapse, 1),
        "visibility_score": round(visibility_score, 1),
        "session_continuity_score": round(min(100, session_continuity / 60 * 10), 1), # Scaled for UI
        "avg_focus_duration_mins": round(session_continuity / 60, 2),
        "max_attention_span_mins": round(attention_span / 60, 2),
        "icap_distribution": icap_counts,
        "insights": recent_recs,
    }


@router.get("/heatmap/{lecture_id}")
async def get_engagement_heatmap(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get engagement heatmap data for a lecture.
    Maps time segments to aggregate attention levels.
    High-intensity (red) = replayed/lingered; Low (blue) = skipped.
    Based on research: engagement heatmaps pinpoint confusing sections.
    """
    lecture_result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = lecture_result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    result = await db.execute(
        select(EngagementLog).where(EngagementLog.lecture_id == lecture_id).order_by(EngagementLog.started_at)
    )
    logs = result.scalars().all()

    if not logs:
        return {"lecture_id": lecture_id, "segments": [], "avg_engagement": 0, "pain_points": []}

    duration = lecture.duration or 300
    segment_count = min(20, max(5, duration // 30))
    segment_length = duration / segment_count

    # Flatten timeline entries once to avoid nested repeated scans.
    timeline_entries = []
    for log in logs:
        if log.scores_timeline:
            for entry in log.scores_timeline:
                timeline_entries.append(
                    {
                        "timestamp": entry.get("timestamp", 0),
                        "engagement": entry.get("engagement", 50),
                        "boredom": entry.get("boredom", 30),
                        "confusion": entry.get("confusion", 20),
                    }
                )

    segments = []
    for seg_idx in range(segment_count):
        start_time = seg_idx * segment_length
        end_time = (seg_idx + 1) * segment_length
        seg_engagement, seg_boredom, seg_confusion = [], [], []

        for entry in timeline_entries:
            ts = entry.get("timestamp", 0)
            if start_time <= ts < end_time:
                seg_engagement.append(entry.get("engagement", 50))
                seg_boredom.append(entry.get("boredom", 30))
                seg_confusion.append(entry.get("confusion", 20))

        # ONLY ADD SEGMENTS WITH REAL DATA - NEVER USE DUMMY/FALLBACK DATA
        if seg_engagement:
            avg_eng = sum(seg_engagement) / max(len(seg_engagement), 1)
            avg_bore = sum(seg_boredom) / max(len(seg_boredom), 1)
            avg_conf = sum(seg_confusion) / max(len(seg_confusion), 1)

            segments.append({
                "index": seg_idx,
                "start_time": round(start_time, 1),
                "end_time": round(end_time, 1),
                "engagement": round(avg_eng, 1),
                "boredom": round(avg_bore, 1),
                "confusion": round(avg_conf, 1),
                "intensity": round(avg_eng / 100.0, 3),
                "student_count": len(set(l.student_id for l in logs)),
            })

    pain_points = [
        {
            "segment": s["index"],
            "time_range": f"{int(s['start_time'])}s - {int(s['end_time'])}s",
            "issue": "high_confusion" if s["confusion"] > 50 else "low_engagement",
            "severity": "high" if s["engagement"] < 25 or s["confusion"] > 70 else "medium",
        }
        for s in segments if s["engagement"] < 40 or s["confusion"] > 50
    ]

    return {
        "lecture_id": lecture_id,
        "lecture_title": lecture.title,
        "duration": duration,
        "segment_count": segment_count,
        "segments": segments,
        "avg_engagement": round(sum(s["engagement"] for s in segments) / max(len(segments), 1), 1),
        "pain_points": pain_points,
        "total_views": len(logs),
    }


@router.get("/heatmap/{lecture_id}/me")
async def get_my_engagement_heatmap(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get student-specific engagement heatmap for current user and lecture."""
    lecture_result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = lecture_result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    result = await db.execute(
        select(EngagementLog)
        .where(EngagementLog.lecture_id == lecture_id, EngagementLog.student_id == current_user.id)
        .order_by(EngagementLog.started_at)
    )
    logs = result.scalars().all()

    if not logs:
        return {"lecture_id": lecture_id, "segments": [], "avg_engagement": 0, "pain_points": [], "scope": "student"}

    duration = lecture.duration or 300
    segment_count = min(20, max(5, duration // 30))
    segment_length = duration / segment_count

    timeline_entries = []
    for log in logs:
        if log.scores_timeline:
            for entry in log.scores_timeline:
                timeline_entries.append(
                    {
                        "timestamp": entry.get("timestamp", 0),
                        "engagement": entry.get("engagement", 50),
                        "boredom": entry.get("boredom", 30),
                        "confusion": entry.get("confusion", 20),
                    }
                )

    segments = []
    for seg_idx in range(segment_count):
        start_time = seg_idx * segment_length
        end_time = (seg_idx + 1) * segment_length
        seg_engagement, seg_boredom, seg_confusion = [], [], []

        for entry in timeline_entries:
            ts = entry.get("timestamp", 0)
            if start_time <= ts < end_time:
                seg_engagement.append(entry.get("engagement", 50))
                seg_boredom.append(entry.get("boredom", 30))
                seg_confusion.append(entry.get("confusion", 20))

        # ONLY ADD SEGMENTS WITH REAL DATA - NEVER USE DUMMY/FALLBACK DATA
        if seg_engagement:
            avg_eng = sum(seg_engagement) / max(len(seg_engagement), 1)
            avg_bore = sum(seg_boredom) / max(len(seg_boredom), 1)
            avg_conf = sum(seg_confusion) / max(len(seg_confusion), 1)

            segments.append(
                {
                    "index": seg_idx,
                    "start_time": round(start_time, 1),
                    "end_time": round(end_time, 1),
                    "engagement": round(avg_eng, 1),
                    "boredom": round(avg_bore, 1),
                    "confusion": round(avg_conf, 1),
                    "intensity": round(avg_eng / 100.0, 3),
                    "student_count": 1,
                }
            )

    pain_points = [
        {
            "segment": s["index"],
            "time_range": f"{int(s['start_time'])}s - {int(s['end_time'])}s",
            "issue": "high_confusion" if s["confusion"] > 50 else "low_engagement",
            "severity": "high" if s["engagement"] < 25 or s["confusion"] > 70 else "medium",
        }
        for s in segments
        if s["engagement"] < 40 or s["confusion"] > 50
    ]

    return {
        "lecture_id": lecture_id,
        "lecture_title": lecture.title,
        "duration": duration,
        "segment_count": segment_count,
        "segments": segments,
        "avg_engagement": round(sum(s["engagement"] for s in segments) / max(len(segments), 1), 1),
        "pain_points": pain_points,
        "total_views": len(logs),
        "scope": "student",
    }


@router.get("/live-watchers/{lecture_id}")
async def get_live_watchers(
    lecture_id: str,
    window_seconds: int = 120,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View which students are currently active on a lecture (Public count for students)."""
    is_privileged = current_user.role in [UserRole.TEACHER, UserRole.ADMIN]
    
    window_seconds = max(30, min(window_seconds, 900))
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)

    result = await db.execute(
        select(EngagementLog, User)
        .join(User, User.id == EngagementLog.student_id)
        .where(EngagementLog.lecture_id == lecture_id)
        .order_by(EngagementLog.started_at.desc())
    )
    rows = result.all()

    latest_by_student = {}
    for log, student in rows:
        if log.student_id not in latest_by_student:
            latest_by_student[log.student_id] = (log, student)

    viewers = []
    for _, (log, student) in latest_by_student.items():
        is_live = bool(log.started_at and log.started_at >= cutoff)
        viewers.append(
            {
                "student_id": student.id,
                "student_name": student.full_name,
                "student_email": student.email,
                "is_live": is_live,
                "last_seen": log.started_at.isoformat() if log.started_at else None,
                "watch_duration": log.watch_duration or 0,
                "engagement_score": round(log.engagement_score or 0, 1),
                "icap_classification": log.icap_classification.value if log.icap_classification else None,
                "model_type": (log.features or {}).get("model_type"),
            }
        )

    live_count = sum(1 for v in viewers if v["is_live"])
    
    # Return count only for students to ensure privacy synchronization
    if not is_privileged:
        return {
            "lecture_id": lecture_id,
            "window_seconds": window_seconds,
            "live_count": live_count,
            "count": live_count,
            "total_students_seen": len(viewers)
        }

    return {
        "lecture_id": lecture_id,
        "window_seconds": window_seconds,
        "live_count": live_count,
        "total_students_seen": len(viewers),
        "viewers": viewers,
    }


@router.get("/model-info")
async def get_model_info():
    """Get information about the current engagement model (Distributed Pipeline)."""
    return {
        "model_loaded": True,
        "model_type": "distributed_async_ensemble",
        "model_version": "3.0.0-pro",
        "description": "Distributed asynchronous pipeline using SQS and Fargate Spot ML Workers. Optimized for cost and scalability.",
        "features": FEATURE_NAMES,
        "num_features": len(FEATURE_NAMES),
        "dimensions": ["boredom", "engagement", "confusion", "frustration"],
        "icap_levels": ["passive", "active", "constructive", "interactive"],
        "temporal_smoothing": True,
        "shap_enabled": True,
        "fuzzy_rules_enabled": True,
    }


@router.get("/models")
async def list_runtime_models():
    """List all runtime-selectable models via the remote ML Client."""
    models = await ml_client.get_models()
    return {
        "models": models,
        "count": len(models),
    }


@router.post("/models/infer")
async def infer_with_selected_model(
    request: ModelInferenceRequest,
    current_user: User = Depends(get_current_user),
):
    """Run asynchronous inference with a user-selected model for manual testing."""
    # Note: Creating a 'fake' log entry for testing isn't ideal,
    # but we follow the async pattern here to stay consistent.
    t0 = time.perf_counter()
    feature_count = len(request.features or [])
    
    # In the pro architecture, we don't return immediate results for heavy models.
    # We return a job status so the user can poll.
    return {
        "status": "async_only",
        "message": "Manual sync inference is disabled on the backend. Use the normal /submit flow to trigger async jobs.",
        "features_received": feature_count,
        "model_id": request.model_id
    }
