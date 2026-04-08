import cv2
import time
import csv
import json
import os
import numpy as np
import torch
import mediapipe as mp
import mediapipe.python.solutions.face_mesh as mp_face_mesh
import mediapipe.python.solutions.drawing_utils as mp_drawing
from pathlib import Path
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from transformers import ViTImageProcessor, ViTModel

# Enable TensorFlow/Torch optimizations
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Import backend ML modules
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.ml.engagement_model import get_engagement_model
    from export.model_loader import load_model_with_custom_layers, predict as keras_predict
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────
# FEATURE EXTRACTION CLASSES
# ─────────────────────────────────────────────────────────────────────────

class MediaPipeExtractor:
    """Extract high-fidelity face landmarks and gaze using MediaPipe."""
    def __init__(self):
        self.mp_face_mesh = mp_face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def extract_features(self, frame: np.ndarray) -> Tuple[Dict[str, Any], Optional[Tuple[int, int, int, int]], Optional[np.ndarray]]:
        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb_frame)
        
        features = {
            "gaze_angle_x": 0.0, "gaze_angle_y": 0.0,
            "head_pose_yaw": 0.0, "head_pose_pitch": 0.0, "head_pose_roll": 0.0,
            "face_detected": False, "eye_aspect_ratio": 0.25
        }
        face_box = None
        face_crop = None

        if results.multi_face_landmarks:
            features["face_detected"] = True
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Simple gaze approximation from iris landmarks
            # Left Iris (468-472), Right Iris (473-477)
            lx = landmarks[468].x
            ly = landmarks[468].y
            features["gaze_angle_x"] = (lx - 0.5) * 45.0
            features["gaze_angle_y"] = (ly - 0.5) * 35.0
            
            # Basic head pose from nose-tip (1) and chin (199)
            nose = landmarks[1]
            chin = landmarks[199]
            features["head_pose_pitch"] = (nose.y - chin.y + 0.1) * 100.0
            features["head_pose_yaw"] = (nose.x - 0.5) * 50.0

            # EAR approximation
            # Left eye top/bottom: 159, 145
            ear = abs(landmarks[159].y - landmarks[145].y) * 10.0
            features["eye_aspect_ratio"] = float(ear)

            # Get BBox for crop
            x_coords = [l.x for l in landmarks]
            y_coords = [l.y for l in landmarks]
            x1, y1 = int(min(x_coords) * w), int(min(y_coords) * h)
            x2, y2 = int(max(x_coords) * w), int(max(y_coords) * h)
            
            # Padding
            pad = int((x2 - x1) * 0.1)
            x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
            x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
            
            face_box = (x1, y1, x2 - x1, y2 - y1)
            face_crop = frame[y1:y2, x1:x2]

        return features, face_box, face_crop

class ViTEmbedder:
    """Extract 768-D ViT embeddings."""
    def __init__(self, model_name="google/vit-base-patch16-224"):
        print(f"Loading ViT Embedder on {DEVICE}...")
        self.processor = ViTImageProcessor.from_pretrained(model_name)
        self.model = ViTModel.from_pretrained(model_name).to(DEVICE)
        self.model.eval()

    def get_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        if face_crop is None: return np.zeros(768, dtype=np.float32)
        with torch.no_grad():
            rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            inputs = self.processor(images=rgb, return_tensors="pt").to(DEVICE)
            outputs = self.model(**inputs)
            # CLS token
            return outputs.last_hidden_state[0, 0, :].cpu().numpy()

class FMAEEmbedder:
    """Extract 256-D FMAE embeddings."""
    def __init__(self, model_path):
        print(f"Loading FMAE Embedder from {model_path}...")
        try:
            from tensorflow.keras.models import load_model
            self.model = load_model(model_path, compile=False)
        except Exception as e:
            print(f"Warning: FMAE load failed ({e}). Using random proxy for dimension matching.")
            self.model = None

    def get_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        if self.model is None or face_crop is None:
            return np.zeros(256, dtype=np.float32)
        try:
            # FMAE expected 224x224x3 (RGB) normalized to [0,1]
            img = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (224, 224))
            img = np.expand_dims(img, axis=0) / 255.0
            pred = self.model.predict(img, verbose=0)
            return pred[0] if isinstance(pred, np.ndarray) else pred[0].numpy()
        except Exception as e:
            # logger.warning(f"FMAE predict failed: {e}")
            return np.zeros(256, dtype=np.float32)

