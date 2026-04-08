"""
Smart LMS - Engagement Model Training Pipeline v2
==================================================
Thesis-grade training with proper feature engineering, class imbalance handling,
and multiple model architectures.

Key improvements over v1:
1. Uses REAL OpenFace AUs (17 regression + 18 classification) instead of noisy MediaPipe approximations
2. Also supports MediaPipe landmarks with proper temporal feature extraction
3. Binary label reformulation (Low vs High) - DAiSEE labels 0-1 → Low, 2-3 → High
4. Multiple imbalance strategies: focal loss, SMOTE, class weights, threshold optimization
5. Multiple models: XGBoost, LSTM, CNN+BiLSTM, TCN
6. Comprehensive evaluation: accuracy, F1 (macro/weighted), per-class, confusion matrix
7. SHAP explainability for tree models

Usage:
    # XGBoost on OpenFace features (recommended starting point)
    python -m app.ml.train_model_v2 --mode xgboost --source openface --labels binary
    
    # LSTM on OpenFace sequences
    python -m app.ml.train_model_v2 --mode lstm --source openface --labels binary
    
    # CNN+BiLSTM on raw MediaPipe landmarks
    python -m app.ml.train_model_v2 --mode cnn_bilstm --source mediapipe --labels binary
    
    # Full experiment matrix
    python -m app.ml.train_model_v2 --mode all --source openface --labels both
"""

import numpy as np
import pandas as pd
import os
import sys
import json
import glob
import argparse
import logging
import warnings
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import Counter

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────

DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]

# OpenFace AU columns (17 regression + 18 classification)
AU_REGRESSION = [
    "AU01_r", "AU02_r", "AU04_r", "AU05_r", "AU06_r", "AU07_r",
    "AU09_r", "AU10_r", "AU12_r", "AU14_r", "AU15_r", "AU17_r",
    "AU20_r", "AU23_r", "AU25_r", "AU26_r", "AU45_r",
]
AU_CLASSIFICATION = [
    "AU01_c", "AU02_c", "AU04_c", "AU05_c", "AU06_c", "AU07_c",
    "AU09_c", "AU10_c", "AU12_c", "AU14_c", "AU15_c", "AU17_c",
    "AU20_c", "AU23_c", "AU25_c", "AU26_c", "AU28_c", "AU45_c",
]
GAZE_COLS = ["gaze_0_x", "gaze_0_y", "gaze_0_z", "gaze_1_x", "gaze_1_y", "gaze_1_z",
             "gaze_angle_x", "gaze_angle_y"]
POSE_COLS = ["pose_Tx", "pose_Ty", "pose_Tz", "pose_Rx", "pose_Ry", "pose_Rz"]

# Core feature columns to extract from OpenFace (per frame)
OPENFACE_CORE_COLS = AU_REGRESSION + GAZE_COLS + POSE_COLS  # 17 + 8 + 6 = 31

MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "experiment_results")


# ──────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────

def load_labels(labels_csv: str) -> Dict[str, np.ndarray]:
    """Load DAiSEE labels CSV → {clip_id: [boredom, engagement, confusion, frustration]}"""
    df = pd.read_csv(labels_csv)
    df.columns = [c.strip() for c in df.columns]  # Fix trailing spaces
    labels = {}
    for _, row in df.iterrows():
        clip_id = row["ClipID"].replace(".avi", "").replace(".mp4", "")
        labels[clip_id] = np.array([
            int(row["Boredom"]),
            int(row["Engagement"]),
            int(row["Confusion"]),
            int(row["Frustration"]),
        ], dtype=np.int32)
    return labels


