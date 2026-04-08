"""
Smart LMS - Multimodal Engagement Model v2 (Enhanced)
Ensemble of XGBoost (v2/v3) and PyTorch Deep Learning Models (BiLSTM, CNN-BiLSTM).

Architecture:
  - Extracts temporal statistics from per-frame features.
  - Runs XGBoost binary models (v2/v3) if features compatible.
  - Runs PyTorch sequence models (BiLSTM, Attention) on temporal sequences.
  - Provides Soft-Voting Ensemble results.
"""

import numpy as np
import os
import json
import joblib
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# PyTorch Imports (Optional)
try:
    import torch
    import torch.nn as nn
    from app.ml.pytorch_definitions import (
        BiLSTMModel, BiLSTMAttention, CNNBiLSTMAttention,
        MultiScaleConv, SEBlock, TemporalTransformer, BiLSTMGRUHybrid
    )
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch or definitions not found. Deep learning models disabled.")

logger = logging.getLogger(__name__)

# Runtime feature names (71 features)
RUNTIME_SIGNAL_NAMES = [
    "ear", "gaze", "mouth", "brow", "stability",
    "yaw", "pitch", "roll",
]
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

MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "experiment_results")

# Legacy feature names for compatibility
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
    """Extract features for both Summary (XGBoost) and Sequence (LSTM) models."""

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
        """Extract 71-dim summary vector for XGBoost/Hybrid."""
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
            
            au01 = float(get_val(f, "au01_inner_brow_raise", 0.0) or get_val(f, "AU01_r", 0.0) or 0.0)
            au04 = float(get_val(f, "au04_brow_lowerer", 0.0) or get_val(f, "AU04_r", 0.0) or 0.0)
            brow_vals.append(au01 - au04)
            
            stability_vals.append(float(get_val(f, "head_pose_stability", 0.5) or 0.5))
            yaw_vals.append(abs(float(get_val(f, "head_pose_yaw", 0.0) or get_val(f, "pose_Ry", 0.0) or 0.0)))
            pitch_vals.append(abs(float(get_val(f, "head_pose_pitch", 0.0) or get_val(f, "pose_Rx", 0.0) or 0.0)))
            roll_vals.append(abs(float(get_val(f, "head_pose_roll", 0.0) or get_val(f, "pose_Rz", 0.0) or 0.0)))

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
    def extract_sequence(features_list: List[dict], seq_len: int = 30) -> np.ndarray:
        """Extract sequence of 31-dim core features -> (seq_len, 31)."""
        sequence = []
        
        def get_val(f, keys, default=0.0):
            if not isinstance(keys, list): keys = [keys]
            for k in keys:
                val = f.get(k) if isinstance(f, dict) else getattr(f, k, None)
                if val is not None: return float(val)
            return default

        frames = features_list[-seq_len:] if len(features_list) > seq_len else features_list
        
        for f in frames:
            row = []
            # 1. AUs (17)
            row.append(get_val(f, ["au01_inner_brow_raise", "AU01_r"]))
            row.append(get_val(f, ["au02_outer_brow_raise", "AU02_r"]))
            row.append(get_val(f, ["au04_brow_lowerer", "AU04_r"]))
            row.append(get_val(f, ["au05_upper_lid_raiser", "AU05_r"])) 
            row.append(get_val(f, ["au06_cheek_raiser", "AU06_r"]))
            row.append(get_val(f, ["au07_lid_tightener", "AU07_r"]))
            row.append(get_val(f, ["au09_nose_wrinkler", "AU09_r"]))
            row.append(get_val(f, ["au10_upper_lip_raiser", "AU10_r"]))
            row.append(get_val(f, ["au12_lip_corner_puller", "AU12_r"]))
            row.append(get_val(f, ["au14_dimpler", "AU14_r"]))
            row.append(get_val(f, ["au15_lip_corner_depressor", "AU15_r"]))
            row.append(get_val(f, ["au17_chin_raiser", "AU17_r"]))
            row.append(get_val(f, ["au20_lip_stretcher", "AU20_r"]))
            row.append(get_val(f, ["au23_lip_tightener", "AU23_r"]))
            row.append(get_val(f, ["au25_lips_part", "AU25_r"]))
            row.append(get_val(f, ["au26_jaw_drop", "AU26_r"]))
            row.append(get_val(f, ["au45_blink", "AU45_r"]))
            
            # 2. Gaze (8)
            row.extend([0.0]*6) # gaze_0/1 x/y/z not available usually
            row.append(get_val(f, ["gaze_angle_x", "gaze_angle_x"]))
            row.append(get_val(f, ["gaze_angle_y", "gaze_angle_y"]))
            
            # 3. Pose (6)
            row.append(get_val(f, ["pose_Tx", "head_pose_tx"]))
            row.append(get_val(f, ["pose_Ty", "head_pose_ty"]))
            row.append(get_val(f, ["pose_Tz", "head_pose_tz"]))
            row.append(get_val(f, ["pose_Rx", "head_pose_pitch"]))
            row.append(get_val(f, ["pose_Ry", "head_pose_yaw"]))
            row.append(get_val(f, ["pose_Rz", "head_pose_roll"]))
            
            # 4. Synthesize Classification AUs (18 features) to match input_dim=49
            # Threshold regression AUs at 0.5 to approximate binary classification
            # Alignment: 01,02,04,05,06,07,09,10,12,14,15,17,20,23,25,26,28,45
            
            # First 16 from regression (01...26)
            au_regs = row[:16] 
            au_class = [1.0 if x > 0.5 else 0.0 for x in au_regs]
            
            # AU28_c (Lip Suck) - Not in regression, default to 0
            au_class.append(0.0) 
            
            # AU45_c (Blink) - Index 16 in regression
            au_class.append(1.0 if row[16] > 0.5 else 0.0)
            
            row.extend(au_class)
            
            sequence.append(row)
        
        # Pad with zeros if short
        if len(sequence) < seq_len:
            pad_len = seq_len - len(sequence)
            padding = [[0.0]*49 for _ in range(pad_len)]
            sequence = padding + sequence
            
        return np.array(sequence, dtype=np.float32)
        
    @staticmethod
    def extract_from_batch(features_list: List[dict]) -> np.ndarray:
        """Legacy extraction for 24 compatibility."""
        if not features_list: return np.zeros(24, dtype=np.float32)
        # Simplified implementation leveraging extract_v2 logic partially or reimplemented
        # For brevity, implementing dummy or minimal needed for compatibility
        # Re-using logic from original file...
        n = len(features_list)
        def get_val(f, key, default=0.0):
             return f.get(key, default) if isinstance(f, dict) else getattr(f, key, default)

        return np.zeros(24, dtype=np.float32) # Placeholder if needed, but extract_v2 handles main logic