class FeatureStatisticsCalculator:
    @staticmethod
    def extract_sequence_raw(features_list: List[Dict[str, Any]], seq_len: int = 30) -> np.ndarray:
        """Map 31-D raw features for models."""
        rows = []
        for f in features_list[-seq_len:]:
            row = [0.0] * 31
            row[23] = f.get("gaze_angle_x", 0.0)
            row[24] = f.get("gaze_angle_y", 0.0)
            row[28] = f.get("head_pose_pitch", 0.0)
            row[29] = f.get("head_pose_yaw", 0.0)
            row[30] = f.get("head_pose_roll", 0.0)
            rows.append(row)
        while len(rows) < seq_len: rows.insert(0, [0.0]*31)
        return np.array(rows, dtype=np.float32)

# ─────────────────────────────────────────────────────────────────────────

EXPORT_DIR = Path("./export")
MODEL_PATHS = {
    "baseline": EXPORT_DIR / "Baseline_LSTM_74.2%_BIASED" / "best_model.h5",
    "bilstm": EXPORT_DIR / "BiLSTM_Enhanced_FMAE_58.6%" / "best_model.h5",
    "fusion": EXPORT_DIR / "Fusion_Enhanced_57.4%" / "best_model.h5",
    "transformer": EXPORT_DIR / "Transformer_ViT_59.6%_BEST" / "best_model.h5",
}
FMAE_PATH = r"C:\Users\revan\Downloads\DAiSEE\lstm_training\pipeline3\fmae_pretrained\fmae_encoder.h5"
CSV_OUTPUT = "engagement_test_results.csv"

