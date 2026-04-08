"""
Smart LMS - Multimodal Engagement Model
XGBoost-based engagement classifier with SHAP explanations.
Based on: "Designing an Explainable Multimodal Engagement Model"

Architecture:
  - Extracts interpretable features (facial AUs, gaze, head pose, behavioral signals)
  - Uses XGBoost (Das & Dev found 82.9% accuracy on DAiSEE with AU+behavioral features)
  - Provides real SHAP explanations for every prediction
  - Supports 4 engagement dimensions: Boredom, Engagement, Confusion, Frustration

References:
  [1] Das & Dev - XGBoost on AU+behavioral features
  [4] Zhao et al. - Fuzzy-logic models for interpretability
  [5] Cheng et al. - Gradient magnitude mapping
"""

import numpy as np
import os
import json
import joblib
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Feature names used by the model (must match training)
FEATURE_NAMES = [
    # Facial Action Units (8)
    "au01_inner_brow_raise",
    "au02_outer_brow_raise",
    "au04_brow_lowerer",
    "au06_cheek_raiser",
    "au12_lip_corner_puller",
    "au15_lip_corner_depressor",
    "au25_lips_part",
    "au26_jaw_drop",
    # Gaze & Head Pose (6)
    "gaze_score",
    "head_pose_yaw",
    "head_pose_pitch",
    "head_pose_roll",
    "head_pose_stability",
    "eye_aspect_ratio",
    # Eye & Mouth (2)
    "blink_rate",
    "mouth_openness",
    # Behavioral signals (5)
    "keyboard_activity_pct",
    "mouse_activity_pct",
    "tab_visible_pct",
    "playback_speed_avg",
    "note_taking_pct",
    # Temporal features (3)
    "gaze_variance",
    "head_stability_variance",
    "blink_rate_variance",
]

NUM_FEATURES = len(FEATURE_NAMES)

# Engagement dimension targets
DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]

# Model directory
MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")


class EngagementFeatureExtractor:
    """
    Extract interpretable features from raw MediaPipe data + behavioral signals.
    Designed for multimodal fusion as recommended by the research paper.
    """

    @staticmethod
    def extract_from_batch(features_list: List[dict]) -> np.ndarray:
        """
        Extract aggregated features from a batch of raw frame-level features.
        Returns a single feature vector of shape (NUM_FEATURES,).
        """
        if not features_list:
            return np.zeros(NUM_FEATURES, dtype=np.float32)

        n = len(features_list)

        # Aggregate facial AUs
        au01 = np.mean([f.get("au01_inner_brow_raise", 0) for f in features_list])
        au02 = np.mean([f.get("au02_outer_brow_raise", 0) for f in features_list])
        au04 = np.mean([f.get("au04_brow_lowerer", 0) for f in features_list])
        au06 = np.mean([f.get("au06_cheek_raiser", 0) for f in features_list])
        au12 = np.mean([f.get("au12_lip_corner_puller", 0) for f in features_list])
        au15 = np.mean([f.get("au15_lip_corner_depressor", 0) for f in features_list])
        au25 = np.mean([f.get("au25_lips_part", 0) for f in features_list])
        au26 = np.mean([f.get("au26_jaw_drop", 0) for f in features_list])

        # Gaze & Head Pose
        gaze_scores = [f.get("gaze_score", 0.5) for f in features_list]
        gaze_score = np.mean(gaze_scores)
        head_yaw = np.mean([abs(f.get("head_pose_yaw", 0)) for f in features_list])
        head_pitch = np.mean([abs(f.get("head_pose_pitch", 0)) for f in features_list])
        head_roll = np.mean([abs(f.get("head_pose_roll", 0)) for f in features_list])
        head_stab_values = [f.get("head_pose_stability", 0.5) for f in features_list]
        head_stability = np.mean(head_stab_values)
        ear_avg = np.mean([
            (f.get("eye_aspect_ratio_left", 0.25) + f.get("eye_aspect_ratio_right", 0.25)) / 2
            for f in features_list
        ])

        # Eye & Mouth
        blink_values = [f.get("blink_rate", 15) for f in features_list]
        blink_rate = np.mean(blink_values)
        mouth = np.mean([f.get("mouth_openness", 0) for f in features_list])

        # Behavioral signals
        keyboard_pct = sum(1 for f in features_list if f.get("keyboard_active", False)) / n
        mouse_pct = sum(1 for f in features_list if f.get("mouse_active", False)) / n
        tab_pct = sum(1 for f in features_list if f.get("tab_visible", True)) / n
        speed_avg = np.mean([f.get("playback_speed", 1.0) for f in features_list])
        note_pct = sum(1 for f in features_list if f.get("note_taking", False)) / n

        # Temporal variance features (captures dynamics)
        gaze_var = np.var(gaze_scores) if n > 1 else 0.0
        head_var = np.var(head_stab_values) if n > 1 else 0.0
        blink_var = np.var(blink_values) if n > 1 else 0.0

        feature_vector = np.array([
            au01, au02, au04, au06, au12, au15, au25, au26,
            gaze_score, head_yaw, head_pitch, head_roll, head_stability, ear_avg,
            blink_rate, mouth,
            keyboard_pct, mouse_pct, tab_pct, speed_avg, note_pct,
            gaze_var, head_var, blink_var,
        ], dtype=np.float32)

        return feature_vector


