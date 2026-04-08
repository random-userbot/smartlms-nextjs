"""
Smart LMS - Multimodal Engagement Model (Lightweight Version)
Pedagogical logic and feature extraction only. 
Heavy inference moved to smartlms-ml-service.
"""

import numpy as np
import os
import logging
from typing import Dict, List, Optional, Tuple, Any

# ML Frameworks moved to Microservice to save local RAM
TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants for feature extraction
RUNTIME_SIGNAL_NAMES = ["ear", "gaze", "mouth", "brow", "stability", "yaw", "pitch", "roll"]
STAT_SUFFIXES = ["mean", "std", "min", "max", "range", "slope", "p10", "p90"]

RUNTIME_FEATURE_NAMES = []
for _sig in RUNTIME_SIGNAL_NAMES:
    for _stat in STAT_SUFFIXES:
        RUNTIME_FEATURE_NAMES.append(f"{_sig}_{_stat}")
RUNTIME_FEATURE_NAMES.extend(["blink_count", "blink_rate"])
RUNTIME_FEATURE_NAMES.extend([
    "keyboard_pct", "mouse_pct", "tab_visible_pct",
    "playback_speed_avg", "note_taking_pct",
])
NUM_RUNTIME_FEATURES = len(RUNTIME_FEATURE_NAMES)  # 71

DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]

OPTIMAL_THRESHOLDS = {
    "boredom": 0.62,
    "engagement": 0.30,
    "confusion": 0.48,
    "frustration": 0.36,
}

FEATURE_NAMES = [
    "au01_inner_brow_raise", "au02_outer_brow_raise",
    "au04_brow_lowerer", "au06_cheek_raiser",
    "au12_lip_corner_puller", "au15_lip_corner_depressor",
    "au25_lips_part", "au26_jaw_drop",
    "gaze_score", "head_pose_yaw", "head_pose_pitch",
    "head_pose_roll", "head_pose_stability", "eye_aspect_ratio",
    "blink_rate", "mouth_openness",
    "keyboard_activity_pct", "mouse_activity_pct",
    "tab_visible_pct", "playback_speed_avg", "note_taking_pct",
    "gaze_variance", "head_stability_variance", "blink_rate_variance",
]

class EngagementFeatureExtractor:
    """Extract features for rule-based pedagogical logic."""

    @staticmethod
    def _signal_stats(values: list) -> list:
        if not values or len(values) == 0:
            return [0.0] * 8
        arr = np.array(values, dtype=np.float32)
        n = len(arr)
        return [
            float(np.mean(arr)), float(np.std(arr)),
            float(np.min(arr)), float(np.max(arr)),
            float(np.max(arr) - np.min(arr)),
            float(np.polyfit(np.arange(n), arr, 1)[0]) if n > 1 and np.std(arr) > 1e-8 else 0.0,
            float(np.percentile(arr, 10)), float(np.percentile(arr, 90)),
        ]

    @staticmethod
    def extract_v2(features_list: List[dict]) -> np.ndarray:
        """Extract 71-dim summary vector for rule-based scoring."""
        if not features_list:
            return np.zeros(NUM_RUNTIME_FEATURES, dtype=np.float32)
        
        def get_val(f, key, default=0.0):
            if isinstance(f, dict):
                return f.get(key, default)
            return getattr(f, key, default)

        ear_vals, gaze_vals, mouth_vals = [], [], []
        brow_vals, stability_vals = [], []
        yaw_vals, pitch_vals, roll_vals = [], [], []

        for f in features_list:
            el = float(get_val(f, "eye_aspect_ratio_left", 0.25) or 0.25)
            er = float(get_val(f, "eye_aspect_ratio_right", 0.25) or 0.25)
            ear_vals.append((el + er) / 2.0)
            
            g = get_val(f, "gaze_score", None)
            if g is None:
                gx = float(get_val(f, "gaze_angle_x", 0.0) or 0.0)
                gy = float(get_val(f, "gaze_angle_y", 0.0) or 0.0)
                g = max(0.0, 1.0 - (np.sqrt(gx**2 + gy**2) / 30.0))
            gaze_vals.append(float(g))
            
            m = float(get_val(f, "mouth_openness", 0.0) or get_val(f, "au25_lips_part", 0.0) or 0.0)
            mouth_vals.append(m)
            
            au01 = float(get_val(f, "au01_inner_brow_raise", 0.0) or 0.0)
            au04 = float(get_val(f, "au04_brow_lowerer", 0.0) or 0.0)
            brow_vals.append(au01 - au04)
            
            stability_vals.append(float(get_val(f, "head_pose_stability", 0.5) or 0.5))
            yaw_vals.append(abs(float(get_val(f, "head_pose_yaw", 0.0) or 0.0)))
            pitch_vals.append(abs(float(get_val(f, "head_pose_pitch", 0.0) or 0.0)))
            roll_vals.append(abs(float(get_val(f, "head_pose_roll", 0.0) or 0.0)))

        feats = []
        for vals in [ear_vals, gaze_vals, mouth_vals, brow_vals, stability_vals, yaw_vals, pitch_vals, roll_vals]:
            feats.extend(EngagementFeatureExtractor._signal_stats(vals))

        if len(ear_vals) > 2:
            ear_arr = np.array(ear_vals)
            blinks = int(np.sum(np.diff((ear_arr < 0.2).astype(int)) > 0))
            rate = blinks / max(len(features_list)/30.0, 0.1) * 60.0
            feats.extend([float(blinks), float(rate)])
        else:
            feats.extend([0.0, 0.0])

        n = len(features_list)
        feats.append(sum(1 for f in features_list if get_val(f, "keyboard_active", False)) / n)
        feats.append(sum(1 for f in features_list if get_val(f, "mouse_active", False)) / n)
        feats.append(sum(1 for f in features_list if get_val(f, "tab_visible", True)) / n)
        feats.append(np.mean([float(get_val(f, "playback_speed", 1.0) or 1.0) for f in features_list]))
        feats.append(sum(1 for f in features_list if get_val(f, "note_taking", False)) / n)

        return np.array(feats, dtype=np.float32)

    @staticmethod
    def extract_from_batch(features_list: List[dict]) -> np.ndarray:
        """Legacy extraction for 24 compatibility."""
        if not features_list: return np.zeros(24, dtype=np.float32)
        return EngagementFeatureExtractor.extract_v2(features_list)[:24]

