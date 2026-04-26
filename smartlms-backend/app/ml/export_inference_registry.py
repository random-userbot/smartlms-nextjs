"""
Runtime registry for engagement models, including exported TensorFlow models.

Provides:
- Model catalog for UI selection.
- Real inference from captured MediaPipe/OpenFace-like features.
- Graceful fallback when TensorFlow/export models are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import importlib.util
import json
import os

import numpy as np
# TF/Keras removed for Ultra-Lean Production
tf = None
keras = None

from app.ml.engagement_model import FEATURE_NAMES, EngagementFeatureExtractor, get_engagement_model


DIMENSIONS = ["boredom", "engagement", "confusion", "frustration"]
CLASS_LABELS = ["Very Low", "Low", "High", "Very High"]


@dataclass
class RuntimeModelInfo:
    model_id: str
    name: str
    family: str
    status: str
    source: str
    recommended: bool
    notes: str
    input_shape: Optional[Tuple[Any, ...]] = None
    outputs: Optional[int] = None
    accuracy_hint: Optional[str] = None

# ---- Fallback Custom Layers ----
# In case `export/model_loader.py` fails to load
_FALLBACK_LAYERS = {}

# Fallback Keras layers removed (All models migrated to ONNX)
_FALLBACK_LAYERS = {}


def _make_serializable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    return obj

class ExportModelRegistry:
    def __init__(self):
        # Path is app/ml/export_inference_registry.py
        # parents[0]=ml, [1]=app, [2]=smartlms-backend
        self.root = Path(__file__).resolve().parents[2]
        workspace_root = self.root.parent
        export_candidates = [
            workspace_root / "smartlms-frontend" / "export",
            self.root / "export",
        ]
        self.export_dir = next((p for p in export_candidates if p.exists()), export_candidates[-1])
        self._model_loader = None
        self._keras = None
        self._loaded_models: Dict[str, Any] = {}
        self._catalog_cache: Optional[List[RuntimeModelInfo]] = None
        self.last_accessed: Optional[datetime] = None

    def _load_model_loader(self):
        if self._model_loader is not None:
            return self._model_loader

        loader_candidates = [
            self.export_dir / "model_loader.py",
            self.root / "export" / "model_loader.py",
        ]
        loader_path = next((p for p in loader_candidates if p.exists()), None)
        if loader_path is None:
            return None

        spec = importlib.util.spec_from_file_location("export_model_loader", str(loader_path))
        if not spec or not spec.loader:
            return None

        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._model_loader = module
            return module
        except Exception:
            return None

    def _load_tensorflow(self):
        if self._keras is not None:
            return self._keras
        try:
            from tensorflow import keras  # type: ignore

            self._keras = keras
            return keras
        except Exception:
            return None

    def _parse_accuracy_hint(self, folder_name: str) -> str:
        parts = folder_name.split("_")
        for p in parts:
            if p.endswith("%"):
                return p
        return "n/a"

    def _load_export_metadata(self, folder: Path) -> Dict[str, Any]:
        test_results = folder / "test_results.json"
        if test_results.exists():
            try:
                return json.loads(test_results.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _discover_export_models(self) -> List[RuntimeModelInfo]:
        if not self.export_dir.exists():
            return []

        loader = self._load_model_loader()
        keras = self._load_tensorflow()
        can_load_keras = bool(loader and keras)

        models: List[RuntimeModelInfo] = []
        for folder in sorted(self.export_dir.iterdir()):
            if not folder.is_dir():
                continue
            model_file = folder / "best_model.h5"
            if not model_file.exists():
                continue

            model_id = f"export::{folder.name}"
            status = "available" if can_load_keras else "requires_tensorflow"
            notes = "Exported Keras model"
            recommended = "BEST" in folder.name.upper() or "ENHANCED" in folder.name.upper()

            if "FAILED" in folder.name.upper():
                notes = "Marked failed during export"
                status = "error"
            if "BIASED" in folder.name.upper():
                notes = "Marked biased in export notes"

            metadata = self._load_export_metadata(folder)
            if metadata.get("status") == "error":
                status = "error"

            models.append(
                RuntimeModelInfo(
                    model_id=model_id,
                    name=folder.name,
                    family="export_keras",
                    status=status,
                    source=str(model_file),
                    recommended=recommended and "FAILED" not in folder.name.upper(),
                    notes=notes,
                    accuracy_hint=self._parse_accuracy_hint(folder.name),
                )
            )

        return models

    def list_models(self) -> List[Dict[str, Any]]:
        if self._catalog_cache is None:
            xgb_model = get_engagement_model()
            base = [
                RuntimeModelInfo(
                    model_id="builtin::xgboost",
                    name="Built-in XGBoost/Hybrid Runtime",
                    family="xgboost_hybrid",
                    status="available",
                    source="smartlms-backend/app/ml/engagement_model.py",
                    recommended=True,
                    notes="Production default used by engagement submit API",
                    accuracy_hint="runtime",
                )
            ]
            if not xgb_model.is_loaded:
                base[0].status = "rule_based_fallback"
                base[0].notes = "Model files missing, using rule-based fallback"

            self._catalog_cache = base + self._discover_export_models()

        return [
            {
                "model_id": m.model_id,
                "name": m.name,
                "family": m.family,
                "status": m.status,
                "source": m.source,
                "recommended": m.recommended,
                "notes": m.notes,
                "input_shape": list(m.input_shape) if m.input_shape else None,
                "outputs": m.outputs,
                "accuracy_hint": m.accuracy_hint,
            }
            for m in self._catalog_cache
        ]

    def _feature_to_legacy_vector(self, feature: Dict[str, Any]) -> np.ndarray:
        def pick(keys, default=0.0):
            for k in keys:
                v = feature.get(k, None)
                if v is not None:
                    return v
            return default

        ear_left = float(pick(["eye_aspect_ratio_left"], 0.0))
        ear_right = float(pick(["eye_aspect_ratio_right"], 0.0))
        eye_avg = (ear_left + ear_right) / 2.0

        gaze_score = feature.get("gaze_score", None)
        if gaze_score is None:
            gx = float(pick(["gaze_angle_x"], 0.0))
            gy = float(pick(["gaze_angle_y"], 0.0))
            gaze_score = max(0.0, 1.0 - (np.sqrt(gx * gx + gy * gy) / 30.0))

        vals = {
            "au01_inner_brow_raise": float(pick(["au01_inner_brow_raise", "AU01_r"], 0.0)),
            "au02_outer_brow_raise": float(pick(["au02_outer_brow_raise", "AU02_r"], 0.0)),
            "au04_brow_lowerer": float(pick(["au04_brow_lowerer", "AU04_r"], 0.0)),
            "au06_cheek_raiser": float(pick(["au06_cheek_raiser", "AU06_r"], 0.0)),
            "au12_lip_corner_puller": float(pick(["au12_lip_corner_puller", "AU12_r"], 0.0)),
            "au15_lip_corner_depressor": float(pick(["au15_lip_corner_depressor", "AU15_r"], 0.0)),
            "au25_lips_part": float(pick(["au25_lips_part", "AU25_r"], 0.0)),
            "au26_jaw_drop": float(pick(["au26_jaw_drop", "AU26_r"], 0.0)),
            "gaze_score": float(gaze_score),
            "head_pose_yaw": float(pick(["head_pose_yaw", "pose_Ry"], 0.0)),
            "head_pose_pitch": float(pick(["head_pose_pitch", "pose_Rx"], 0.0)),
            "head_pose_roll": float(pick(["head_pose_roll", "pose_Rz"], 0.0)),
            "head_pose_stability": float(feature.get("head_pose_stability", 0.0)),
            "eye_aspect_ratio": eye_avg,
            "blink_rate": float(pick(["blink_rate", "au45_blink", "AU45_r"], 0.0)),
            "mouth_openness": float(pick(["mouth_openness", "au25_lips_part", "AU25_r"], 0.0)),
            "keyboard_activity_pct": 1.0 if feature.get("keyboard_active", False) else 0.0,
            "mouse_activity_pct": 1.0 if feature.get("mouse_active", False) else 0.0,
            "tab_visible_pct": 1.0 if feature.get("tab_visible", True) else 0.0,
            "playback_speed_avg": float(feature.get("playback_speed", 1.0)),
            "note_taking_pct": 1.0 if feature.get("note_taking", False) else 0.0,
            "gaze_variance": 0.0,
            "head_stability_variance": 0.0,
            "blink_rate_variance": 0.0,
        }
        return np.array([vals.get(name, 0.0) for name in FEATURE_NAMES], dtype=np.float32)

    def _make_signal_pool(self, features: List[Dict[str, Any]]) -> np.ndarray:
        if not features:
            return np.zeros(128, dtype=np.float32)

        seq_vectors = [self._feature_to_legacy_vector(f) for f in features]
        seq_arr = np.vstack(seq_vectors)

        batch_vector = EngagementFeatureExtractor.extract_from_batch(features)
        runtime_vector = EngagementFeatureExtractor.extract_v2(features)

        flattened = np.concatenate(
            [
                seq_arr.flatten(),
                batch_vector,
                runtime_vector,
            ]
        )
        if flattened.size == 0:
            return np.zeros(128, dtype=np.float32)
        return flattened.astype(np.float32)

    def _tile_pool(self, pool: np.ndarray, size: int) -> np.ndarray:
        if size <= 0:
            return np.array([], dtype=np.float32)
        repeats = int(np.ceil(size / max(pool.size, 1)))
        tiled = np.tile(pool, repeats)
        return tiled[:size]

    def _build_input_for_shape(self, features: List[Dict[str, Any]], input_shape: Tuple[Any, ...]) -> np.ndarray:
        if not input_shape:
            raise ValueError("Model has unknown input shape")

        # Normalize shape like (None, 30, 768)
        shape = list(input_shape)
        if len(shape) == 0:
            raise ValueError("Invalid input shape")

        # batch dimension
        if shape[0] is None:
            shape[0] = 1
        if int(shape[0]) != 1:
            shape[0] = 1

        seq_vectors = [self._feature_to_legacy_vector(f) for f in features] or [np.zeros(len(FEATURE_NAMES), dtype=np.float32)]
        pool = self._make_signal_pool(features)

        visual_vectors: List[np.ndarray] = []
        for f in features:
            emb = f.get("visual_embedding") if isinstance(f, dict) else None
            if isinstance(emb, list) and emb:
                try:
                    visual_vectors.append(np.array(emb, dtype=np.float32).reshape(-1))
                except Exception:
                    continue

        if len(shape) == 2:
            feat_dim = int(shape[1] or len(FEATURE_NAMES))
            if visual_vectors and feat_dim >= 128:
                row = visual_vectors[-1]
                if row.size > feat_dim:
                    row = row[:feat_dim]
                elif row.size < feat_dim:
                    row = np.concatenate([row, np.zeros(feat_dim - row.size, dtype=np.float32)])
                return row.reshape(1, feat_dim).astype(np.float32)
            row = self._tile_pool(pool, feat_dim)
            return row.reshape(1, feat_dim).astype(np.float32)

        if len(shape) == 3:
            seq_len = int(shape[1] or max(len(seq_vectors), 1))
            feat_dim = int(shape[2] or len(FEATURE_NAMES))

            # Prefer real visual embeddings for high-dimensional model inputs.
            if visual_vectors and feat_dim in (256, 768):
                rows: List[np.ndarray] = []
                for idx in range(seq_len):
                    base = visual_vectors[min(idx, len(visual_vectors) - 1)]
                    if base.size > feat_dim:
                        row = base[:feat_dim]
                    elif base.size < feat_dim:
                        row = np.concatenate([base, np.zeros(feat_dim - base.size, dtype=np.float32)])
                    else:
                        row = base
                    rows.append(row.astype(np.float32))
                arr = np.stack(rows, axis=0)
                return arr.reshape(1, seq_len, feat_dim)

            rows: List[np.ndarray] = []
            for idx in range(seq_len):
                base = seq_vectors[min(idx, len(seq_vectors) - 1)]
                if feat_dim <= base.size:
                    row = base[:feat_dim]
                else:
                    extra = self._tile_pool(pool, feat_dim - base.size)
                    row = np.concatenate([base, extra])
                rows.append(row.astype(np.float32))

            arr = np.stack(rows, axis=0)
            return arr.reshape(1, seq_len, feat_dim)

        # Generic N-D fallback for future models
        flat_size = 1
        dynamic_shape = [1]
        for dim in shape[1:]:
            d = int(dim or max(len(features), 1))
            dynamic_shape.append(d)
            flat_size *= d

        values = self._tile_pool(pool, flat_size)
        return values.reshape(dynamic_shape).astype(np.float32)

    def _get_or_load_export_model(self, model_id: str):
        self.last_accessed = datetime.now(timezone.utc)
        
        if model_id in self._loaded_models:
            # Move to end (LRU)
            model = self._loaded_models.pop(model_id)
            self._loaded_models[model_id] = model
            return model

        if not model_id.startswith("export::"):
            raise ValueError("Not an export model id")

        # Check Nightly Sleep Window (2 AM - 7 AM IST / UTC+5:30

        loader = self._load_model_loader()
        keras = self._load_tensorflow()
        if not loader or not keras:
            raise RuntimeError("TensorFlow runtime is unavailable. Install tensorflow-cpu to use exported models.")

        # Aggressive memory management for free-tier hosting (Render/Railway/etc.)
        # Default to -1 (Unlimited) for AWS t3.large as requested by user
        try:
            DEFAULT_MAX_MODELS = int(os.getenv("MAX_LOADED_MODELS", "-1"))
        except ValueError:
            DEFAULT_MAX_MODELS = -1
        
        # Simple LRU: if full (and limit > 0), clear oldest 
        if DEFAULT_MAX_MODELS > 0 and len(self._loaded_models) >= DEFAULT_MAX_MODELS:
            print(f"[MEMORY] Cache limit ({DEFAULT_MAX_MODELS}) reached. Clearing loaded models...", flush=True)
            self._loaded_models.clear()
            keras.backend.clear_session()
            import gc
            gc.collect()

        folder_name = model_id.split("::", 1)[1]
        model_file = self.export_dir / folder_name / "best_model.h5"
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")

        try:
            print(f"[MEMORY] Loading model {folder_name}...", flush=True)
            model = loader.load_model_with_custom_layers(str(model_file), compile=False)
            self._loaded_models[model_id] = model
            return model
        except Exception as e:
            print(f"[MEMORY] FAILED to load model {folder_name}: {e}", flush=True)
            # Try to cleanup if load failed halfway
            keras.backend.clear_session()
            import gc
            gc.collect()
            raise RuntimeError(f"Failed to load model architecture: {e}")

    def is_in_sleep_window(self) -> bool:
        """Check if current time is in the 2 AM - 7 AM IST window"""
        # IST is UTC + 5:30
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        hour = now_ist.hour
        # User requested 2 AM to 7 AM sleep
        return 2 <= hour < 7

    def cleanup_if_idle(self, idle_minutes: int = 10):
        """Unload models if no signals received for X minutes to save AWS credits"""
        if not self._loaded_models:
            return
        
        if self.last_accessed is None:
            return

        now = datetime.now(timezone.utc)
        diff = (now - self.last_accessed).total_seconds() / 60.0
        
        if diff >= idle_minutes:
            print(f"[MEMORY] Neural Sleep: Domain idle for {int(diff)}m. Purging {len(self._loaded_models)} models...", flush=True)
            self._loaded_models.clear()
            keras = self._load_tensorflow()
            if keras:
                keras.backend.clear_session()
            import gc
            gc.collect()

    def preload_all_models(self):
        """Eagerly load all recommended models for continuous speed results"""
        if self.is_in_sleep_window():
            print("[BOOT] Skipping preload due to IST Nightly Sleep Window.", flush=True)
            return

        # Ensure registry is cataloged
        self.list_models()
        if not self._catalog_cache:
            return

        export_ids = [m.model_id for m in self._catalog_cache if m.model_id.startswith("export::") and m.recommended]
        
        print(f"[BOOT] Pre-loading {len(export_ids)} neural models for immediate sync...", flush=True)
        for mid in export_ids:
            try:
                self._get_or_load_export_model(mid)
            except Exception as e:
                print(f"[BOOT] Failed to preload {mid}: {e}", flush=True)

    def _parse_predictions(self, preds: Any) -> Dict[str, Any]:
        preds = _make_serializable(preds)
        
        if isinstance(preds, list):
            dims = {}
            raw = []
            for i, p in enumerate(preds[:4]):
                arr = np.array(p)
                probs = arr[0].tolist() if arr.ndim >= 2 else arr.tolist()
                class_idx = int(np.argmax(probs)) if len(probs) else 0
                dims[DIMENSIONS[i]] = {
                    "class_index": class_idx,
                    "label": CLASS_LABELS[class_idx] if class_idx < len(CLASS_LABELS) else str(class_idx),
                    "confidence": float(probs[class_idx]) if len(probs) > class_idx else 0.0,
                    "probabilities": [float(x) for x in probs],
                }
                raw.append([float(x) for x in probs])

            overall = 0.0
            if dims:
                overall = float(
                    np.mean([
                        dims.get("engagement", {}).get("confidence", 0.0),
                        1.0 - dims.get("boredom", {}).get("confidence", 0.0),
                        1.0 - dims.get("confusion", {}).get("confidence", 0.0),
                        1.0 - dims.get("frustration", {}).get("confidence", 0.0),
                    ])
                ) * 100.0

            return {
                "format": "multidim_class_probs",
                "dimensions": dims,
                "overall_proxy": round(overall, 1),
                "raw": raw,
            }

        arr = np.array(preds)
        flat = arr.flatten().tolist()
        return {
            "format": "generic_tensor",
            "shape": list(arr.shape),
            "values": [float(x) for x in flat[:64]],
            "truncated": len(flat) > 64,
        }

    def infer(self, model_id: str, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Track activity for Neural Sleep timer
        self.last_accessed = datetime.now(timezone.utc)

        if model_id == "builtin::xgboost":
            model = get_engagement_model()
            pred = model.predict(features)
            return {
                "model_id": model_id,
                "family": "xgboost_hybrid",
                "output": _make_serializable(pred),
            }

        model = self._get_or_load_export_model(model_id)
        if not model:
            # Fallback if in sleep window or load failed
            return {"model_id": model_id, "error": "Model sleep/unavailable", "fallback": True}

        input_shape = tuple(getattr(model, "input_shape", ()) or ())
        x = self._build_input_for_shape(features, input_shape)
        preds = model.predict(x, verbose=0)
        parsed = self._parse_predictions(preds)

        return {
            "model_id": model_id,
            "family": "export_keras",
            "input_shape": list(input_shape),
            "resolved_input_shape": list(x.shape),
            "output": parsed,
        }


@lru_cache(maxsize=1)
def get_export_model_registry() -> ExportModelRegistry:
    return ExportModelRegistry()
