"""
SmartLMS - Live Camera Engagement Model Tester
===========================================
Runs the engagement models locally against a live webcam feed.

This version avoids the broken MediaPipe solutions package and uses
OpenCV-only face detection so the tester can still run locally.
"""

import cv2
import csv
import importlib.util
import json
import joblib
import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "app" / "ml" / "trained_models"
DEBUG_DIR = Path(__file__).parent / "debug_logs" / "live_test"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_ROOT = Path(__file__).parent.parent

EXPORT_DIR_CANDIDATES = [
    PROJECT_ROOT / "smartlms-frontend" / "export",
    Path(__file__).parent / "export",
]

DIMENSIONS = ["boredom", "engagement", "confusion", "frustration"]
OPTIMAL_THRESHOLDS = {
    "boredom": 0.62,
    "engagement": 0.30,
    "confusion": 0.48,
    "frustration": 0.36,
}

RUNTIME_SIGNAL_NAMES = ["ear", "gaze", "mouth", "brow", "stability", "yaw", "pitch", "roll"]
STAT_SUFFIXES = ["mean", "std", "min", "max", "range", "slope", "p10", "p90"]

RUNTIME_FEATURE_NAMES: List[str] = []
for sig in RUNTIME_SIGNAL_NAMES:
    for stat in STAT_SUFFIXES:
        RUNTIME_FEATURE_NAMES.append(f"{sig}_{stat}")
RUNTIME_FEATURE_NAMES.extend(["blink_count", "blink_rate"])
RUNTIME_FEATURE_NAMES.extend([
    "keyboard_pct", "mouse_pct", "tab_visible_pct",
    "playback_speed_avg", "note_taking_pct",
])
NUM_RUNTIME_FEATURES = len(RUNTIME_FEATURE_NAMES)