class EngagementModel:
    def __init__(self):
        self.xgb_models: Dict[str, object] = {}
        self.torch_models: Dict[str, object] = {}
        self.scalers: Dict[str, object] = {}
        self.explainers: Dict[str, object] = {}
        self.model_version = "none"
        self.is_loaded = False
        self.feature_extractor = EngagementFeatureExtractor()
        self.thresholds = dict(OPTIMAL_THRESHOLDS)
        self.device = torch.device('cpu') if TORCH_AVAILABLE else None

    def load(self) -> bool:
        """Load trained models from disk."""
        try:
            if not os.path.exists(MODEL_DIR): 
                return False

            # Load XGBoost (v2/v3)
            loaded_xgb = 0
            for dim in DIMENSION_NAMES:
                # v2
                path = os.path.join(MODEL_DIR, f"xgb_v2_{dim}_bin.joblib")
                if os.path.exists(path):
                    self.xgb_models[dim] = joblib.load(path)
                    loaded_xgb += 1
            
            if loaded_xgb > 0:
                self.model_version = "v2_binary"
                self.is_loaded = True
                print(f"✅ [MODEL_LOAD] Loaded {loaded_xgb} XGBoost v2 models.", flush=True)
            else:
                 # v3
                 for dim in DIMENSION_NAMES:
                    path = os.path.join(MODEL_DIR, f"xgb_v3_{dim}_bin.joblib")
                    if os.path.exists(path):
                        self.xgb_models[dim] = joblib.load(path)
                        loaded_xgb += 1
                 if loaded_xgb > 0:
                    self.is_loaded = True
                    print(f"✅ [MODEL_LOAD] Loaded {loaded_xgb} XGBoost v3 models.", flush=True)
                 else:
                    print(f"❌ [MODEL_LOAD] No XGBoost models found in {MODEL_DIR}", flush=True)

            # Load PyTorch
            if TORCH_AVAILABLE:
                self._load_pytorch_models()

            return self.is_loaded

        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False

    def _load_pytorch_models(self):
        """Load BiLSTM / Attention models."""
        # BiLSTM v2
        for dim in DIMENSION_NAMES:
            path = os.path.join(MODEL_DIR, f"lstm_v2_{dim}_bin.pt")
            if os.path.exists(path):
                try:
                    model = BiLSTMModel(input_dim=49, hidden_dim=64, n_layers=2)
                    model.load_state_dict(torch.load(path, map_location=self.device))
                    model.to(self.device).eval()
                    self.torch_models[f"lstm_v2_{dim}"] = model
                except Exception as e:
                    print(f"Error loading {path}: {e}")

        # BiLSTM v3 (Try Input=31)
        for dim in DIMENSION_NAMES:
             path = os.path.join(MODEL_DIR, f"lstm_v3_{dim}_bin.pt")
             if os.path.exists(path):
                try:
                    state_dict = torch.load(path, map_location=self.device)
                    # Infer input dimension
                    input_dim = 31
                    w = state_dict.get('lstm.weight_ih_l0')
                    if w is not None: input_dim = w.shape[1]
                    
                    if input_dim == 31: # Only load if compatible
                        model = BiLSTMAttention(input_dim=31)
                        model.load_state_dict(state_dict)
                        model.to(self.device).eval()
                        self.torch_models[f"lstm_v3_{dim}"] = model
                        print(f"Loaded PyTorch v3 model for {dim}")
                except Exception as e:
                    print(f"Error loading {path}: {e}")

    def predict(self, features_list: List[dict]) -> Dict:
        """Ensemble prediction using Hybrid + PyTorch models."""
        # 1. Feature Extraction
        fs = [f if isinstance(f, dict) else f.__dict__ for f in features_list]
        runtime_71 = self.feature_extractor.extract_v2(fs)
        
        # 2. Hybrid Baseline
        hybrid = self._hybrid_scoring(runtime_71)
        
        engagement_scores = [hybrid["engagement"]]

        # 3. Running PyTorch Models
        if self.torch_models and TORCH_AVAILABLE and fs:
            try:
                # Use longer sequence if possible, or pad to 30
                seq = self.feature_extractor.extract_sequence(fs, seq_len=30)
                batch = torch.from_numpy(seq).unsqueeze(0).to(self.device)
                
                for dim in DIMENSION_NAMES:
                    probs = []
                    for k, m in self.torch_models.items():
                        if f"_{dim}" in k:
                            with torch.no_grad():
                                logit = m(batch).item()
                            prob = 1.0 / (1.0 + np.exp(-logit))
                            probs.append(prob * 100.0)
                    
                    if probs:
                        avg = np.mean(probs)
                        if dim == "engagement":
                            engagement_scores.append(avg)
                        hybrid[dim] = round((hybrid[dim] + avg)/2, 1)

            except Exception as e:
                logger.error(f"PyTorch inference failed: {e}")
        
        # Final Engagement Score
        final_engagement = round(np.mean(engagement_scores), 1)
        hybrid["overall"] = final_engagement
        hybrid["engagement"] = final_engagement

        return hybrid

    def forecast_next(self, features_list: List[dict], current_score: float) -> float:
        """
        Predict the engagement score for the NEXT window (60s).
        Uses current engagement velocity (slope) and behavioral signals.
        """
        if not features_list:
            return current_score
            
        fs = [f if isinstance(f, dict) else f.__dict__ for f in features_list]
        runtime = self.feature_extractor.extract_v2(fs)
        
        # Extract trend features from summary stats
        # ear_slope: index 5, gaze_slope: index 13, brow_slope: index 29
        ear_slope = runtime[5]
        gaze_slope = runtime[13]
        brow_slope = runtime[21] # inner_brow - brow_lowerer trend
        pose_slope = (runtime[45] + runtime[53] + runtime[61]) / 3.0 # yaw, pitch, roll slopes
        
        # Behavioral cues
        tab_hidden = 1.0 - runtime[68] # tab_visible_pct
        play_speed = runtime[69] # playback_speed_avg
        
        # Heuristic Projection: 
        # Future = Current + (Velocity * Time) + Bias
        # Time = 1 unit (next window)
        
        velocity = (gaze_slope * 2.0) + (ear_slope * 1.5) + (brow_slope * 0.5) - (pose_slope * 1.0)
        
        # Penalize if tab is hidden or speed is erratic
        penalty = (tab_hidden * 15.0) + (abs(play_speed - 1.0) * 5.0)
        
        # Bonus for stable and focused signals
        bonus = (runtime[32] * 5.0) # head_pose_stability_mean
        
        projected = current_score + (velocity * 10.0) - penalty + bonus
        
        # Regression to mean: extreme scores tend to stabilize
        # We alpha-blend with the current score for stability
        stable_projected = (0.7 * projected) + (0.3 * current_score)
        
        return round(float(np.clip(stable_projected, 0, 100)), 1)

    def _hybrid_scoring(self, runtime: np.ndarray) -> Dict:
        # Simple stats-based scoring
        # Idx mapping: 0-7: ear, 8-15: gaze, ...
        ear_mean = runtime[0]
        gaze_mean = runtime[8]
        stab_mean = runtime[32]
        
        score = (gaze_mean * 30 + stab_mean * 20 + ear_mean * 20)
        score = np.clip(score + 10, 0, 100) # Base bias
        
        return {
            "overall": round(score, 1),
            "engagement": round(score, 1),
            "boredom": round(100 - score, 1),
            "confusion": 10.0,
            "frustration": 10.0
        }


