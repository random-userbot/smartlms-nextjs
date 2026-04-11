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
import boto3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import importlib.util
import json
import os

import numpy as np
import onnxruntime as ort

# TF/Keras removed for Ultra-Lean Production
tf = None
keras = None

from app.config import settings
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
        self._s3_client = None

    @property
    def s3(self):
        if self._s3_client is None:
            self._s3_client = boto3.client('s3', region_name=settings.AWS_REGION)
        return self._s3_client

    def _sync_model_from_s3(self, folder_name: str) -> bool:
        """Download model folder from S3 if it doesn't exist locally"""
        bucket = settings.AWS_S3_MODEL_BUCKET
        if not bucket:
            print(f"[S3] AWS_S3_MODEL_BUCKET not set. Skipping S3 check for {folder_name}.", flush=True)
            return False

        prefix = settings.MODEL_S3_PREFIX
        s3_path = f"{prefix}{folder_name}/"
        local_path = self.export_dir / folder_name
        
        try:
            print(f"[S3] Checking S3 for model: {s3_path}", flush=True)
            response = self.s3.list_objects_v2(Bucket=bucket, Prefix=s3_path)
            
            if 'Contents' not in response:
                print(f"[S3] Model folder {s3_path} not found in bucket {bucket}", flush=True)
                return False

            if not local_path.exists():
                local_path.mkdir(parents=True, exist_ok=True)

            print(f"[S3] Downloading files for {folder_name}...", flush=True)
            for obj in response['Contents']:
                file_key = obj['Key']
                if file_key.endswith('/'): continue # Skip folders
                
                relative_file_path = file_key.replace(s3_path, "")
                dest_path = local_path / relative_file_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                print(f"  -> Downloading {relative_file_path}", flush=True)
                self.s3.download_file(bucket, file_key, str(dest_path))
            
            print(f"[S3] Successfully downloaded {folder_name} to {local_path}", flush=True)
            return True
        except Exception as e:
            print(f"[S3] Error downloading model {folder_name}: {e}", flush=True)
            return False

    def _sync_catalog_from_s3(self) -> List[str]:
        """List folders in S3 to discover models not yet downloaded."""
        bucket = settings.AWS_S3_MODEL_BUCKET
        if not bucket:
            return []

        prefix = settings.MODEL_S3_PREFIX
        try:
            print(f"[S3] Discovering models in bucket: {bucket}/{prefix}", flush=True)
            response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
            
            model_folders = []
            if 'CommonPrefixes' in response:
                for cp in response['CommonPrefixes']:
                    folder = cp['Prefix'].replace(prefix, "").strip("/")
                    if folder:
                        model_folders.append(folder)
            
            print(f"[S3] Found {len(model_folders)} models in S3.", flush=True)
            return model_folders
        except Exception as e:
            print(f"[S3] Error listing catalog: {e}", flush=True)
            return []

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
        # TensorFlow is no longer used at runtime in the lean image
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
        model_folders = []
        if self.export_dir.exists():
            model_folders = [f.name for f in self.export_dir.iterdir() if f.is_dir()]

        # S3 Discovery fallback
        s3_models = self._sync_catalog_from_s3()
        all_unique_folders = sorted(list(set(model_folders + s3_models)))

        loader = self._load_model_loader()
        can_load_keras = True # Assumption for ONNX

        models: List[RuntimeModelInfo] = []
        for name in all_unique_folders:
            folder = self.export_dir / name
            model_file = folder / "model.onnx"
            status = "available" if (model_file.exists() and can_load_keras) else "available_in_s3"
            
            # If locally missing, we use a placeholder source until downloaded
            source = str(model_file) if model_file.exists() else f"s3://{settings.AWS_S3_MODEL_BUCKET}/{settings.MODEL_S3_PREFIX}{name}"

            model_id = f"export::{name}"
            notes = "Exported Keras model"
            recommended = "BEST" in name.upper() or "ENHANCED" in name.upper()

            if "FAILED" in name.upper():
                notes = "Marked failed during export"
                status = "error"
            if "BIASED" in name.upper():
                notes = "Marked biased in export notes"

            metadata = self._load_export_metadata(folder) if folder.exists() else {}
            if metadata.get("status") == "error":
                status = "error"

            models.append(
                RuntimeModelInfo(
                    model_id=model_id,
                    name=name,
                    family="export_onnx",
                    status=status,
                    source=source,
                    recommended=recommended and "FAILED" not in name.upper(),
                    notes=notes,
                    accuracy_hint=self._parse_accuracy_hint(name),
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
        # Handle symbolic names like 'unk__1192' by defaulting to 1 for non-fixed dims
        def _to_int(dim, default=1):
            if dim is None or isinstance(dim, str):
                return default
            try:
                return int(dim)
            except (ValueError, TypeError):
                return default

        shape = [_to_int(d, default=1) for d in list(input_shape)]
        
        # Batch dimension must be 1 for our current worker setup
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
            feat_dim = shape[1] if shape[1] > 1 else len(FEATURE_NAMES)
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
            seq_len = shape[1] if shape[1] > 1 else max(len(seq_vectors), 1)
            feat_dim = shape[2] if shape[2] > 1 else len(FEATURE_NAMES)

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
            d = dim if dim > 1 else max(len(features), 1)
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

        if not model_id or not model_id.startswith("export::"):
            print(f"[MEMORY] Skipping model load for non-export ID: {model_id}", flush=True)
            return None

        # Check Nightly Sleep Window (2 AM - 7 AM IST / UTC+5:30)
        if self.is_in_sleep_window():
            print("[MEMORY] Nightly Sleep window active (2-7 AM IST). Skipping model load.", flush=True)
            return None

        loader = self._load_model_loader()
        # model_loader is legacy; ONNX models don't require it, so we only log if missing
        if not loader:
            print("[BOOT] Warning: model_loader.py not found. Proceeding with native ONNX inference.", flush=True)

        # Aggressive memory management for free-tier hosting (Render/Railway/etc.)
        # Default to -1 (Unlimited) for AWS t3.large as requested by user
        try:
            DEFAULT_MAX_MODELS = int(os.getenv("MAX_LOADED_MODELS", "-1"))
        except ValueError:
            DEFAULT_MAX_MODELS = -1
        
        # Simple LRU: if full (and limit > 0), clear oldest 
        if DEFAULT_MAX_MODELS > 0 and len(self._loaded_models) >= DEFAULT_MAX_MODELS:
            print(f"[MEMORY] Cache limit ({DEFAULT_MAX_MODELS}) reached. Clearing sessions...", flush=True)
            self._loaded_models.clear()
            import gc
            gc.collect()

        folder_name = model_id.split("::", 1)[1]
        model_file = self.export_dir / folder_name / "model.onnx"
        
        # S3 Lazy Download: if file is missing, try to sync from S3
        if not model_file.exists():
            print(f"[S3] Model {folder_name} (.onnx) missing locally. Attempting S3 sync...", flush=True)
            if not self._sync_model_from_s3(folder_name):
                # Try fallback to .h5 if it's there (unlikely in lean image but good for dev)
                model_file = self.export_dir / folder_name / "best_model.h5"
                if not model_file.exists():
                    raise FileNotFoundError(f"Model file not found locally and S3 sync failed: {model_file}")

        try:
            print(f"[MEMORY] Loading ONNX session for {folder_name}...", flush=True)
            if str(model_file).endswith(".onnx"):
                session = ort.InferenceSession(str(model_file), providers=['CPUExecutionProvider'])
                self._loaded_models[model_id] = session
                return session
            else:
                raise RuntimeError("Keras (.h5) fallback is disabled in production. Use ONNX models.")
        except Exception as e:
            print(f"[MEMORY] FAILED to load model {folder_name}: {e}", flush=True)
            import gc
            gc.collect()
            raise RuntimeError(f"Failed to load model session: {e}")

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
                "overall": round(overall, 1),
                "engagement": round(dims.get("engagement", {}).get("confidence", 0.0) * 100.0, 1),
                "boredom": round(dims.get("boredom", {}).get("confidence", 0.0) * 100.0, 1),
                "confusion": round(dims.get("confusion", {}).get("confidence", 0.0) * 100.0, 1),
                "frustration": round(dims.get("frustration", {}).get("confidence", 0.0) * 100.0, 1),
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
            # Fallback if in sleep window, load failed, or invalid ID
            return {
                "model_id": model_id, 
                "error": "Model unavailable or invalid ID",
                "fallback": True,
                "output": {"overall": 50.0, "engagement": 50.0, "status": "fallback"}
            }

        if isinstance(model, ort.InferenceSession):
            input_name = model.get_inputs()[0].name
            input_shape = model.get_inputs()[0].shape
            x = self._build_input_for_shape(features, tuple(input_shape))
            preds = model.run(None, {input_name: x})
            # ONNX returns a list of outputs, Keras expected a tensor
            parsed = self._parse_predictions(preds)
        else:
            # Keras Fallback
            input_shape = tuple(getattr(model, "input_shape", ()) or ())
            x = self._build_input_for_shape(features, input_shape)
            preds = model.predict(x, verbose=0)
            parsed = self._parse_predictions(preds)

        return {
            "model_id": model_id,
            "family": "export_onnx",
            "input_shape": list(input_shape),
            "resolved_input_shape": list(x.shape),
            "output": parsed,
        }


@lru_cache(maxsize=1)
def get_export_model_registry() -> ExportModelRegistry:
    return ExportModelRegistry()