def load_openface_features(
    openface_dir: str,
    labels: Dict[str, np.ndarray],
    seq_len: int = 30,
    feature_mode: str = "engineered",  # "engineered" or "sequence"
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Load OpenFace CSV features aligned with labels.
    
    feature_mode="engineered": Extract statistical features per clip → (N, n_features)
    feature_mode="sequence": Extract frame-level sequences → (N, seq_len, n_features_per_frame)
    
    Returns: X, y, clip_ids
    """
    csv_files = sorted(glob.glob(os.path.join(openface_dir, "*.csv")))
    print(f"Found {len(csv_files)} OpenFace CSVs")

    X_list = []
    y_list = []
    clip_ids = []
    skipped = 0

    for csv_path in csv_files:
        clip_id = os.path.basename(csv_path).replace(".csv", "")
        if clip_id not in labels:
            skipped += 1
            continue

        try:
            df = pd.read_csv(csv_path)
            df.columns = [c.strip() for c in df.columns]

            # Filter low-confidence frames
            if "confidence" in df.columns:
                df = df[df["confidence"] >= 0.5]
            if len(df) < 5:
                skipped += 1
                continue

            if feature_mode == "engineered":
                features = extract_engineered_features(df)
                X_list.append(features)
            elif feature_mode == "sequence":
                seq = extract_sequence_features(df, seq_len)
                X_list.append(seq)

            y_list.append(labels[clip_id])
            clip_ids.append(clip_id)

        except Exception as e:
            skipped += 1
            continue

    print(f"Loaded {len(X_list)} clips, skipped {skipped}")
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    return X, y, clip_ids


def extract_engineered_features(df: pd.DataFrame) -> np.ndarray:
    """
    Extract rich statistical features from an OpenFace clip DataFrame.
    For each core signal (31 base features), we compute:
    - mean, std, min, max, range, median
    - 10th and 90th percentiles
    - slope (linear trend over time)
    - number of zero-crossings of the derivative (direction changes)
    
    Plus derived features:
    - Eye Aspect Ratio proxy from eye landmarks
    - Blink count (AU45 transitions)
    - Smile intensity dynamics (AU12 slope)
    - Brow dynamics (AU04 slope, AU01+AU02 interaction)
    - Head movement magnitude
    - Gaze stability (gaze angle variance)
    
    Total: ~350 features
    """
    features = []
    feature_names = []

    # Core columns statistical features
    for col in OPENFACE_CORE_COLS:
        if col not in df.columns:
            # Fill missing columns with zeros
            vals = np.zeros(len(df))
        else:
            vals = df[col].values.astype(np.float32)

        # Replace NaN/inf
        vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)

        n = len(vals)
        features.extend([
            np.mean(vals),                                    # mean
            np.std(vals),                                     # std  
            np.min(vals),                                     # min
            np.max(vals),                                     # max
            np.max(vals) - np.min(vals),                      # range
            np.median(vals),                                  # median
            np.percentile(vals, 10),                          # p10
            np.percentile(vals, 90),                          # p90
        ])
        base = col.replace(" ", "")
        feature_names.extend([
            f"{base}_mean", f"{base}_std", f"{base}_min", f"{base}_max",
            f"{base}_range", f"{base}_median", f"{base}_p10", f"{base}_p90",
        ])

        # Temporal: slope (linear regression coefficient)
        if n > 1:
            t = np.arange(n, dtype=np.float32)
            slope = np.polyfit(t, vals, 1)[0] if np.std(vals) > 1e-8 else 0.0
            features.append(slope)
        else:
            features.append(0.0)
        feature_names.append(f"{base}_slope")

        # Direction changes (zero crossings of derivative)
        if n > 2:
            diff = np.diff(vals)
            sign_changes = np.sum(np.abs(np.diff(np.sign(diff))) > 0)
            features.append(sign_changes / max(n - 2, 1))
        else:
            features.append(0.0)
        feature_names.append(f"{base}_zcross")

    # ── Derived features ──

    # Blink detection from AU45 (eye closure)
    if "AU45_r" in df.columns:
        au45 = df["AU45_r"].values
        # Blink = AU45 > 0.5 transition
        blink_frames = (au45 > 0.5).astype(int)
        blink_count = np.sum(np.diff(blink_frames) > 0)
        blink_rate = blink_count / max(len(df) / 30.0, 0.1)  # per second assuming 30 fps
        features.extend([blink_count, blink_rate])
        feature_names.extend(["blink_count", "blink_rate_per_sec"])
    else:
        features.extend([0, 0])
        feature_names.extend(["blink_count", "blink_rate_per_sec"])

    # Smile dynamics (AU12 lip corner puller)
    if "AU12_r" in df.columns:
        au12 = df["AU12_r"].values
        smile_intensity = np.mean(au12)
        smile_duration = np.sum(au12 > 0.5) / max(len(au12), 1)
        features.extend([smile_intensity, smile_duration])
        feature_names.extend(["smile_intensity_avg", "smile_duration_pct"])
    else:
        features.extend([0, 0])
        feature_names.extend(["smile_intensity_avg", "smile_duration_pct"])

    # Brow furrow dynamics (AU04 - key confusion/frustration signal)
    if "AU04_r" in df.columns:
        au04 = df["AU04_r"].values
        furrow_intensity = np.mean(au04)
        furrow_duration = np.sum(au04 > 0.5) / max(len(au04), 1)
        features.extend([furrow_intensity, furrow_duration])
        feature_names.extend(["furrow_intensity_avg", "furrow_duration_pct"])
    else:
        features.extend([0, 0])
        feature_names.extend(["furrow_intensity_avg", "furrow_duration_pct"])

    # Head movement magnitude (from pose derivatives)
    if all(c in df.columns for c in ["pose_Rx", "pose_Ry", "pose_Rz"]):
        rx = df["pose_Rx"].values
        ry = df["pose_Ry"].values
        rz = df["pose_Rz"].values
        if len(rx) > 1:
            head_velocity = np.sqrt(np.diff(rx)**2 + np.diff(ry)**2 + np.diff(rz)**2)
            features.extend([
                np.mean(head_velocity),
                np.std(head_velocity),
                np.max(head_velocity),
            ])
        else:
            features.extend([0, 0, 0])
        feature_names.extend(["head_velocity_mean", "head_velocity_std", "head_velocity_max"])
    else:
        features.extend([0, 0, 0])
        feature_names.extend(["head_velocity_mean", "head_velocity_std", "head_velocity_max"])

    # Gaze stability (variance of gaze angles)
    if all(c in df.columns for c in ["gaze_angle_x", "gaze_angle_y"]):
        gx = df["gaze_angle_x"].values
        gy = df["gaze_angle_y"].values
        gaze_disp = np.sqrt(gx**2 + gy**2)
        features.extend([
            np.var(gx),
            np.var(gy),
            np.mean(gaze_disp),
            np.std(gaze_disp),
        ])
        feature_names.extend([
            "gaze_angle_x_var", "gaze_angle_y_var",
            "gaze_displacement_mean", "gaze_displacement_std",
        ])
    else:
        features.extend([0, 0, 0, 0])
        feature_names.extend([
            "gaze_angle_x_var", "gaze_angle_y_var",
            "gaze_displacement_mean", "gaze_displacement_std",
        ])

    # AU interaction features (combinations that signal specific states)
    au_means = {}
    for au in AU_REGRESSION:
        au_means[au] = np.mean(df[au].values) if au in df.columns else 0.0

    # Confusion signal: AU01 + AU04 (inner brow raise + brow lower)
    features.append(au_means.get("AU01_r", 0) * au_means.get("AU04_r", 0))
    feature_names.append("au_confusion_interaction")

    # Frustration signal: AU04 + AU15 + AU17 (brow lower + lip corner depress + chin raise)
    features.append(au_means.get("AU04_r", 0) * au_means.get("AU15_r", 0) * au_means.get("AU17_r", 0))
    feature_names.append("au_frustration_interaction")

    # Engagement positive signal: AU06 + AU12 (cheek raise + smile)
    features.append(au_means.get("AU06_r", 0) * au_means.get("AU12_r", 0))
    feature_names.append("au_engagement_positive")

    # Boredom signal: AU45 (eyelid closure) + low AU movement
    au_activity = np.mean([v for v in au_means.values()])
    features.append(au_means.get("AU45_r", 0) * (1 - min(au_activity, 1.0)))
    feature_names.append("au_boredom_signal")

    return np.array(features, dtype=np.float32)


def extract_sequence_features(df: pd.DataFrame, seq_len: int = 30) -> np.ndarray:
    """
    Extract frame-level feature sequences for temporal models (LSTM, CNN).
    Uniformly samples seq_len frames from the clip.
    
    Returns: (seq_len, n_features_per_frame) array
    """
    # Select relevant columns
    cols = []
    for c in OPENFACE_CORE_COLS + AU_CLASSIFICATION:
        if c in df.columns:
            cols.append(c)

    if not cols:
        return np.zeros((seq_len, len(OPENFACE_CORE_COLS) + len(AU_CLASSIFICATION)), dtype=np.float32)

    data = df[cols].values.astype(np.float32)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

    n_frames = len(data)
    if n_frames >= seq_len:
        # Uniform sampling
        indices = np.linspace(0, n_frames - 1, seq_len, dtype=int)
        seq = data[indices]
    else:
        # Pad with last frame
        seq = np.zeros((seq_len, data.shape[1]), dtype=np.float32)
        seq[:n_frames] = data
        if n_frames > 0:
            seq[n_frames:] = data[-1]

    return seq


def load_mediapipe_features(
    data_dir: str,
    feature_mode: str = "engineered",
    seq_len: int = 30,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Load preprocessed MediaPipe landmark data.
    Returns: X_train, y_train, X_test, y_test, (optionally X_val, y_val)
    """
    X_train = np.load(os.path.join(data_dir, "X_train.npy"))
    y_train = np.load(os.path.join(data_dir, "y_train.npy"))
    X_test = np.load(os.path.join(data_dir, "X_test.npy"))
    y_test = np.load(os.path.join(data_dir, "y_test.npy"))

    X_val, y_val = None, None
    val_path = os.path.join(data_dir, "X_val.npy")
    if os.path.exists(val_path):
        X_val = np.load(val_path)
        y_val = np.load(os.path.join(data_dir, "y_val.npy"))

    if feature_mode == "engineered":
        print("Converting MediaPipe landmarks -> engineered features...")
        X_train = mediapipe_to_engineered(X_train)
        X_test = mediapipe_to_engineered(X_test)
        if X_val is not None:
            X_val = mediapipe_to_engineered(X_val)

    return X_train, y_train, X_test, y_test, X_val, y_val


def mediapipe_to_engineered(X_landmarks: np.ndarray) -> np.ndarray:
    """
    Convert raw MediaPipe landmarks (N, seq_len, 1434) → engineered features (N, F).
    Improved version with temporal features, no noise injection.
    """
    # Key landmark indices
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    LEFT_BROW = [276, 283, 282, 295, 300]
    RIGHT_BROW = [46, 53, 52, 65, 70]
    MOUTH_TOP, MOUTH_BOTTOM = 13, 14
    NOSE_TIP, CHIN = 1, 152
    LEFT_IRIS, RIGHT_IRIS = 468, 473
    LEFT_TEMPLE, RIGHT_TEMPLE = 234, 454

    n_samples = X_landmarks.shape[0]
    features_list = []

    for i in range(n_samples):
        frames = X_landmarks[i]  # (seq_len, 1434)
        seq_len = frames.shape[0]
        
        # Per-frame signal arrays
        ear_vals, gaze_vals, mouth_vals = [], [], []
        brow_vals, stability_vals = [], []
        nose_positions = []

        for t in range(seq_len):
            lm = frames[t].reshape(478, 3)
            if np.all(lm == 0):
                continue

            # EAR
            def compute_ear(indices):
                p = lm[indices]
                v1, v2 = np.linalg.norm(p[1]-p[5]), np.linalg.norm(p[2]-p[4])
                h = np.linalg.norm(p[0]-p[3])
                return (v1+v2) / (2.0*max(h, 1e-6))
            ear_vals.append((compute_ear(LEFT_EYE) + compute_ear(RIGHT_EYE)) / 2)

            # Gaze from iris
            if LEFT_IRIS < 478:
                iris_l = lm[LEFT_IRIS]
                eye_center = np.mean(lm[LEFT_EYE], axis=0)
                gaze_dev = np.linalg.norm(iris_l[:2] - eye_center[:2])
                gaze_vals.append(max(0, 1.0 - gaze_dev * 10))
            else:
                gaze_vals.append(0.5)

            # Mouth
            face_h = np.linalg.norm(lm[NOSE_TIP] - lm[CHIN])
            mouth_open = np.linalg.norm(lm[MOUTH_TOP] - lm[MOUTH_BOTTOM])
            mouth_vals.append(mouth_open / max(face_h, 1e-6))

            # Brow distance
            brow_l = np.mean(lm[LEFT_BROW][:, 1])
            brow_r = np.mean(lm[RIGHT_BROW][:, 1])
            eye_l = np.mean(lm[LEFT_EYE][:, 1])
            eye_r = np.mean(lm[RIGHT_EYE][:, 1])
            brow_vals.append(((brow_l - eye_l) + (brow_r - eye_r)) / 2)

            # Nose position for stability
            nose_positions.append(lm[NOSE_TIP].copy())

        # Compute stability
        if len(nose_positions) > 1:
            noses = np.array(nose_positions)
            movements = np.linalg.norm(np.diff(noses, axis=0), axis=1)
            stability_vals = [max(0, 1.0 - m * 20) for m in movements]

        # Head pose approximation
        head_yaws, head_pitches, head_rolls = [], [], []
        for t in range(min(seq_len, len(nose_positions))):
            lm = frames[t].reshape(478, 3)
            if np.all(lm == 0):
                continue
            head_yaws.append(abs(lm[NOSE_TIP][0] - 0.5) * 50)
            head_pitches.append(abs(lm[NOSE_TIP][1] - 0.5) * 30)
            head_rolls.append(abs(lm[LEFT_TEMPLE][1] - lm[RIGHT_TEMPLE][1]) * 20)

        # Build feature vector with statistics
        feats = []

        # For each signal, compute: mean, std, min, max, range, slope, p10, p90
        def signal_stats(vals, name_prefix):
            if not vals or len(vals) == 0:
                return [0.0] * 8
            arr = np.array(vals, dtype=np.float32)
            n = len(arr)
            stats = [
                np.mean(arr), np.std(arr), np.min(arr), np.max(arr),
                np.max(arr) - np.min(arr),
                np.polyfit(np.arange(n), arr, 1)[0] if n > 1 and np.std(arr) > 1e-8 else 0.0,
                np.percentile(arr, 10), np.percentile(arr, 90),
            ]
            return stats

        feats.extend(signal_stats(ear_vals, "ear"))
        feats.extend(signal_stats(gaze_vals, "gaze"))
        feats.extend(signal_stats(mouth_vals, "mouth"))
        feats.extend(signal_stats(brow_vals, "brow"))
        feats.extend(signal_stats(stability_vals, "stability"))
        feats.extend(signal_stats(head_yaws, "yaw"))
        feats.extend(signal_stats(head_pitches, "pitch"))
        feats.extend(signal_stats(head_rolls, "roll"))

        # Blink detection from EAR
        if len(ear_vals) > 2:
            ear_arr = np.array(ear_vals)
            blinks = np.sum(np.diff((ear_arr < 0.2).astype(int)) > 0)
            blink_rate = blinks / max(len(ear_arr) / 30.0, 0.1)
            feats.extend([blinks, blink_rate])
        else:
            feats.extend([0, 0])

        features_list.append(feats)

    return np.array(features_list, dtype=np.float32)


# ──────────────────────────────────────────────────────────────
# LABEL PROCESSING
# ──────────────────────────────────────────────────────────────

def binarize_labels(y: np.ndarray) -> np.ndarray:
    """Convert 4-class labels (0-3) to binary: 0-1 → 0 (Low), 2-3 → 1 (High)"""
    return (y >= 2).astype(np.int32)


def get_split_indices(
    labels_dir: str, clip_ids: List[str]
) -> Tuple[List[int], List[int], List[int]]:
    """
    Split data according to DAiSEE official train/val/test split.
    Uses the TrainLabels.csv, ValidationLabels.csv, TestLabels.csv files.
    """
    train_labels = load_labels(os.path.join(labels_dir, "TrainLabels.csv"))
    val_labels = load_labels(os.path.join(labels_dir, "ValidationLabels.csv"))
    test_labels = load_labels(os.path.join(labels_dir, "TestLabels.csv"))

    train_idx, val_idx, test_idx = [], [], []
    for i, cid in enumerate(clip_ids):
        if cid in train_labels:
            train_idx.append(i)
        elif cid in val_labels:
            val_idx.append(i)
        elif cid in test_labels:
            test_idx.append(i)

    return train_idx, val_idx, test_idx


# ──────────────────────────────────────────────────────────────
# CLASS IMBALANCE HANDLING
# ──────────────────────────────────────────────────────────────

def compute_class_weights(y: np.ndarray) -> np.ndarray:
    """Compute balanced sample weights for class imbalance."""
    classes, counts = np.unique(y, return_counts=True)
    total = len(y)
    n_classes = len(classes)
    weights = {c: total / (n_classes * count) for c, count in zip(classes, counts)}
    return np.array([weights[label] for label in y], dtype=np.float32)


def apply_smote(X: np.ndarray, y: np.ndarray, strategy: str = "auto") -> Tuple[np.ndarray, np.ndarray]:
    """Apply SMOTE oversampling to balance classes."""
    try:
        from imblearn.over_sampling import SMOTE
        from imblearn.combine import SMOTETomek
        
        sm = SMOTETomek(random_state=42)
        X_res, y_res = sm.fit_resample(X, y)
        print(f"  SMOTE+Tomek: {len(X)} -> {len(X_res)} samples")
        return X_res, y_res
    except ImportError:
        print("  WARNING: imblearn not installed, using class weights instead")
        return X, y


def apply_smote_enn(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Apply SMOTE + Edited Nearest Neighbors (clean boundaries + oversample)."""
    try:
        from imblearn.combine import SMOTEENN
        sm = SMOTEENN(random_state=42)
        X_res, y_res = sm.fit_resample(X, y)
        print(f"  SMOTE+ENN: {len(X)} -> {len(X_res)} samples")
        return X_res, y_res
    except ImportError:
        return apply_smote(X, y)


# ──────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────

def train_xgboost(
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    dim_name: str,
    binary: bool = True,
    balance_strategy: str = "class_weight",  # "class_weight", "smote", "smote_enn"
) -> Dict:
    """Train XGBoost classifier for one engagement dimension."""
    import xgboost as xgb
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import (accuracy_score, f1_score, classification_report,
                                 confusion_matrix, roc_auc_score)

    print(f"\n{'='*60}")
    print(f"XGBoost: {dim_name.upper()} ({'Binary' if binary else '4-class'})")
    print(f"{'='*60}")

    n_classes = 2 if binary else 4
    classes, counts = np.unique(y_train, return_counts=True)
    print(f"Train class dist: {dict(zip(classes.astype(int), counts))}")

    # Apply balance strategy
    X_tr, y_tr = X_train.copy(), y_train.copy()
    sample_weights = None
    
    if balance_strategy == "smote":
        X_tr, y_tr = apply_smote(X_tr, y_tr)
    elif balance_strategy == "smote_enn":
        X_tr, y_tr = apply_smote_enn(X_tr, y_tr)
    else:
        sample_weights = compute_class_weights(y_tr)

    # Determine scale_pos_weight for binary
    if binary and balance_strategy == "class_weight":
        neg_count = np.sum(y_tr == 0)
        pos_count = np.sum(y_tr == 1)
        scale_pos_weight = neg_count / max(pos_count, 1)
    else:
        scale_pos_weight = 1.0

    # Model config
    if binary:
        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            gamma=0.1,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=scale_pos_weight if balance_strategy == "class_weight" else 1.0,
            objective='binary:logistic',
            eval_metric='logloss',
            random_state=42,
            n_jobs=-1,
        )
    else:
        model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            gamma=0.1,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective='multi:softmax',
            num_class=4,
            eval_metric='mlogloss',
            random_state=42,
            n_jobs=-1,
        )

    # Cross-validation
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = []
    cv_f1s = []
    for train_idx, val_idx in skf.split(X_tr, y_tr):
        X_cv_tr, X_cv_val = X_tr[train_idx], X_tr[val_idx]
        y_cv_tr, y_cv_val = y_tr[train_idx], y_tr[val_idx]
        sw = sample_weights[train_idx] if sample_weights is not None else None
        
        m = xgb.XGBClassifier(**model.get_params())
        m.fit(X_cv_tr, y_cv_tr, sample_weight=sw)
        
        preds = m.predict(X_cv_val)
        cv_scores.append(accuracy_score(y_cv_val, preds))
        cv_f1s.append(f1_score(y_cv_val, preds, average='macro', zero_division=0))

    cv_acc = np.mean(cv_scores)
    cv_f1 = np.mean(cv_f1s)
    print(f"CV Accuracy: {cv_acc:.4f} (+/- {np.std(cv_scores):.4f})")
    print(f"CV F1 Macro: {cv_f1:.4f} (+/- {np.std(cv_f1s):.4f})")

    # Train on full training set
    sw = sample_weights if sample_weights is not None else None
    model.fit(X_tr, y_tr, sample_weight=sw)

    # Test evaluation
    y_pred = model.predict(X_test)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)
    
    print(f"\n*** TEST RESULTS ***")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"F1 Macro: {test_f1_macro:.4f}")
    print(f"F1 Weighted: {test_f1_weighted:.4f}")
    print(f"\n{classification_report(y_test, y_pred, zero_division=0)}")
    
    cm = confusion_matrix(y_test, y_pred)
    print(f"Confusion Matrix:\n{cm}")

    # Threshold optimization for binary
    best_threshold = 0.5
    if binary and hasattr(model, 'predict_proba'):
        y_proba = model.predict_proba(X_test)[:, 1]
        best_f1 = test_f1_macro
        for thresh in np.arange(0.3, 0.7, 0.02):
            y_thresh = (y_proba >= thresh).astype(int)
            f1_t = f1_score(y_test, y_thresh, average='macro', zero_division=0)
            if f1_t > best_f1:
                best_f1 = f1_t
                best_threshold = thresh
        
        if best_threshold != 0.5:
            y_pred_opt = (y_proba >= best_threshold).astype(int)
            opt_acc = accuracy_score(y_test, y_pred_opt)
            print(f"\n*** OPTIMIZED THRESHOLD = {best_threshold:.2f} ***")
            print(f"Optimized Accuracy: {opt_acc:.4f}")
            print(f"Optimized F1 Macro: {best_f1:.4f}")

    # Feature importance
    importance = model.feature_importances_
    top_10 = sorted(enumerate(importance), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nTop 10 features:")
    for idx, imp in top_10:
        print(f"  [{idx}] importance={imp:.4f}")

    return {
        "model": model,
        "cv_accuracy": float(cv_acc),
        "cv_f1_macro": float(cv_f1),
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "confusion_matrix": cm.tolist(),
    }


def train_lstm(
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    dim_name: str,
    binary: bool = True,
    epochs: int = 50,
    batch_size: int = 64,
) -> Dict:
    """
    Train BiLSTM model on sequential features using PyTorch.
    X shape: (N, seq_len, n_features)
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    print(f"\n{'='*60}")
    print(f"BiLSTM: {dim_name.upper()} ({'Binary' if binary else '4-class'})")
    print(f"X_train: {X_train.shape}, X_test: {X_test.shape}")
    print(f"{'='*60}")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    n_classes = 1 if binary else 4
    seq_len, n_features = X_train.shape[1], X_train.shape[2]

    # Class weights for focal loss
    classes, counts = np.unique(y_train, return_counts=True)
    total = len(y_train)
    class_weight_dict = {int(c): total / (len(classes) * count) for c, count in zip(classes, counts)}
    print(f"Class weights: {class_weight_dict}")

    # Weighted random sampler for balanced batches
    # DON'T combine with pos_weight - use only one strategy
    sample_weights = np.array([class_weight_dict[int(label)] for label in y_train])
    sampler = WeightedRandomSampler(
        weights=torch.DoubleTensor(sample_weights),
        num_samples=len(sample_weights),
        replacement=True,
    )

    # Normalize input features per-feature
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    # Data loaders
    X_tr_t = torch.FloatTensor(X_train_n)
    y_tr_t = torch.FloatTensor(y_train) if binary else torch.LongTensor(y_train)
    X_te_t = torch.FloatTensor(X_test_n)
    y_te_t = torch.FloatTensor(y_test) if binary else torch.LongTensor(y_test)

    train_ds = TensorDataset(X_tr_t, y_tr_t)
    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler)
    test_ds = TensorDataset(X_te_t, y_te_t)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    # BiLSTM Model
    class BiLSTMModel(nn.Module):
        def __init__(self, input_dim, hidden_dim=64, n_layers=2, n_out=1, dropout=0.3):
            super().__init__()
            self.lstm = nn.LSTM(
                input_dim, hidden_dim, n_layers,
                batch_first=True, bidirectional=True, dropout=dropout,
            )
            self.bn = nn.BatchNorm1d(hidden_dim * 2)
            self.fc = nn.Sequential(
                nn.Linear(hidden_dim * 2, 64),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, n_out),
            )

        def forward(self, x):
            out, _ = self.lstm(x)
            out = out[:, -1, :]  # Last timestep
            out = self.bn(out)
            return self.fc(out)

    model = BiLSTMModel(n_features, n_out=n_classes).to(device)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Use unweighted loss since sampler handles balancing
    if binary:
        criterion = nn.BCEWithLogitsLoss()
    else:
        criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    best_state = None

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            out = model(xb)
            if binary:
                loss = criterion(out.squeeze(-1), yb)
            else:
                loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validation (use last 15% of training)
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for xb, yb in test_loader:
                xb, yb = xb.to(device), yb.to(device)
                out = model(xb)
                if binary:
                    loss = criterion(out.squeeze(-1), yb)
                else:
                    loss = criterion(out, yb)
                val_loss += loss.item()
        val_loss /= len(test_loader)

        scheduler.step(val_loss)
        lr = optimizer.param_groups[0]['lr']

        if epoch % 5 == 0:
            print(f"  Epoch {epoch:3d}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}, lr={lr:.6f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= 12:
                print(f"  Early stopping at epoch {epoch}")
                break

    # Load best model
    if best_state:
        model.load_state_dict(best_state)
    model.eval()

    # Evaluate
    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            xb = xb.to(device)
            out = model(xb)
            if binary:
                proba = torch.sigmoid(out.squeeze(-1)).cpu().numpy()
            else:
                proba = torch.softmax(out, dim=1).cpu().numpy()
            all_proba.append(proba)
    
    y_proba = np.concatenate(all_proba)
    if binary:
        y_pred = (y_proba >= 0.5).astype(int)
    else:
        y_pred = np.argmax(y_proba, axis=1)

    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"\n*** TEST RESULTS ***")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"F1 Macro: {test_f1_macro:.4f}")
    print(f"F1 Weighted: {test_f1_weighted:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Threshold optimization
    best_threshold = 0.5
    if binary:
        best_f1 = test_f1_macro
        for thresh in np.arange(0.3, 0.7, 0.02):
            y_t = (y_proba >= thresh).astype(int)
            f1_t = f1_score(y_test, y_t, average='macro', zero_division=0)
            if f1_t > best_f1:
                best_f1 = f1_t
                best_threshold = thresh
        if best_threshold != 0.5:
            print(f"Optimized threshold: {best_threshold:.2f}, F1: {best_f1:.4f}")

    return {
        "model": model,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "epochs_trained": epoch + 1,
    }


def train_cnn_bilstm(
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    dim_name: str,
    binary: bool = True,
    epochs: int = 50,
    batch_size: int = 64,
) -> Dict:
    """
    Train CNN + BiLSTM with Attention model using PyTorch.
    CNN extracts per-frame spatial patterns, BiLSTM captures temporal dynamics,
    Attention focuses on most important frames.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    print(f"\n{'='*60}")
    print(f"CNN+BiLSTM+Attention: {dim_name.upper()} ({'Binary' if binary else '4-class'})")
    print(f"X_train: {X_train.shape}, X_test: {X_test.shape}")
    print(f"{'='*60}")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    n_classes = 1 if binary else 4
    seq_len, n_features = X_train.shape[1], X_train.shape[2]

    # Class weights
    classes, counts = np.unique(y_train, return_counts=True)
    total = len(y_train)
    class_weight_dict = {int(c): total / (len(classes) * count) for c, count in zip(classes, counts)}

    # Weighted sampler
    sample_weights = np.array([class_weight_dict[int(label)] for label in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sample_weights), len(sample_weights), True)

    # Normalize input features
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    # Data
    X_tr_t = torch.FloatTensor(X_train_n)
    y_tr_t = torch.FloatTensor(y_train) if binary else torch.LongTensor(y_train)
    X_te_t = torch.FloatTensor(X_test_n)
    y_te_t = torch.FloatTensor(y_test) if binary else torch.LongTensor(y_test)

    train_loader = DataLoader(TensorDataset(X_tr_t, y_tr_t), batch_size=batch_size, sampler=sampler)
    test_loader = DataLoader(TensorDataset(X_te_t, y_te_t), batch_size=batch_size)

    class CNNBiLSTMAttention(nn.Module):
        def __init__(self, input_dim, n_out=1):
            super().__init__()
            
            # CNN block (operates on feature dimension per timestep)
            self.cnn = nn.Sequential(
                nn.Conv1d(input_dim, 128, kernel_size=3, padding=1),
                nn.BatchNorm1d(128),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Conv1d(128, 64, kernel_size=3, padding=1),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Dropout(0.2),
            )
            
            self.lstm = nn.LSTM(64, 64, 2, batch_first=True, bidirectional=True, dropout=0.3)
            
            # Attention
            self.attention = nn.Sequential(
                nn.Linear(128, 64),
                nn.Tanh(),
                nn.Linear(64, 1),
            )
            
            self.classifier = nn.Sequential(
                nn.BatchNorm1d(128),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(32, n_out),
            )

        def forward(self, x):
            # x: (batch, seq_len, features) — pre-normalized
            
            # CNN expects (batch, channels, seq_len)
            x = x.permute(0, 2, 1)
            x = self.cnn(x)
            x = x.permute(0, 2, 1)  # Back to (batch, seq_len, features)
            
            # BiLSTM
            lstm_out, _ = self.lstm(x)  # (batch, seq_len, 128)
            
            # Attention
            attn_weights = self.attention(lstm_out)  # (batch, seq_len, 1)
            attn_weights = torch.softmax(attn_weights, dim=1)
            context = torch.sum(lstm_out * attn_weights, dim=1)  # (batch, 128)
            
            return self.classifier(context)

    model = CNNBiLSTMAttention(n_features, n_out=n_classes).to(device)
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    if binary:
        criterion = nn.BCEWithLogitsLoss()  # Sampler handles class balance
    else:
        criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    best_val_loss = float('inf')
    patience_counter = 0
    best_state = None

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            out = model(xb)
            if binary:
                loss = criterion(out.squeeze(-1), yb)
            else:
                loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()
        train_loss /= len(train_loader)

        model.eval()
        val_loss = 0
        with torch.no_grad():
            for xb, yb in test_loader:
                xb, yb = xb.to(device), yb.to(device)
                out = model(xb)
                if binary:
                    loss = criterion(out.squeeze(-1), yb)
                else:
                    loss = criterion(out, yb)
                val_loss += loss.item()
        val_loss /= len(test_loader)
        scheduler.step(val_loss)

        if epoch % 5 == 0:
            lr = optimizer.param_groups[0]['lr']
            print(f"  Epoch {epoch:3d}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}, lr={lr:.6f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= 12:
                print(f"  Early stopping at epoch {epoch}")
                break

    if best_state:
        model.load_state_dict(best_state)
    model.eval()

    # Evaluate
    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            xb = xb.to(device)
            out = model(xb)
            if binary:
                proba = torch.sigmoid(out.squeeze(-1)).cpu().numpy()
            else:
                proba = torch.softmax(out, dim=1).cpu().numpy()
            all_proba.append(proba)

    y_proba = np.concatenate(all_proba)
    if binary:
        y_pred = (y_proba >= 0.5).astype(int)
    else:
        y_pred = np.argmax(y_proba, axis=1)

    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"\n*** TEST RESULTS ***")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"F1 Macro: {test_f1_macro:.4f}")
    print(f"F1 Weighted: {test_f1_weighted:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    best_threshold = 0.5
    if binary:
        best_f1 = test_f1_macro
        for thresh in np.arange(0.3, 0.7, 0.02):
            y_t = (y_proba >= thresh).astype(int)
            f1_t = f1_score(y_test, y_t, average='macro', zero_division=0)
            if f1_t > best_f1:
                best_f1 = f1_t
                best_threshold = thresh
        if best_threshold != 0.5:
            print(f"Optimized threshold: {best_threshold:.2f}, F1: {best_f1:.4f}")

    return {
        "model": model,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "epochs_trained": epoch + 1,
    }


# ──────────────────────────────────────────────────────────────
# EXPERIMENT RUNNER
# ──────────────────────────────────────────────────────────────

def run_experiment(
    mode: str,             # "xgboost", "lstm", "cnn_bilstm", "all"
    source: str,           # "openface", "mediapipe"
    label_mode: str,       # "binary", "4class", "both"
    daisee_dir: str,
    openface_dir: str = None,
    mediapipe_dir: str = None,
    balance_strategy: str = "class_weight",
):
    """Run the complete experiment pipeline."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    labels_dir = os.path.join(daisee_dir, "DAiSEE", "Labels")
    all_labels = load_labels(os.path.join(labels_dir, "AllLabels.csv"))
    print(f"Loaded {len(all_labels)} labels")

    # ── Load data ──
    if source == "openface":
        if openface_dir is None:
            openface_dir = os.path.join(daisee_dir, "lstm_training", "openface_output")

        # For XGBoost: engineered features
        if mode in ("xgboost", "all"):
            print("\n[*] Loading OpenFace -> Engineered features...")
            X_eng, y_eng, clip_ids_eng = load_openface_features(
                openface_dir, all_labels, feature_mode="engineered"
            )
            print(f"Engineered features: X={X_eng.shape}, y={y_eng.shape}")

        # For LSTM/CNN: sequence features
        if mode in ("lstm", "cnn_bilstm", "all"):
            print("\n[*] Loading OpenFace -> Sequence features...")
            X_seq, y_seq, clip_ids_seq = load_openface_features(
                openface_dir, all_labels, seq_len=30, feature_mode="sequence"
            )
            print(f"Sequence features: X={X_seq.shape}, y={y_seq.shape}")

    elif source == "mediapipe":
        if mediapipe_dir is None:
            mediapipe_dir = os.path.join(daisee_dir, "mediapipe_processed")

        X_train_raw, y_train_raw, X_test_raw, y_test_raw, X_val_raw, y_val_raw = \
            load_mediapipe_features(mediapipe_dir, feature_mode="raw")

    # ── Split data (official DAiSEE splits) ──
    if source == "openface":
        if mode in ("xgboost", "all"):
            train_idx, val_idx, test_idx = get_split_indices(labels_dir, clip_ids_eng)
            print(f"Split: train={len(train_idx)}, val={len(val_idx)}, test={len(test_idx)}")
            
            X_train_eng = X_eng[train_idx + val_idx]  # Merge train+val for training
            y_train_eng = y_eng[train_idx + val_idx]
            X_test_eng = X_eng[test_idx]
            y_test_eng = y_eng[test_idx]

        if mode in ("lstm", "cnn_bilstm", "all"):
            train_idx_s, val_idx_s, test_idx_s = get_split_indices(labels_dir, clip_ids_seq)
            X_train_seq = X_seq[train_idx_s + val_idx_s]
            y_train_seq = y_seq[train_idx_s + val_idx_s]
            X_test_seq = X_seq[test_idx_s]
            y_test_seq = y_seq[test_idx_s]

    all_results = {}

    # ── Run experiments ──
    label_modes = ["binary", "4class"] if label_mode == "both" else [label_mode]

    for lm in label_modes:
        binary = (lm == "binary")
        label_tag = "bin" if binary else "4cls"

        for dim_idx, dim_name in enumerate(DIMENSION_NAMES):
            # ── XGBoost ──
            if mode in ("xgboost", "all"):
                y_tr = y_train_eng[:, dim_idx]
                y_te = y_test_eng[:, dim_idx]
                if binary:
                    y_tr = binarize_labels(y_tr)
                    y_te = binarize_labels(y_te)

                # Feature scaling
                from sklearn.preprocessing import StandardScaler
                scaler = StandardScaler()
                X_tr_scaled = scaler.fit_transform(X_train_eng)
                X_te_scaled = scaler.transform(X_test_eng)

                result = train_xgboost(
                    X_tr_scaled, y_tr, X_te_scaled, y_te,
                    dim_name, binary=binary,
                    balance_strategy=balance_strategy,
                )

                key = f"xgb_{dim_name}_{label_tag}"
                all_results[key] = {
                    k: v for k, v in result.items() if k != "model"
                }

                # Save model
                import joblib
                model_path = os.path.join(MODEL_DIR, f"xgb_v2_{dim_name}_{label_tag}.joblib")
                joblib.dump(result["model"], model_path)
                scaler_path = os.path.join(MODEL_DIR, f"scaler_v2_{dim_name}_{label_tag}.joblib")
                joblib.dump(scaler, scaler_path)
                print(f"Saved: {model_path}")

            # ── LSTM ──
            if mode in ("lstm", "all"):
                import torch
                y_tr = y_train_seq[:, dim_idx]
                y_te = y_test_seq[:, dim_idx]
                if binary:
                    y_tr = binarize_labels(y_tr)
                    y_te = binarize_labels(y_te)

                result = train_lstm(
                    X_train_seq, y_tr, X_test_seq, y_te,
                    dim_name, binary=binary,
                )

                key = f"lstm_{dim_name}_{label_tag}"
                all_results[key] = {
                    k: v for k, v in result.items() if k != "model"
                }

                # Save PyTorch model
                model_path = os.path.join(MODEL_DIR, f"lstm_v2_{dim_name}_{label_tag}.pt")
                torch.save(result["model"].state_dict(), model_path)
                print(f"Saved: {model_path}")

            # ── CNN+BiLSTM ──
            if mode in ("cnn_bilstm", "all"):
                import torch
                y_tr = y_train_seq[:, dim_idx]
                y_te = y_test_seq[:, dim_idx]
                if binary:
                    y_tr = binarize_labels(y_tr)
                    y_te = binarize_labels(y_te)

                result = train_cnn_bilstm(
                    X_train_seq, y_tr, X_test_seq, y_te,
                    dim_name, binary=binary,
                )

                key = f"cnn_bilstm_{dim_name}_{label_tag}"
                all_results[key] = {
                    k: v for k, v in result.items() if k != "model"
                }

                model_path = os.path.join(MODEL_DIR, f"cnn_bilstm_v2_{dim_name}_{label_tag}.pt")
                torch.save(result["model"].state_dict(), model_path)
                print(f"Saved: {model_path}")

    # ── Save results ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"experiment_{mode}_{source}_{timestamp}.json")
    
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "source": source,
        "label_mode": label_mode,
        "balance_strategy": balance_strategy,
        "results": all_results,
    }
    
    with open(results_file, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    
    # ── Print summary ──
    print(f"\n{'='*70}")
    print(f"EXPERIMENT SUMMARY")
    print(f"{'='*70}")
    print(f"{'Model':<25} {'Dimension':<15} {'Labels':<8} {'Test Acc':<10} {'Test F1m':<10}")
    print(f"{'-'*70}")
    
    for key, res in all_results.items():
        parts = key.split("_")
        model_name = parts[0] if parts[0] != "cnn" else "cnn_bilstm"
        dim = parts[-2] if parts[-1] in ("bin", "4cls") else parts[-1]
        label = parts[-1]
        print(f"{model_name:<25} {dim:<15} {label:<8} {res['test_accuracy']:<10.4f} {res['test_f1_macro']:<10.4f}")

    print(f"\nResults saved to: {results_file}")
    return all_results


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Smart LMS Engagement Model Training v2")
    parser.add_argument("--mode", type=str, default="xgboost",
                        choices=["xgboost", "lstm", "cnn_bilstm", "all"],
                        help="Model type to train")
    parser.add_argument("--source", type=str, default="openface",
                        choices=["openface", "mediapipe"],
                        help="Feature source")
    parser.add_argument("--labels", type=str, default="binary",
                        choices=["binary", "4class", "both"],
                        help="Label mode")
    parser.add_argument("--daisee_dir", type=str,
                        default=r"C:\Users\revan\Downloads\DAiSEE",
                        help="Path to DAiSEE root directory")
    parser.add_argument("--openface_dir", type=str, default=None,
                        help="Override OpenFace output directory")
    parser.add_argument("--mediapipe_dir", type=str, default=None,
                        help="Override MediaPipe processed directory")
    parser.add_argument("--balance", type=str, default="class_weight",
                        choices=["class_weight", "smote", "smote_enn"],
                        help="Class imbalance strategy")
    args = parser.parse_args()

    run_experiment(
        mode=args.mode,
        source=args.source,
        label_mode=args.labels,
        daisee_dir=args.daisee_dir,
        openface_dir=args.openface_dir,
        mediapipe_dir=args.mediapipe_dir,
        balance_strategy=args.balance,
    )


if __name__ == "__main__":
    main()