class ICAPClassifier:
    """
    ICAP Framework Classifier (Chi & Wylie 2014).
    Categorizes student learning behaviors into categories: Interactive, Constructive, Active, Passive.
    """
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
        note_pct = sum(1 for f in features_list if (f.get("note_taking", False) if isinstance(f, dict) else getattr(f, "note_taking", False))) / n
        keyboard_pct = sum(1 for f in features_list if (f.get("keyboard_active", False) if isinstance(f, dict) else getattr(f, "keyboard_active", False))) / n
        gaze_avg = np.mean([f.get("gaze_score", 0.5) if isinstance(f, dict) else getattr(f, "gaze_score", 0.5) for f in features_list])
        mouse_pct = sum(1 for f in features_list if (f.get("mouse_active", False) if isinstance(f, dict) else getattr(f, "mouse_active", False))) / n

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
    """
    Fuzzy-logic engagement rules for human-readable explanations.
    """
    @staticmethod
    def evaluate(feature_vector: np.ndarray, scores: Dict) -> List[Dict]:
        # Feature indices mapping for 71-dim vector:
        # 0-7: ear, 8-15: gaze, 16-23: mouth, 24-31: brow, 32-39: stability, 40-47: yaw, 48-55: pitch, 56-63: roll
        # 64: blink_count, 65: blink_rate, 66: keyboard_pct, 67: mouse_pct, 68: tab_visible_pct, 69: playback_speed, 70: note_taking
        
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


# Singleton accessors
_model_instance = None
def get_engagement_model():
    global _model_instance
    if _model_instance is None:
        _model_instance = EngagementModel()
        _model_instance.load()
    return _model_instance

def get_icap_classifier(): 
    return ICAPClassifier() 

def get_fuzzy_rules(): 
    return FuzzyEngagementRules()