class EngagementModel:
    """
    XGBoost-based multimodal engagement model with SHAP explanations.
    
    Following the research paper recommendations:
    - XGBoost on AU+behavioral features (Das & Dev approach, 82.9% on DAiSEE)
    - SHAP for feature-level explanations
    - Separate models for each engagement dimension
    - Temporal smoothing for stable predictions
    """

    def __init__(self):
        self.models: Dict[str, object] = {}  # dimension -> XGBoost model
        self.explainers: Dict[str, object] = {}  # dimension -> SHAP TreeExplainer
        self.is_loaded = False
        self.feature_extractor = EngagementFeatureExtractor()
        self._prediction_history: List[Dict] = []  # For temporal smoothing

    def load(self) -> bool:
        """Load trained models from disk."""
        try:
            import xgboost as xgb
            import shap

            if not os.path.exists(MODEL_DIR):
                logger.warning(f"Model directory not found: {MODEL_DIR}")
                return False

            for dim in DIMENSION_NAMES:
                model_path = os.path.join(MODEL_DIR, f"xgb_{dim}.joblib")
                if os.path.exists(model_path):
                    self.models[dim] = joblib.load(model_path)
                    self.explainers[dim] = shap.TreeExplainer(self.models[dim])
                    logger.info(f"Loaded model for {dim}")
                else:
                    logger.warning(f"Model file not found: {model_path}")
                    return False

            self.is_loaded = True
            logger.info("All engagement models loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False

    def predict(self, features_list: List[dict]) -> Dict:
        """
        Predict engagement scores from raw features.
        Falls back to rule-based scoring if model not loaded.

        Returns:
            Dict with scores (0-100), SHAP explanations, and confidence
        """
        feature_vector = self.feature_extractor.extract_from_batch(
            [f if isinstance(f, dict) else f.__dict__ if hasattr(f, '__dict__') else {}
             for f in features_list]
        )

        if self.is_loaded:
            return self._predict_with_model(feature_vector)
        else:
            return self._predict_rule_based(feature_vector, features_list)

    def _predict_with_model(self, feature_vector: np.ndarray) -> Dict:
        """Predict using trained XGBoost models with SHAP explanations."""
        import shap

        X = feature_vector.reshape(1, -1)
        scores = {}
        shap_explanations = {}

        for dim in DIMENSION_NAMES:
            if dim in self.models:
                # Predict (models output 0-3 scale like DAiSEE, convert to 0-100)
                raw_pred = self.models[dim].predict(X)[0]
                scores[dim] = float(np.clip(raw_pred / 3.0 * 100, 0, 100))

                # SHAP explanation
                shap_values = self.explainers[dim].shap_values(X)
                if isinstance(shap_values, list):
                    shap_values = shap_values[0]
                shap_dict = {
                    FEATURE_NAMES[i]: round(float(shap_values[0][i]), 4)
                    for i in range(NUM_FEATURES)
                }
                shap_explanations[dim] = shap_dict

        # Compute overall score  
        overall = (
            scores.get("engagement", 50) * 0.4 +
            (100 - scores.get("boredom", 30)) * 0.3 +
            (100 - scores.get("confusion", 20)) * 0.2 +
            (100 - scores.get("frustration", 10)) * 0.1
        )

        # Temporal smoothing: weighted average with recent predictions
        smoothed = self._apply_temporal_smoothing(scores, overall)

        # Top contributing features across all dimensions
        combined_importance = {}
        for dim, shap_dict in shap_explanations.items():
            for feat, val in shap_dict.items():
                if feat not in combined_importance:
                    combined_importance[feat] = 0
                combined_importance[feat] += abs(val)

        top_factors = sorted(combined_importance.items(), key=lambda x: x[1], reverse=True)[:6]

        return {
            "overall": round(smoothed["overall"], 1),
            "boredom": round(smoothed["boredom"], 1),
            "engagement": round(smoothed["engagement"], 1),
            "confusion": round(smoothed["confusion"], 1),
            "frustration": round(smoothed["frustration"], 1),
            "shap_explanations": shap_explanations,
            "top_factors": [
                {"feature": feat, "importance": round(imp, 4)}
                for feat, imp in top_factors
            ],
            "model_type": "xgboost",
            "confidence": self._compute_confidence(feature_vector),
        }

    def _predict_rule_based(self, feature_vector: np.ndarray, raw_features: List) -> Dict:
        """
        Enhanced rule-based scoring (fallback when model not trained).
        Uses weighted feature combination with interpretable formulas.
        Improved based on research paper insights.
        """
        # Unpack features
        (au01, au02, au04, au06, au12, au15, au25, au26,
         gaze, yaw, pitch, roll, stability, ear,
         blink, mouth,
         keyboard, mouse, tab, speed, notes,
         gaze_var, head_var, blink_var) = feature_vector

        # Normalize blink rate (normal: 15-20 bpm)
        blink_norm = 1.0 - min(abs(blink - 17) / 20.0, 1.0)

        # === Engagement (higher = more engaged) ===
        engagement = np.clip(
            gaze * 25 +                  # Looking at screen
            stability * 20 +             # Stable head position
            ear * 40 +                   # Eyes open (EAR ~0.25 normal)
            tab * 20 +                   # Tab visible
            keyboard * 10 +              # Active typing
            notes * 8 +                  # Note-taking
            au06 * 5 +                   # Cheek raiser (attentive smile)
            au12 * 5 +                   # Smile (positive engagement)
            blink_norm * 5 -             # Normal blink rate
            (1 - stability) * 10 -       # Penalize restlessness
            gaze_var * 15,               # Penalize gaze instability
            0, 100
        )

        # === Boredom (higher = more bored) ===
        boredom = np.clip(
            (1 - gaze) * 25 +           # Not looking at screen
            (1 - stability) * 15 +       # Restless movement
            (blink / 40) * 15 +          # High blink rate = fatigue/boredom
            (1 - tab) * 20 +             # Tab switching away
            (1 - keyboard) * 8 +         # Idle hands
            au15 * 10 +                  # Lip corner depressor (frown)
            (speed - 1) * 10 +           # Fast playback = bored
            head_var * 10,               # Head movement variance
            0, 100
        )

        # === Confusion (higher = more confused) ===
        confusion = np.clip(
            au04 * 30 +                  # Furrowed brows (key confusion signal)
            au01 * 15 +                  # Inner brow raise
            (1 - stability) * 15 +       # Head tilting (searching behavior)
            mouth * 12 +                 # Mouth movement
            (1 - gaze) * 10 +            # Looking away
            blink_var * 15 +             # Irregular blinking
            au02 * 8,                    # Outer brow raise
            0, 100
        )

        # === Frustration (higher = more frustrated) ===
        frustration = np.clip(
            au04 * 25 +                  # Furrowed brows
            (1 - au12) * 12 +            # No smile
            au15 * 15 +                  # Lip corner depressor (frown)
            abs(blink - 17) * 0.5 +      # Abnormal blink rate
            (1 - tab) * 15 +             # Tab switching (giving up)
            gaze_var * 10 +              # Erratic gaze
            (1 - keyboard) * 5,          # Stopped typing
            0, 100
        )

        # Overall weighted score
        overall = (
            engagement * 0.4 +
            (100 - boredom) * 0.3 +
            (100 - confusion) * 0.2 +
            (100 - frustration) * 0.1
        )

        scores = {
            "boredom": boredom,
            "engagement": engagement,
            "confusion": confusion,
            "frustration": frustration,
        }

        # Apply temporal smoothing
        smoothed = self._apply_temporal_smoothing(scores, overall)

        # Compute SHAP-style feature contributions (rule-based)
        shap_explanations = self._compute_rule_based_shap(feature_vector)

        return {
            "overall": round(smoothed["overall"], 1),
            "boredom": round(smoothed["boredom"], 1),
            "engagement": round(smoothed["engagement"], 1),
            "confusion": round(smoothed["confusion"], 1),
            "frustration": round(smoothed["frustration"], 1),
            "shap_explanations": shap_explanations,
            "top_factors": self._get_top_factors(shap_explanations),
            "model_type": "rule_based",
            "confidence": 0.7,  # Lower confidence for rule-based
        }

    def _compute_rule_based_shap(self, feature_vector: np.ndarray) -> Dict:
        """
        Compute interpretable feature contributions for rule-based model.
        Simulates SHAP-style explanations based on feature deviations from baseline.
        """
        # Baseline (neutral student)
        baseline = np.array([
            0.1, 0.1, 0.1, 0.1, 0.2, 0.1, 0.1, 0.1,  # AUs
            0.7, 5.0, 4.0, 2.5, 0.7, 0.25,              # Gaze/Head
            17.0, 0.1,                                      # Blink/Mouth
            0.15, 0.3, 0.9, 1.0, 0.1,                     # Behavioral
            0.02, 0.02, 5.0,                                # Variance
        ], dtype=np.float32)

        # Feature importance weights per dimension
        weights = {
            "engagement": np.array([
                0.02, 0.01, -0.03, 0.04, 0.05, -0.02, 0.01, 0.01,
                0.25, -0.05, -0.03, -0.02, 0.20, 0.10,
                0.03, -0.02,
                0.10, 0.05, 0.20, -0.05, 0.08,
                -0.10, -0.05, -0.03,
            ]),
        }

        explanations = {}
        for dim in ["engagement"]:
            w = weights.get(dim, np.ones(NUM_FEATURES) * 0.04)
            deviations = feature_vector - baseline
            contributions = deviations * w
            explanations[dim] = {
                FEATURE_NAMES[i]: round(float(contributions[i]), 4)
                for i in range(NUM_FEATURES)
            }

        return explanations

    def _get_top_factors(self, shap_explanations: Dict) -> List[Dict]:
        """Get top contributing features from SHAP explanations."""
        combined = {}
        for dim, shap_dict in shap_explanations.items():
            for feat, val in shap_dict.items():
                if feat not in combined:
                    combined[feat] = 0
                combined[feat] += abs(val)

        sorted_feats = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:6]
        return [
            {"feature": feat, "importance": round(imp, 4)}
            for feat, imp in sorted_feats
        ]

    def _apply_temporal_smoothing(self, scores: Dict, overall: float) -> Dict:
        """
        Apply temporal smoothing over recent predictions.
        Aggregates over a sliding window (research recommends 5-10 sec).
        Helps produce stable, non-jittery engagement scores.
        """
        current = {**scores, "overall": overall}

        self._prediction_history.append(current)
        # Keep last 5 predictions (sliding window)
        if len(self._prediction_history) > 5:
            self._prediction_history = self._prediction_history[-5:]

        if len(self._prediction_history) == 1:
            return current

        # Exponentially weighted moving average (recent = more weight)
        weights = np.array([0.1, 0.15, 0.2, 0.25, 0.3])[-len(self._prediction_history):]
        weights = weights / weights.sum()

        smoothed = {}
        for key in current.keys():
            values = [h[key] for h in self._prediction_history]
            smoothed[key] = float(np.average(values, weights=weights))

        return smoothed

    def _compute_confidence(self, feature_vector: np.ndarray) -> float:
        """Compute prediction confidence based on feature quality."""
        gaze = feature_vector[8]
        stability = feature_vector[12]
        ear = feature_vector[13]

        # If features look like face was detected properly
        if gaze > 0.1 and ear > 0.1 and stability > 0.1:
            return min(0.95, 0.6 + gaze * 0.2 + stability * 0.15)
        return 0.3  # Low confidence if face not detected well