class ICAPClassifier:
    """Classifies learning behaviors into ICAP levels."""
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
        if not features_list:
            return "passive", {"reason": "no_data"}, 0.3

        n = len(features_list)
        def get_val(f, key, default=0.0):
            return f.get(key, default) if isinstance(f, dict) else getattr(f, key, default)

        note_pct = sum(1 for f in features_list if get_val(f, "note_taking", False)) / n
        keyboard_pct = sum(1 for f in features_list if get_val(f, "keyboard_active", False)) / n
        gaze_avg = np.mean([get_val(f, "gaze_score", 0.5) for f in features_list])
        mouse_pct = sum(1 for f in features_list if get_val(f, "mouse_active", False)) / n

        interactive_score = (keyboard_pct * 0.30 + note_pct * 0.25 + (1.0 if quiz_score is not None and quiz_score > 70 else 0.0) * 0.20 + mouse_pct * 0.15 + min(keyboard_events / 100, 1.0) * 0.10)
        constructive_score = (note_pct * 0.35 + keyboard_pct * 0.30 + gaze_avg * 0.20 + min(mouse_events / 50, 1.0) * 0.15)
        active_score = (gaze_avg * 0.50 + (1.0 - min(tab_switches / 5, 1.0)) * 0.30 + (1.0 if note_pct < 0.1 and keyboard_pct < 0.1 else 0.5) * 0.20)

        evidence = {
            "keyboard_events": keyboard_events,
            "mouse_events": mouse_events,
            "note_taking_pct": round(note_pct, 4),
            "keyboard_pct": round(keyboard_pct, 4),
            "gaze_avg": round(gaze_avg, 4),
            "tab_switches": tab_switches,
            "quiz_score": quiz_score,
            "scores": {
                "interactive": round(interactive_score, 3),
                "constructive": round(constructive_score, 3),
                "active": round(active_score, 3),
            }
        }

        if interactive_score >= ICAPClassifier.INTERACTIVE_THRESHOLD:
            return "interactive", evidence, min(0.95, interactive_score)
        if constructive_score >= ICAPClassifier.CONSTRUCTIVE_THRESHOLD:
            return "constructive", evidence, min(0.90, constructive_score + 0.1)
        if active_score >= ICAPClassifier.ACTIVE_THRESHOLD:
            return "active", evidence, min(0.85, active_score + 0.1)
        return "passive", evidence, 0.6

class FuzzyEngagementRules:
    """Fuzzy-logic engagement rules for human-readable explanations."""
    @staticmethod
    def evaluate(feature_vector: np.ndarray, scores: Dict) -> List[Dict]:
        gaze = feature_vector[8] if len(feature_vector) > 8 else 0.5
        stab = feature_vector[32] if len(feature_vector) > 32 else 0.5
        tab = feature_vector[68] if len(feature_vector) > 68 else 1.0
        brow = feature_vector[24] if len(feature_vector) > 24 else 0.0

        rules = []
        if gaze < 0.4 and tab < 0.5:
            rules.append({
                "rule": "IF gaze is LOW AND tab-focus is LOW THEN engagement = LOW",
                "severity": "high",
                "dimension": "engagement",
                "suggestion": "User appears distracted. Review recent content clarity."
            })
        if gaze > 0.7 and stab > 0.6:
            rules.append({
                "rule": "IF gaze is HIGH AND head-stable THEN engagement = HIGH",
                "severity": "positive",
                "dimension": "engagement",
                "suggestion": "Excellent focus levels detected."
            })
        if brow > 0.4:
            rules.append({
                "rule": "IF brow-furrowed is HIGH THEN confusion = HIGH",
                "severity": "medium",
                "dimension": "confusion",
                "suggestion": "Potential struggle with concept detected."
            })
        
        if not rules:
            rules.append({
                "rule": "All behavioral metrics within optimal range",
                "severity": "positive",
                "dimension": "overall",
                "suggestion": "Maintain current learning momentum."
            })
        return rules

# --- Global Accessors ---
_icap_classifier = ICAPClassifier()
_fuzzy_rules = FuzzyEngagementRules()

def get_icap_classifier():
    return _icap_classifier

def get_fuzzy_rules():
    return _fuzzy_rules

def get_engagement_model():
    """Stub for remote model logic"""
    return None