class LiveEngagementTester:
    def __init__(self):
        print("Initializing High-Fidelity (MediaPipe) Engagement Test...")
        self.face_extractor = MediaPipeExtractor()
        self.vit_embedder = ViTEmbedder()
        self.fmae_embedder = FMAEEmbedder(FMAE_PATH)
        self.xgb_model = get_engagement_model()
        
        self.keras_models = {}
        for name, path in MODEL_PATHS.items():
            if path.exists():
                print(f"Loading {name} model...")
                self.keras_models[name] = load_model_with_custom_layers(str(path))

        self.feature_history = deque(maxlen=300)
        self.vit_history = deque(maxlen=30)
        self.fmae_history = deque(maxlen=30)
        
        # Forecasting Buffer: (timestamp_of_forecast, forecasted_value)
        self.forecast_buffer = deque() 
        
        headers = ["timestamp", "elapsed_sec", "actual_ensemble", "face_detected"]
        # Add granular XGB dimensions
        headers.extend(["xgb_engagement", "xgb_boredom", "xgb_confusion", "xgb_frustration"])
        for name in ["baseline", "bilstm", "fusion", "transformer"]:
            headers.append(f"score_{name}")
        headers.extend(["forecast_60s", "actual_at_forecast", "forecast_error"])
        
        with open(CSV_OUTPUT, 'w', newline='') as f:
            csv.writer(f).writerow(headers)

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open camera.")
            return

        print("\n" + "="*50)
        print("LIVE ENGAGEMENT TEST: MULTI-ARCH COMPARISON")
        print(f"Running on {DEVICE} | Saving to {CSV_OUTPUT}")
        print("="*50 + "\n")

        start_time = time.time()
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret: break
            frame_idx += 1
            elapsed = time.time() - start_time

            # 1. Feature Extraction
            features, face_box, face_crop = self.face_extractor.extract_features(frame)
            self.feature_history.append(features)
            
            # Extract heavy embeddings only every few frames for speed
            if frame_idx % 30 == 0:
                vit_vec = self.vit_embedder.get_embedding(face_crop)
                fmae_vec = self.fmae_embedder.get_embedding(face_crop)
                self.vit_history.append(vit_vec)
                self.fmae_history.append(fmae_vec)

                # Prep current sequence
                hist_list = list(self.feature_history)[-30:]
                raw_seq = FeatureStatisticsCalculator.extract_sequence_raw(hist_list)
                
                # Convert deque to array and pad to exactly 30 frames
                def get_padded_seq(dq, dim):
                    seq = np.array(list(dq))
                    if len(seq) == 0:
                        return np.zeros((30, dim), dtype=np.float32)
                    if len(seq) < 30:
                        pad = np.zeros((30 - len(seq), dim), dtype=np.float32)
                        return np.vstack([pad, seq])
                    return seq[-30:]

                vit_seq = get_padded_seq(self.vit_history, 768)
                fmae_seq = get_padded_seq(self.fmae_history, 256)

                feat_dict = {'raw': raw_seq, 'vit': vit_seq, 'fmae': fmae_seq}

                # 2. Predicted Scores
                xgb_res = self.xgb_model.predict(hist_list)
                actual_score = xgb_res.get("overall", 0.0)

                keras_scores = {}
                for name, model in self.keras_models.items():
                    try:
                        res = keras_predict(model, feat_dict)
                        # Fix: check for None instead of falsy 0.0
                        if res is not None:
                            keras_scores[name] = res.get("overall_proxy", 0.0)
                        else:
                            keras_scores[name] = 0.0
                    except Exception as e:
                        print(f"Prediction error for {name}: {e}")
                        keras_scores[name] = 0.0

                # 3. Forecasting Logic (60s Window)
                current_time = time.time()
                next_forecast = self.xgb_model.forecast_next(hist_list, actual_score)
                self.forecast_buffer.append((current_time + 60.0, next_forecast))

                # Check if any previous forecast is due for verification
                forecast_score_due = 0.0
                actual_at_forecast = 0.0
                forecast_error = 0.0

                if self.forecast_buffer and current_time >= self.forecast_buffer[0][0]:
                    due_time, forecast_score_due = self.forecast_buffer.popleft()
                    actual_at_forecast = actual_score
                    forecast_error = abs(actual_at_forecast - forecast_score_due)
                    print(f"--- FORECAST VERIFIED: Pred(60s ago)={round(forecast_score_due, 1)} | Actual={round(actual_score, 1)} | Err={round(forecast_error, 1)} ---")

                # 4. Logging
                row = [
                    datetime.now().strftime("%H:%M:%S"), 
                    round(elapsed, 2), 
                    round(actual_score, 2), 
                    features["face_detected"],
                    round(xgb_res.get("engagement", 0.0), 2),
                    round(xgb_res.get("boredom", 0.0), 2),
                    round(xgb_res.get("confusion", 0.0), 2),
                    round(xgb_res.get("frustration", 0.0), 2)
                ]
                for name in ["baseline", "bilstm", "fusion", "transformer"]:
                    score = keras_scores.get(name, 0.0)
                    row.append(round(score, 2))
                
                # Forecasting columns
                row.extend([
                    round(next_forecast, 2),
                    round(actual_at_forecast, 2) if actual_at_forecast > 0 else "",
                    round(forecast_error, 2) if actual_at_forecast > 0 else ""
                ])
                
                with open(CSV_OUTPUT, 'a', newline='') as f:
                    csv.writer(f).writerow(row)

                status_line = (f"[{round(elapsed, 1)}s] Face: {features['face_detected']} | Ensemble: {round(actual_score, 1)} | "
                               f"ViT: {round(keras_scores.get('transformer',0), 1)} | BiLSTM: {round(keras_scores.get('bilstm',0), 1)} | "
                               f"Fusion: {round(keras_scores.get('fusion',0), 1)}")
                if forecast_error > 0:
                    status_line += f" | F-Err: {round(forecast_error, 1)}"
                print(status_line)

            # UI Update
            if face_box:
                x, y, w, h = face_box
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                cv2.putText(frame, "Analyzing Engagement...", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            cv2.imshow('SmartLMS Multi-Model Engagement Comparison', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        cap.release()
        cv2.destroyAllWindows()
        print(f"\nTest complete. Results: {CSV_OUTPUT}")

if __name__ == "__main__":
    tester = LiveEngagementTester()
    tester.run()