class ICAPClassifier:
    """
    ICAP Framework Classifier (Chi & Wylie 2014).
    Categorizes student learning behaviors into:
      - Interactive: Engaging with peers/content collaboratively
      - Constructive: Generating output (notes, summaries, questions)
      - Active: Attentive watching, following along
      - Passive: Minimal engagement, just watching

    Each successive mode (P->A->C->I) is associated with deeper processing
    and better learning outcomes.
    """

    # Weights for ICAP classification (tuned based on research)
    INTERACTIVE_THRESHOLD = 0.65
    CONSTRUCTIVE_THRESHOLD = 0.45
    ACTIVE_THRESHOLD = 0.30

    @staticmethod
    def classify(
        features_list: List[dict],
        keyboard_events: int = 0,
        mouse_events: int = 0,
        quiz_score: Optional[float] = None,
        tab_switches: int = 0,
        note_taking_detected: bool = False,
    ) -> Tuple[str, Dict, float]:
        """
        Classify student behavior into ICAP level.
        
        Returns:
            Tuple of (level, evidence_dict, confidence)
        """
        if not features_list:
            return "passive", {"reason": "no_data"}, 0.3

        n = len(features_list)

        # Extract behavioral indicators
        note_pct = sum(1 for f in features_list
                       if (f.get("note_taking", False) if isinstance(f, dict)
                           else getattr(f, "note_taking", False))) / n
        keyboard_pct = sum(1 for f in features_list
                          if (f.get("keyboard_active", False) if isinstance(f, dict)
                              else getattr(f, "keyboard_active", False))) / n
        gaze_avg = np.mean([
            f.get("gaze_score", 0.5) if isinstance(f, dict) else getattr(f, "gaze_score", 0.5)
            for f in features_list
        ])
        mouse_pct = sum(1 for f in features_list
                       if (f.get("mouse_active", False) if isinstance(f, dict)
                           else getattr(f, "mouse_active", False))) / n

        # Compute ICAP score (0-1 scale)
        # Interactive: high keyboard + notes + quiz interaction
        interactive_score = (
            keyboard_pct * 0.30 +
            note_pct * 0.25 +
            (1.0 if quiz_score is not None and quiz_score > 70 else 0.0) * 0.20 +
            mouse_pct * 0.15 +
            min(keyboard_events / 100, 1.0) * 0.10
        )

        # Constructive: generating notes, moderate keyboard
        constructive_score = (
            note_pct * 0.35 +
            keyboard_pct * 0.30 +
            gaze_avg * 0.20 +
            min(mouse_events / 50, 1.0) * 0.15
        )

        # Active: attentive watching
        active_score = (
            gaze_avg * 0.50 +
            (1.0 - min(tab_switches / 5, 1.0)) * 0.30 +
            (1.0 if note_pct < 0.1 and keyboard_pct < 0.1 else 0.5) * 0.20
        )

        evidence = {
            "keyboard_events": keyboard_events,
            "mouse_events": mouse_events,
            "note_taking_pct": round(note_pct, 3),
            "keyboard_pct": round(keyboard_pct, 3),
            "gaze_avg": round(gaze_avg, 3),
            "tab_switches": tab_switches,
            "quiz_score": quiz_score,
            "scores": {
                "interactive": round(interactive_score, 3),
                "constructive": round(constructive_score, 3),
                "active": round(active_score, 3),
            }
        }

        # Classification logic
        if interactive_score >= ICAPClassifier.INTERACTIVE_THRESHOLD:
            return "interactive", evidence, min(0.95, interactive_score)

        if constructive_score >= ICAPClassifier.CONSTRUCTIVE_THRESHOLD:
            return "constructive", evidence, min(0.90, constructive_score + 0.1)

        if active_score >= ICAPClassifier.ACTIVE_THRESHOLD:
            return "active", evidence, min(0.85, active_score + 0.1)

        return "passive", evidence, 0.6