class FacialFeatureExtractor:
    """Extract lightweight heuristic facial features using OpenCV only."""

    def __init__(self):
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            raise RuntimeError(f"Failed to load face cascade: {cascade_path}")
        logger.info("OpenCV face detector initialized")

    def extract_features(self, frame: np.ndarray) -> Tuple[Dict[str, Any], Optional[Tuple[int, int, int, int]]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]

        features: Dict[str, Any] = {
            "eye_aspect_ratio_left": 0.25,
            "eye_aspect_ratio_right": 0.25,
            "gaze_score": 0.5,
            "gaze_angle_x": 0.0,
            "gaze_angle_y": 0.0,
            "mouth_openness": 0.0,
            "au01_inner_brow_raise": 0.0,
            "au04_brow_lowerer": 0.0,
            "au25_lips_part": 0.0,
            "au26_jaw_drop": 0.0,
            "head_pose_yaw": 0.0,
            "head_pose_pitch": 0.0,
            "head_pose_roll": 0.0,
            "head_pose_stability": 0.5,
            "keyboard_active": False,
            "mouse_active": False,
            "tab_visible": True,
            "playback_speed": 1.0,
            "note_taking": False,
            "face_detected": False,
        }

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(80, 80),
        )

        face_box = None
        if len(faces) > 0:
            x, y, fw, fh = max(faces, key=lambda box: box[2] * box[3])
            face_box = (int(x), int(y), int(fw), int(fh))
            features["face_detected"] = True

            cv2.rectangle(frame, (x, y), (x + fw, y + fh), (0, 255, 0), 2)
            cv2.putText(
                frame,
                "Face detected",
                (x, max(20, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )

            center_x = x + fw / 2.0
            center_y = y + fh / 2.0
            offset_x = (center_x / max(w, 1)) - 0.5
            offset_y = (center_y / max(h, 1)) - 0.5
            area_ratio = (fw * fh) / float(max(w * h, 1))

            features["gaze_score"] = float(np.clip(1.0 - abs(offset_x) * 2.0, 0.0, 1.0))
            features["gaze_angle_x"] = float(offset_x * 45.0)
            features["gaze_angle_y"] = float(offset_y * 35.0)
            features["head_pose_yaw"] = float(np.clip(offset_x * 50.0, -45.0, 45.0))
            features["head_pose_pitch"] = float(np.clip(offset_y * 40.0, -45.0, 45.0))
            features["head_pose_roll"] = float(np.clip((fw - fh) / max(fh, 1) * 10.0, -20.0, 20.0))
            features["head_pose_stability"] = float(np.clip(1.0 - min(abs(offset_x) + abs(offset_y), 1.0), 0.0, 1.0))

            features["mouth_openness"] = float(np.clip((fh / max(fw, 1)) - 0.85, 0.0, 1.0))
            features["au25_lips_part"] = float(np.clip(features["mouth_openness"] * 1.2, 0.0, 1.0))
            features["au26_jaw_drop"] = float(np.clip(area_ratio * 8.0, 0.0, 1.0))
            features["au01_inner_brow_raise"] = float(np.clip(1.0 - area_ratio * 5.0, 0.0, 1.0))
            features["au04_brow_lowerer"] = float(np.clip(abs(offset_x) * 1.5, 0.0, 1.0))
            features["eye_aspect_ratio_left"] = float(np.clip(0.18 + (1.0 - area_ratio * 6.0) * 0.1, 0.05, 0.4))
            features["eye_aspect_ratio_right"] = float(np.clip(0.18 + (1.0 - area_ratio * 6.0) * 0.1, 0.05, 0.4))

        return features, face_box


class FeatureStatisticsCalculator:
    @staticmethod
    def signal_stats(values: List[float]) -> List[float]:
        if not values:
            return [0.0] * 8
        arr = np.array(values, dtype=np.float32)
        n = len(arr)
        return [
            float(np.mean(arr)),
            float(np.std(arr)),
            float(np.min(arr)),
            float(np.max(arr)),
            float(np.max(arr) - np.min(arr)),
            float(np.polyfit(np.arange(n), arr, 1)[0]) if n > 1 and np.std(arr) > 1e-8 else 0.0,
            float(np.percentile(arr, 10)),
            float(np.percentile(arr, 90)),
        ]

    @staticmethod
    def extract_summary_features(features_list: List[Dict[str, Any]]) -> np.ndarray:
        if not features_list:
            return np.zeros(NUM_RUNTIME_FEATURES, dtype=np.float32)

        def get_val(f: Dict[str, Any], key: str, default: float = 0.0):
            return f.get(key, default) if isinstance(f, dict) else getattr(f, key, default)

        ear_vals, gaze_vals, mouth_vals = [], [], []
        brow_vals, stability_vals = [], []
        yaw_vals, pitch_vals, roll_vals = [], [], []

        for f in features_list:
            el = float(get_val(f, "eye_aspect_ratio_left", 0.25) or 0.25)
            er = float(get_val(f, "eye_aspect_ratio_right", 0.25) or 0.25)
            ear_vals.append((el + er) / 2.0)
            gaze_vals.append(float(get_val(f, "gaze_score", 0.5) or 0.5))
            mouth_vals.append(float(get_val(f, "mouth_openness", 0.0) or get_val(f, "au25_lips_part", 0.0) or 0.0))
            brow_vals.append(float(get_val(f, "au01_inner_brow_raise", 0.0) or 0.0) - float(get_val(f, "au04_brow_lowerer", 0.0) or 0.0))
            stability_vals.append(float(get_val(f, "head_pose_stability", 0.5) or 0.5))
            yaw_vals.append(abs(float(get_val(f, "head_pose_yaw", 0.0) or 0.0)))
            pitch_vals.append(abs(float(get_val(f, "head_pose_pitch", 0.0) or 0.0)))
            roll_vals.append(abs(float(get_val(f, "head_pose_roll", 0.0) or 0.0)))

        feats: List[float] = []
        for vals in [ear_vals, gaze_vals, mouth_vals, brow_vals, stability_vals, yaw_vals, pitch_vals, roll_vals]:
            feats.extend(FeatureStatisticsCalculator.signal_stats(vals))

        if len(ear_vals) > 2:
            ear_arr = np.array(ear_vals)
            blinks = int(np.sum(np.diff((ear_arr < 0.2).astype(int)) > 0))
            rate = blinks / max(len(features_list) / 30.0, 0.1) * 60.0
            feats.extend([float(blinks), float(rate)])
        else:
            feats.extend([0.0, 0.0])

        n = len(features_list)
        feats.append(sum(1 for f in features_list if get_val(f, "keyboard_active", False)) / n)
        feats.append(sum(1 for f in features_list if get_val(f, "mouse_active", False)) / n)
        feats.append(sum(1 for f in features_list if get_val(f, "tab_visible", True)) / n)
        feats.append(float(np.mean([float(get_val(f, "playback_speed", 1.0) or 1.0) for f in features_list])))
        feats.append(sum(1 for f in features_list if get_val(f, "note_taking", False)) / n)

        return np.array(feats, dtype=np.float32)

    @staticmethod
    def extract_sequence31(features_list: List[Dict[str, Any]], seq_len: int = 30) -> np.ndarray:
        """Build 31-dim sequence expected by exported Keras models."""
        if not features_list:
            return np.zeros((seq_len, 31), dtype=np.float32)

        frames = features_list[-seq_len:] if len(features_list) > seq_len else features_list
        sequence: List[List[float]] = []

        for f in frames:
            row: List[float] = []

            # 17 AU-like channels
            row.append(float(f.get("au01_inner_brow_raise", 0.0)))  # au01
            row.extend([0.0])  # au02
            row.append(float(f.get("au04_brow_lowerer", 0.0)))  # au04
            row.extend([0.0, 0.0, 0.0, 0.0, 0.0])  # au05,06,07,09,10
            row.extend([0.0, 0.0, 0.0, 0.0, 0.0])  # au12,14,15,17,20
            row.extend([0.0])  # au23
            row.append(float(f.get("au25_lips_part", f.get("mouth_openness", 0.0))))  # au25
            row.append(float(f.get("au26_jaw_drop", 0.0)))  # au26
            row.append(0.0)  # au45

            # 8 gaze channels (6 placeholders + 2 angles)
            row.extend([0.0] * 6)
            row.append(float(f.get("gaze_angle_x", 0.0)))
            row.append(float(f.get("gaze_angle_y", 0.0)))

            # 6 pose channels (Tx,Ty,Tz,Rx,Ry,Rz)
            row.extend([0.0, 0.0, 0.0])
            row.append(float(f.get("head_pose_pitch", 0.0)))
            row.append(float(f.get("head_pose_yaw", 0.0)))
            row.append(float(f.get("head_pose_roll", 0.0)))

            sequence.append(row)

        if len(sequence) < seq_len:
            pad = [[0.0] * 31 for _ in range(seq_len - len(sequence))]
            sequence = pad + sequence

        return np.array(sequence, dtype=np.float32)

    @staticmethod
    def extract_sequence49(features_list: List[Dict[str, Any]], seq_len: int = 30) -> np.ndarray:
        """Build 49-dim sequence expected by trained PyTorch BiLSTM models."""
        if not features_list:
            return np.zeros((seq_len, 49), dtype=np.float32)

        frames = features_list[-seq_len:] if len(features_list) > seq_len else features_list
        sequence: List[List[float]] = []

        for f in frames:
            row: List[float] = []

            # 17 AU regression-like channels
            row.append(float(f.get("au01_inner_brow_raise", 0.0)))
            row.extend([0.0])  # au02
            row.append(float(f.get("au04_brow_lowerer", 0.0)))
            row.extend([0.0, 0.0, 0.0, 0.0, 0.0])  # au05,06,07,09,10
            row.extend([0.0, 0.0, 0.0, 0.0, 0.0])  # au12,14,15,17,20
            row.extend([0.0])  # au23
            row.append(float(f.get("au25_lips_part", f.get("mouth_openness", 0.0))))
            row.append(float(f.get("au26_jaw_drop", 0.0)))
            row.append(0.0)  # au45

            # 8 gaze channels
            row.extend([0.0] * 6)
            row.append(float(f.get("gaze_angle_x", 0.0)))
            row.append(float(f.get("gaze_angle_y", 0.0)))

            # 6 pose channels
            row.extend([0.0, 0.0, 0.0])  # pose Tx,Ty,Tz unavailable in live pipeline
            row.append(float(f.get("head_pose_pitch", 0.0)))
            row.append(float(f.get("head_pose_yaw", 0.0)))
            row.append(float(f.get("head_pose_roll", 0.0)))

            # 18 binary AU-style channels derived from regression-like channels
            au_regs = row[:16]
            au_class = [1.0 if x > 0.5 else 0.0 for x in au_regs]
            au_class.append(0.0)  # AU28 placeholder
            au_class.append(1.0 if row[16] > 0.5 else 0.0)  # AU45 class
            row.extend(au_class)

            sequence.append(row)

        if len(sequence) < seq_len:
            pad = [[0.0] * 49 for _ in range(seq_len - len(sequence))]
            sequence = pad + sequence

        return np.array(sequence, dtype=np.float32)


class ModelManager:
    def __init__(self):
        self.xgb_models: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.model_feature_dims: Dict[str, int] = {}
        self.scaler_feature_dims: Dict[str, int] = {}
        self.keras_models: Dict[str, Any] = {}
        self.keras_predict = None
        self.keras_model_paths: Dict[str, Path] = {}
        self.lstm_models: Dict[str, Any] = {}
        self.model_history: Dict[str, deque] = {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        self.load_models()

    def _init_model_history(self, name: str):
        if name not in self.model_history:
            self.model_history[name] = deque(maxlen=40)

    def _update_model_history(self, name: str, preds: Dict[str, float]):
        self._init_model_history(name)
        self.model_history[name].append([float(preds.get(dim, 0.5)) for dim in DIMENSIONS])

    def _is_model_healthy(self, name: str, preds: Dict[str, float]) -> bool:
        values = [float(preds.get(dim, 0.5)) for dim in DIMENSIONS]
        if any((not np.isfinite(v)) or v < 0.0 or v > 1.0 for v in values):
            return False

        # If all dimensions collapse to nearly same value repeatedly, mark unhealthy.
        sep = float(np.mean([abs(values[i] - values[j]) for i in range(4) for j in range(i + 1, 4)]))
        self._update_model_history(name, preds)
        history = np.array(self.model_history.get(name, []), dtype=np.float32)

        if history.shape[0] >= 8:
            hist_std = float(np.mean(np.std(history, axis=0)))
            if hist_std < 1e-4:
                return False

        if sep < 1e-5 and history.shape[0] >= 6:
            return False

        return True

    def _load_lstm_models(self):
        try:
            from app.ml.pytorch_definitions import BiLSTMAttention  # type: ignore
        except Exception as exc:
            logger.warning(f"PyTorch model definitions unavailable: {exc}")
            return

        for dim in DIMENSIONS:
            p = MODEL_DIR / f"lstm_v3_{dim}_bin.pt"
            if not p.exists():
                continue
            try:
                state = torch.load(str(p), map_location=self.device)
                w = state.get("lstm.weight_ih_l0")
                if w is None:
                    logger.warning(f"Missing LSTM input weights in {p.name}")
                    continue
                input_dim = int(w.shape[1])
                hidden = int(w.shape[0] // 4)
                layer_keys = [k for k in state.keys() if k.startswith("lstm.weight_ih_l")]
                layers = max(1, len(layer_keys) // 2)

                # Infer classifier head width from checkpoint to match training architecture.
                head1 = state.get("head.0.weight")
                head2 = state.get("head.3.weight")
                out1 = int(head1.shape[0]) if isinstance(head1, torch.Tensor) and head1.ndim == 2 else 128
                out2 = int(head2.shape[0]) if isinstance(head2, torch.Tensor) and head2.ndim == 2 else 64

                model = BiLSTMAttention(input_dim=input_dim, hidden=hidden, layers=layers, dropout=0.4)
                model.head = nn.Sequential(
                    nn.Linear(hidden * 2, out1), nn.GELU(), nn.Dropout(0.4),
                    nn.Linear(out1, out2), nn.GELU(), nn.Dropout(0.3),
                    nn.Linear(out2, 1),
                )
                model.load_state_dict(state, strict=False)
                model.to(self.device)
                model.eval()
                self.lstm_models[dim] = model
                logger.info(
                    f"Loaded PyTorch LSTM v3 {dim} "
                    f"(input_dim={input_dim}, hidden={hidden}, layers={layers}, head={out1}->{out2})"
                )
            except Exception as exc:
                logger.warning(f"Failed loading LSTM v3 {dim}: {exc}")

    def _load_export_keras_loader(self):
        model_loader_path = Path(__file__).parent / "export" / "model_loader.py"
        if not model_loader_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location("smartlms_export_model_loader", str(model_loader_path))
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.warning(f"Failed loading export model loader: {exc}")
            return None

    def _resolve_export_dir(self) -> Optional[Path]:
        for candidate in EXPORT_DIR_CANDIDATES:
            if candidate.exists():
                return candidate
        return None

    def load_models(self):
        logger.info(f"Loading models from: {MODEL_DIR}")
        for dim in DIMENSIONS:
            xgb_path = MODEL_DIR / f"xgb_v3_{dim}_bin.joblib"
            scaler_path = MODEL_DIR / f"scaler_v3_{dim}_bin.joblib"
            if xgb_path.exists() and scaler_path.exists():
                try:
                    self.xgb_models[dim] = joblib.load(str(xgb_path))
                    scaler = joblib.load(str(scaler_path))
                    self.scalers[f"xgb_{dim}"] = scaler
                    self.model_feature_dims[dim] = int(getattr(self.xgb_models[dim], "n_features_in_", NUM_RUNTIME_FEATURES))
                    self.scaler_feature_dims[dim] = int(getattr(scaler, "n_features_in_", NUM_RUNTIME_FEATURES))
                    logger.info(f"Loaded XGBoost v3 {dim}")
                except Exception as exc:
                    logger.warning(f"Failed loading XGBoost {dim}: {exc}")
            else:
                logger.warning(f"Missing XGBoost files for {dim}")

        self._load_lstm_models()

        # Load exported Keras models from export folders.
        export_dir = self._resolve_export_dir()
        loader_module = self._load_export_keras_loader()
        if export_dir is not None and loader_module is not None:
            self.keras_predict = getattr(loader_module, "predict", None)
            load_fn = getattr(loader_module, "load_model_with_custom_layers", None)
            if load_fn is None:
                load_fn = getattr(loader_module, "load_model", None)

            keras_specs = {
                "baseline_h5": export_dir / "Baseline_LSTM_74.2%_BIASED" / "best_model.h5",
                "bilstm_h5": export_dir / "BiLSTM_Enhanced_FMAE_58.6%" / "best_model.h5",
                "fusion_h5": export_dir / "Fusion_Enhanced_57.4%" / "best_model.h5",
                "transformer_vit_h5": export_dir / "Transformer_ViT_59.6%_BEST" / "best_model.h5",
            }

            for name, path in keras_specs.items():
                if not path.exists() or load_fn is None:
                    continue
                try:
                    self.keras_models[name] = load_fn(str(path), compile=False)
                    self.keras_model_paths[name] = path
                    logger.info(f"Loaded export model: {name}")
                except Exception as exc:
                    logger.warning(f"Failed loading export model {name}: {exc}")

        logger.info(
            f"Model Summary: XGBoost={len(self.xgb_models)}, LSTM={len(self.lstm_models)}, ExportH5={len(self.keras_models)}"
        )

    def _fit_sequence(self, seq: np.ndarray, seq_len: int, feat_dim: int) -> np.ndarray:
        seq = np.array(seq, dtype=np.float32)
        if seq.ndim != 2:
            seq = np.zeros((seq_len, feat_dim), dtype=np.float32)

        if seq.shape[0] > seq_len:
            seq = seq[-seq_len:]
        elif seq.shape[0] < seq_len:
            pad = np.zeros((seq_len - seq.shape[0], seq.shape[1]), dtype=np.float32)
            seq = np.vstack([pad, seq])

        if seq.shape[1] > feat_dim:
            seq = seq[:, :feat_dim]
        elif seq.shape[1] < feat_dim:
            pad = np.zeros((seq.shape[0], feat_dim - seq.shape[1]), dtype=np.float32)
            seq = np.hstack([seq, pad])

        return seq

    def _build_export_input(
        self,
        model: Any,
        seq31: np.ndarray,
        seq_vit: Optional[np.ndarray],
    ) -> np.ndarray:
        input_shape = getattr(model, "input_shape", None)
        if not input_shape or not isinstance(input_shape, tuple) or len(input_shape) < 3:
            return seq31.reshape(1, seq31.shape[0], seq31.shape[1]).astype(np.float32)

        seq_len = int(input_shape[1] or 30)
        feat_dim = int(input_shape[2] or 31)

        if feat_dim == 768 and seq_vit is not None:
            fitted = self._fit_sequence(seq_vit, seq_len, 768)
            return fitted.reshape(1, seq_len, 768).astype(np.float32)

        if feat_dim == 256:
            if seq_vit is not None:
                fitted = self._fit_sequence(seq_vit, seq_len, 256)
            else:
                fitted31 = self._fit_sequence(seq31, seq_len, 31)
                repeat_count = int(np.ceil(256 / 31.0))
                tiled = np.tile(fitted31, (1, repeat_count))
                fitted = tiled[:, :256]
            return fitted.reshape(1, seq_len, 256).astype(np.float32)

        fitted31 = self._fit_sequence(seq31, seq_len, feat_dim)
        return fitted31.reshape(1, seq_len, feat_dim).astype(np.float32)

    def _preds_to_probs(self, preds: Any) -> Dict[str, float]:
        model_probs = {dim: 0.5 for dim in DIMENSIONS}

        if isinstance(preds, list) and len(preds) >= 4:
            for i, dim in enumerate(DIMENSIONS):
                arr = np.array(preds[i], dtype=np.float32).reshape(-1)
                if arr.size == 0:
                    continue
                if arr.size > 1:
                    probs = np.clip(arr, 0.0, 1.0)
                    denom = float(np.sum(probs))
                    if denom > 0:
                        probs = probs / denom
                    expected_class = float(np.sum(np.arange(len(probs), dtype=np.float32) * probs))
                    model_probs[dim] = float(np.clip(expected_class / max(len(probs) - 1, 1), 0.0, 1.0))
                else:
                    model_probs[dim] = float(np.clip(arr[0], 0.0, 1.0))
            return model_probs

        arr = np.array(preds, dtype=np.float32)
        if arr.ndim >= 2 and arr.shape[-1] == 4:
            probs = np.clip(arr.reshape(-1, 4)[0], 0.0, 1.0)
            denom = float(np.sum(probs))
            if denom > 0:
                probs = probs / denom
            expected_class = float(np.sum(np.arange(4, dtype=np.float32) * probs))
            shared = float(np.clip(expected_class / 3.0, 0.0, 1.0))
            for dim in DIMENSIONS:
                model_probs[dim] = shared

        return model_probs

    def predict_xgboost(self, features: np.ndarray) -> Dict[str, float]:
        results: Dict[str, float] = {}
        for dim in DIMENSIONS:
            model = self.xgb_models.get(dim)
            scaler = self.scalers.get(f"xgb_{dim}")
            if model is None:
                results[dim] = 0.5
                continue
            try:
                model_dim = self.model_feature_dims.get(dim, features.shape[-1])
                if features.shape[-1] < model_dim:
                    padded = np.zeros(model_dim, dtype=np.float32)
                    padded[: features.shape[-1]] = features
                    features_to_use = padded
                else:
                    features_to_use = features[:model_dim]

                X = features_to_use.reshape(1, -1)
                scaler_dim = self.scaler_feature_dims.get(dim)
                if scaler is not None and scaler_dim == model_dim:
                    X = scaler.transform(X)
                pred = model.predict_proba(X)[0]
                results[dim] = float(pred[1]) if len(pred) > 1 else 0.5
            except Exception as exc:
                logger.warning(f"XGBoost prediction error for {dim}: {exc}")
                results[dim] = 0.5
        return results

    def predict_lstm(self, seq49: Optional[np.ndarray]) -> Dict[str, float]:
        if not self.lstm_models or seq49 is None:
            return {dim: 0.5 for dim in DIMENSIONS}

        results: Dict[str, float] = {}
        try:
            x = torch.tensor(seq49, dtype=torch.float32, device=self.device).unsqueeze(0)
            for dim in DIMENSIONS:
                model = self.lstm_models.get(dim)
                if model is None:
                    results[dim] = 0.5
                    continue
                with torch.no_grad():
                    y = model(x)
                    prob = float(torch.sigmoid(y).detach().cpu().reshape(-1)[0].item())
                    results[dim] = float(np.clip(prob, 0.0, 1.0))
        except Exception as exc:
            logger.warning(f"LSTM inference failed: {exc}")
            return {dim: 0.5 for dim in DIMENSIONS}

        return results

    def predict_export_h5(self, seq31: np.ndarray, seq_vit: Optional[np.ndarray] = None) -> Dict[str, Dict[str, float]]:
        results: Dict[str, Dict[str, float]] = {}
        if not self.keras_models:
            return results

        for model_name, model in self.keras_models.items():
            try:
                model_input = self._build_export_input(model, seq31, seq_vit)
                preds = model.predict(model_input, verbose=0)
                results[model_name] = self._preds_to_probs(preds)
            except Exception as exc:
                logger.warning(f"Export model inference failed for {model_name}: {exc}")
                results[model_name] = {dim: 0.5 for dim in DIMENSIONS}

        return results

    def predict_ensemble(
        self,
        features: np.ndarray,
        seq49: Optional[np.ndarray] = None,
        seq31: Optional[np.ndarray] = None,
        seq_vit: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, float]]:
        xgb_pred = self.predict_xgboost(features)
        lstm_pred = self.predict_lstm(seq49)
        export_preds = self.predict_export_h5(seq31, seq_vit=seq_vit) if seq31 is not None else {}

        source_map: Dict[str, Dict[str, float]] = {
            "xgboost": xgb_pred,
            "lstm": lstm_pred,
            **export_preds,
        }
        healthy_map: Dict[str, bool] = {name: self._is_model_healthy(name, pred) for name, pred in source_map.items()}
        sources: List[Dict[str, float]] = [pred for name, pred in source_map.items() if healthy_map.get(name, True)]
        if not sources:
            sources = [xgb_pred]

        ensemble: Dict[str, float] = {}
        for dim in DIMENSIONS:
            vals = [src.get(dim, 0.5) for src in sources]
            ensemble[dim] = float(np.mean(vals)) if vals else 0.5

        payload: Dict[str, Dict[str, float]] = {
            "xgboost": xgb_pred,
            "lstm": lstm_pred,
            "ensemble": ensemble,
        }
        payload.update(export_preds)
        payload["model_health"] = {name: float(1.0 if ok else 0.0) for name, ok in healthy_map.items()}  # type: ignore[index]
        return payload


class LiveEngagementTester:
    def __init__(self):
        self.feature_extractor = FacialFeatureExtractor()
        self.model_manager = ModelManager()
        self.stat_calculator = FeatureStatisticsCalculator()
        self.frame_features_history = deque(maxlen=300)
        self.vit_embedding_history = deque(maxlen=300)
        self.running = True
        self.paused = False
        self.show_models = {
            "xgboost": True,
            "lstm": True,
            "baseline_h5": True,
            "bilstm_h5": True,
            "fusion_h5": True,
            "transformer_vit_h5": True,
        }
        self.frame_count = 0
        self.fps = 0.0
        self.last_time = datetime.now()
        self.window_name = "SmartLMS - Engagement Model Tester"
        self.capture_width = 640
        self.capture_height = 360
        self.vit_extractor = self._init_vit_extractor()
        self.csv_log_path = DEBUG_DIR / f"model_outputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv_logger()

    def _init_vit_extractor(self):
        # Use the same extractor class as backend runtime when available.
        try:
            from app.ml.extract_face_embeddings import ViTEmbeddingExtractor  # type: ignore

            device = "cuda" if torch.cuda.is_available() else "cpu"
            if os.getenv("SMARTLMS_VIT_DEVICE"):
                device = os.getenv("SMARTLMS_VIT_DEVICE", device)
            extractor = ViTEmbeddingExtractor(device=device)
            logger.info(f"ViT live extractor enabled on {device}")
            return extractor
        except Exception as exc:
            logger.warning(f"ViT extractor unavailable, continuing without ViT embeddings: {exc}")
            return None

    def _extract_vit_embedding(self, frame: np.ndarray, face_box: Optional[Tuple[int, int, int, int]]) -> Optional[np.ndarray]:
        if self.vit_extractor is None or face_box is None:
            return None
        try:
            x, y, fw, fh = face_box
            h, w = frame.shape[:2]
            margin = int(max(fw, fh) * 0.15)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(w, x + fw + margin)
            y2 = min(h, y + fh + margin)
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size == 0:
                return None
            emb = self.vit_extractor.extract_batch([face_crop])
            if emb is None or len(emb) == 0:
                return None
            return np.array(emb[0], dtype=np.float32)
        except Exception as exc:
            logger.warning(f"ViT embedding extraction failed: {exc}")
            return None

    def _build_vit_sequence(self, seq_len: int = 30, feat_dim: int = 768) -> Optional[np.ndarray]:
        if not self.vit_embedding_history:
            return None
        rows = list(self.vit_embedding_history)[-seq_len:]
        arr = np.array(rows, dtype=np.float32)
        if arr.ndim != 2:
            return None
        if arr.shape[1] > feat_dim:
            arr = arr[:, :feat_dim]
        elif arr.shape[1] < feat_dim:
            pad = np.zeros((arr.shape[0], feat_dim - arr.shape[1]), dtype=np.float32)
            arr = np.hstack([arr, pad])
        if arr.shape[0] < seq_len:
            pad = np.zeros((seq_len - arr.shape[0], feat_dim), dtype=np.float32)
            arr = np.vstack([pad, arr])
        return arr

    def _init_csv_logger(self):
        headers = [
            "timestamp",
            "frame_count",
            "face_detected",
            "xgb_boredom",
            "xgb_engagement",
            "xgb_confusion",
            "xgb_frustration",
            "lstm_boredom",
            "lstm_engagement",
            "lstm_confusion",
            "lstm_frustration",
            "baseline_h5_boredom",
            "baseline_h5_engagement",
            "baseline_h5_confusion",
            "baseline_h5_frustration",
            "bilstm_h5_boredom",
            "bilstm_h5_engagement",
            "bilstm_h5_confusion",
            "bilstm_h5_frustration",
            "fusion_h5_boredom",
            "fusion_h5_engagement",
            "fusion_h5_confusion",
            "fusion_h5_frustration",
            "transformer_vit_h5_boredom",
            "transformer_vit_h5_engagement",
            "transformer_vit_h5_confusion",
            "transformer_vit_h5_frustration",
            "ensemble_boredom",
            "ensemble_engagement",
            "ensemble_confusion",
            "ensemble_frustration",
        ]
        with open(self.csv_log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        logger.info(f"CSV logging enabled: {self.csv_log_path}")

    def _append_csv_row(self, features: Dict[str, Any], predictions: Dict[str, Dict[str, float]]):
        row = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "frame_count": self.frame_count,
            "face_detected": int(bool(features.get("face_detected", False))),
            "xgb_boredom": predictions.get("xgboost", {}).get("boredom", 0.5),
            "xgb_engagement": predictions.get("xgboost", {}).get("engagement", 0.5),
            "xgb_confusion": predictions.get("xgboost", {}).get("confusion", 0.5),
            "xgb_frustration": predictions.get("xgboost", {}).get("frustration", 0.5),
            "lstm_boredom": predictions.get("lstm", {}).get("boredom", 0.5),
            "lstm_engagement": predictions.get("lstm", {}).get("engagement", 0.5),
            "lstm_confusion": predictions.get("lstm", {}).get("confusion", 0.5),
            "lstm_frustration": predictions.get("lstm", {}).get("frustration", 0.5),
            "baseline_h5_boredom": predictions.get("baseline_h5", {}).get("boredom", 0.5),
            "baseline_h5_engagement": predictions.get("baseline_h5", {}).get("engagement", 0.5),
            "baseline_h5_confusion": predictions.get("baseline_h5", {}).get("confusion", 0.5),
            "baseline_h5_frustration": predictions.get("baseline_h5", {}).get("frustration", 0.5),
            "bilstm_h5_boredom": predictions.get("bilstm_h5", {}).get("boredom", 0.5),
            "bilstm_h5_engagement": predictions.get("bilstm_h5", {}).get("engagement", 0.5),
            "bilstm_h5_confusion": predictions.get("bilstm_h5", {}).get("confusion", 0.5),
            "bilstm_h5_frustration": predictions.get("bilstm_h5", {}).get("frustration", 0.5),
            "fusion_h5_boredom": predictions.get("fusion_h5", {}).get("boredom", 0.5),
            "fusion_h5_engagement": predictions.get("fusion_h5", {}).get("engagement", 0.5),
            "fusion_h5_confusion": predictions.get("fusion_h5", {}).get("confusion", 0.5),
            "fusion_h5_frustration": predictions.get("fusion_h5", {}).get("frustration", 0.5),
            "transformer_vit_h5_boredom": predictions.get("transformer_vit_h5", {}).get("boredom", 0.5),
            "transformer_vit_h5_engagement": predictions.get("transformer_vit_h5", {}).get("engagement", 0.5),
            "transformer_vit_h5_confusion": predictions.get("transformer_vit_h5", {}).get("confusion", 0.5),
            "transformer_vit_h5_frustration": predictions.get("transformer_vit_h5", {}).get("frustration", 0.5),
            "ensemble_boredom": predictions.get("ensemble", {}).get("boredom", 0.5),
            "ensemble_engagement": predictions.get("ensemble", {}).get("engagement", 0.5),
            "ensemble_confusion": predictions.get("ensemble", {}).get("confusion", 0.5),
            "ensemble_frustration": predictions.get("ensemble", {}).get("frustration", 0.5),
        }
        with open(self.csv_log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writerow(row)

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Failed to open camera!")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.capture_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.capture_height)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, self.capture_width, self.capture_height)
        logger.info("Camera opened. Press 'h' for help, 'q' to quit.")

        latest_predictions = None
        latest_features: Dict[str, Any] = {}

        while self.running:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to read frame!")
                break

            frame = cv2.flip(frame, 1)

            if not self.paused:
                latest_features, face_box = self.feature_extractor.extract_features(frame)
                self.frame_features_history.append(latest_features)
                vit_emb = self._extract_vit_embedding(frame, face_box)
                if vit_emb is not None:
                    self.vit_embedding_history.append(vit_emb)
                self.frame_count += 1

                if self.frame_count % 30 == 0 and len(self.frame_features_history) >= 1:
                    summary_features = self.stat_calculator.extract_summary_features(list(self.frame_features_history))
                    seq49 = self.stat_calculator.extract_sequence49(list(self.frame_features_history), seq_len=30)
                    seq31 = self.stat_calculator.extract_sequence31(list(self.frame_features_history), seq_len=30)
                    seq_vit = self._build_vit_sequence(seq_len=30, feat_dim=768)
                    latest_predictions = self.model_manager.predict_ensemble(
                        summary_features,
                        seq49=seq49,
                        seq31=seq31,
                        seq_vit=seq_vit,
                    )
                    self._append_csv_row(latest_features, latest_predictions)

            if latest_predictions is not None:
                self._render_predictions(frame, latest_features, latest_predictions)

            self._draw_ui(frame)
            cv2.imshow(self.window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if not self._handle_key(key):
                break

        cap.release()
        cv2.destroyAllWindows()

    def _render_predictions(self, frame: np.ndarray, features: Dict[str, Any], predictions: Dict[str, Dict[str, float]]):
        h, w = frame.shape[:2]
        face_status = "✓ Face Detected" if features.get("face_detected") else "✗ No Face"
        color = (0, 255, 0) if features.get("face_detected") else (0, 0, 255)
        cv2.putText(frame, face_status, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

        y_offset = 80
        cv2.putText(frame, "Raw Features:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 25
        feature_lines = [
            ("EAR", (features.get("eye_aspect_ratio_left", 0.25) + features.get("eye_aspect_ratio_right", 0.25)) / 2.0),
            ("Mouth", float(features.get("mouth_openness", 0.0))),
            ("Yaw", float(features.get("head_pose_yaw", 0.0))),
            ("Pitch", float(features.get("head_pose_pitch", 0.0))),
            ("Gaze", float(features.get("gaze_score", 0.5))),
        ]
        for name, value in feature_lines:
            cv2.putText(frame, f"{name}: {value:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            y_offset += 20

        y_offset += 10
        cv2.putText(frame, "Model Predictions:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        y_offset += 25
        for dim in DIMENSIONS:
            threshold = OPTIMAL_THRESHOLDS[dim]
            xgb_prob = predictions.get("xgboost", {}).get(dim, 0.5)
            ens_prob = predictions.get("ensemble", {}).get(dim, 0.5)
            xgb_color = (0, 255, 0) if xgb_prob > threshold else (255, 0, 0)
            ens_color = (0, 255, 0) if ens_prob > threshold else (255, 0, 0)
            if self.show_models["xgboost"]:
                cv2.putText(frame, f"XGB-{dim[:3].upper()}: {xgb_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, xgb_color, 1)
                y_offset += 20
            if self.show_models["lstm"]:
                lstm_prob = predictions.get("lstm", {}).get(dim, 0.5)
                cv2.putText(frame, f"LSTM-{dim[:3].upper()}: {lstm_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                y_offset += 20
            if self.show_models["baseline_h5"]:
                base_prob = predictions.get("baseline_h5", {}).get(dim, 0.5)
                cv2.putText(frame, f"BASE-{dim[:3].upper()}: {base_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 220, 220), 1)
                y_offset += 20
            if self.show_models["bilstm_h5"]:
                bi_prob = predictions.get("bilstm_h5", {}).get(dim, 0.5)
                cv2.putText(frame, f"BIH5-{dim[:3].upper()}: {bi_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 180, 120), 1)
                y_offset += 20
            if self.show_models["fusion_h5"]:
                fus_prob = predictions.get("fusion_h5", {}).get(dim, 0.5)
                cv2.putText(frame, f"FUS-{dim[:3].upper()}: {fus_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 140, 220), 1)
                y_offset += 20
            if self.show_models["transformer_vit_h5"]:
                tr_prob = predictions.get("transformer_vit_h5", {}).get(dim, 0.5)
                cv2.putText(frame, f"VIT-{dim[:3].upper()}: {tr_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (140, 220, 140), 1)
                y_offset += 20
            cv2.putText(frame, f"ENS-{dim[:3].upper()}: {ens_prob:.3f}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ens_color, 1)
            y_offset += 20

        now = datetime.now()
        dt = (now - self.last_time).total_seconds()
        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)
            self.last_time = now
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (w - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    def _draw_ui(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        status_text = "PAUSED" if self.paused else "RECORDING"
        color = (0, 0, 255) if self.paused else (0, 255, 0)
        cv2.rectangle(frame, (0, 0), (w, 50), (20, 20, 20), -1)
        cv2.putText(frame, status_text, (w - 150, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

        help_texts = [
            "q/ESC: Quit | p: Pause | r: Reset | s: Save | h: Help",
            "1:XGB 2:LSTM 3:BASE 4:BIH5 5:FUS 6:VIT",
        ]
        for i, text in enumerate(help_texts):
            cv2.putText(frame, text, (10, h - 50 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 0), 1)

    def _handle_key(self, key: int) -> bool:
        if key == ord("q") or key == 27:
            logger.info("Quitting...")
            return False
        if key == ord("p"):
            self.paused = not self.paused
            logger.info(f"Paused: {self.paused}")
        elif key == ord("r"):
            self.frame_features_history.clear()
            logger.info("Feature history reset")
        elif key == ord("s"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_file = DEBUG_DIR / f"debug_{timestamp}.json"
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump({"timestamp": timestamp, "frame_count": self.frame_count, "history_size": len(self.frame_features_history)}, f, indent=2)
            logger.info(f"Saved debug info to {debug_file}")
        elif key == ord("1"):
            self.show_models["xgboost"] = not self.show_models["xgboost"]
            logger.info(f"XGBoost display: {self.show_models['xgboost']}")
        elif key == ord("2"):
            self.show_models["lstm"] = not self.show_models["lstm"]
            logger.info(f"LSTM display: {self.show_models['lstm']}")
        elif key == ord("3"):
            self.show_models["baseline_h5"] = not self.show_models["baseline_h5"]
            logger.info(f"Baseline H5 display: {self.show_models['baseline_h5']}")
        elif key == ord("4"):
            self.show_models["bilstm_h5"] = not self.show_models["bilstm_h5"]
            logger.info(f"BiLSTM H5 display: {self.show_models['bilstm_h5']}")
        elif key == ord("5"):
            self.show_models["fusion_h5"] = not self.show_models["fusion_h5"]
            logger.info(f"Fusion H5 display: {self.show_models['fusion_h5']}")
        elif key == ord("6"):
            self.show_models["transformer_vit_h5"] = not self.show_models["transformer_vit_h5"]
            logger.info(f"Transformer ViT H5 display: {self.show_models['transformer_vit_h5']}")
        elif key == ord("h"):
            self._print_help()
        return True

    def _print_help(self):
        logger.info(
            """
SmartLMS Live Tester Controls
q / ESC  Quit
p        Pause/Resume
r        Reset feature history
s        Save debug info
h        Show help
1        Toggle XGBoost display
2        Toggle LSTM display
3        Toggle Baseline H5 display
4        Toggle BiLSTM H5 display
5        Toggle Fusion H5 display
6        Toggle Transformer ViT H5 display
"""
        )


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("SmartLMS - Live Engagement Model Tester")
    logger.info("=" * 70)
    try:
        tester = LiveEngagementTester()
        tester.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
    finally:
        logger.info("Cleanup complete")