class FuzzyEngagementRules:
    """
    Fuzzy-logic engagement rules for human-readable explanations.
    Based on Zhao et al. (2024) - fuzzy models capture uncertainty in educational data.
    
    Generates human-readable rules like:
    "IF eye-contact is low AND quiz score is low THEN engagement = low"
    """

    @staticmethod
    def evaluate(feature_vector: np.ndarray, scores: Dict) -> List[Dict]:
        """
        Evaluate fuzzy rules and return triggered rules with explanations.
        """
        gaze = feature_vector[8]
        stability = feature_vector[12]
        blink = feature_vector[14]
        keyboard = feature_vector[16]
        tab = feature_vector[18]
        au04 = feature_vector[2]  # Brow lowerer

        rules = []

        # Engagement rules
        if gaze < 0.4 and tab < 0.5:
            rules.append({
                "rule": "IF eye-contact is LOW AND tab-focus is LOW THEN engagement = LOW",
                "severity": "high",
                "dimension": "engagement",
                "suggestion": "Student appears distracted. Consider interactive content."
            })

        if gaze > 0.7 and stability > 0.6 and keyboard > 0.2:
            rules.append({
                "rule": "IF eye-contact is HIGH AND head-stable AND taking-notes THEN engagement = HIGH",
                "severity": "positive",
                "dimension": "engagement",
                "suggestion": "Student is actively engaged and taking notes."
            })

        # Boredom rules
        if blink > 25 and stability < 0.4:
            rules.append({
                "rule": "IF blink-rate is HIGH AND head-restless THEN boredom = HIGH",
                "severity": "medium",
                "dimension": "boredom",
                "suggestion": "Student may be fatigued. Consider a break or interactive activity."
            })

        # Confusion rules
        if au04 > 0.5 and gaze < 0.5:
            rules.append({
                "rule": "IF brow-furrowed AND looking-away THEN confusion = HIGH",
                "severity": "high",
                "dimension": "confusion",
                "suggestion": "Student appears confused. Simplify content or add examples."
            })

        if au04 > 0.3 and stability < 0.5:
            rules.append({
                "rule": "IF brow-lowered AND head-tilting THEN confusion = MODERATE",
                "severity": "medium",
                "dimension": "confusion",
                "suggestion": "Student may be struggling. Consider pausing for questions."
            })

        # Frustration rules
        if tab < 0.5 and keyboard < 0.1 and gaze < 0.4:
            rules.append({
                "rule": "IF tab-switching AND idle AND not-looking THEN frustration = HIGH",
                "severity": "high",
                "dimension": "frustration",
                "suggestion": "Student may be giving up. Provide support or simplify tasks."
            })

        if not rules:
            rules.append({
                "rule": "All indicators within normal range",
                "severity": "positive",
                "dimension": "overall",
                "suggestion": "Student engagement appears healthy."
            })

        return rules


# ─── Global Model Instance ───────────────────────────────
_model_instance: Optional[EngagementModel] = None


def get_engagement_model() -> EngagementModel:
    """Get or create the global engagement model instance."""
    global _model_instance
    if _model_instance is None:
        _model_instance = EngagementModel()
        # Try to load trained models
        loaded = _model_instance.load()
        if not loaded:
            logger.info("Using rule-based engagement scoring (no trained model found)")
    return _model_instance


def get_icap_classifier() -> ICAPClassifier:
    """Get ICAP classifier instance."""
    return ICAPClassifier()


def get_fuzzy_rules() -> FuzzyEngagementRules:
    """Get fuzzy rules evaluator instance."""
    return FuzzyEngagementRules()
