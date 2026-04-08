"""
Smart LMS - Engagement Model Training Script
Trains XGBoost models on DAiSEE-style features for 4 engagement dimensions.

Based on: "Designing an Explainable Multimodal Engagement Model"
- Das & Dev: XGBoost on AU+behavioral features → 82.9% accuracy
- Uses extracted MediaPipe landmarks → engineered features → XGBoost
- Produces SHAP-explainable models

Usage:
    python -m app.ml.train_model --data_dir /path/to/mediapipe_processed
    
    Or with synthetic data for bootstrapping:
    python -m app.ml.train_model --synthetic
"""

import numpy as np
import os
import json
import argparse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Same feature definitions as engagement_model.py
FEATURE_NAMES = [
    "au01_inner_brow_raise", "au02_outer_brow_raise", "au04_brow_lowerer",
    "au06_cheek_raiser", "au12_lip_corner_puller", "au15_lip_corner_depressor",
    "au25_lips_part", "au26_jaw_drop",
    "gaze_score", "head_pose_yaw", "head_pose_pitch", "head_pose_roll",
    "head_pose_stability", "eye_aspect_ratio",
    "blink_rate", "mouth_openness",
    "keyboard_activity_pct", "mouse_activity_pct", "tab_visible_pct",
    "playback_speed_avg", "note_taking_pct",
    "gaze_variance", "head_stability_variance", "blink_rate_variance",
]

DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]
MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")


def generate_synthetic_dataset(n_samples: int = 5000) -> tuple:
    """
    Generate synthetic training data that mimics DAiSEE engagement patterns.
    Each sample has 24 features and 4 target labels (0-3 scale).
    
    This creates realistic correlations:
    - High gaze + stable head → high engagement
    - Furrowed brows (au04) → high confusion
    - High blink rate + restlessness → high boredom
    - Low tab visibility + frustration signals → high frustration
    """
    np.random.seed(42)
    X = np.zeros((n_samples, len(FEATURE_NAMES)), dtype=np.float32)
    y = np.zeros((n_samples, 4), dtype=np.float32)  # boredom, engagement, confusion, frustration

    for i in range(n_samples):
        # Generate base behavioral state (latent engagement level 0-1)
        true_engagement = np.random.beta(2, 2)  # Centered around 0.5
        true_confusion = np.random.beta(1.5, 3)  # Skewed low
        true_boredom = np.random.beta(1.5, 3)
        true_frustration = np.random.beta(1.2, 4)  # Rare

        noise = lambda scale=0.1: np.random.normal(0, scale)

        # --- Generate features from latent states ---

        # Action Units
        X[i, 0] = np.clip(0.1 + true_confusion * 0.4 + noise(0.08), 0, 1)  # au01
        X[i, 1] = np.clip(0.05 + true_confusion * 0.3 + noise(0.06), 0, 1)  # au02
        X[i, 2] = np.clip(0.1 + true_confusion * 0.5 + true_frustration * 0.3 + noise(0.08), 0, 1)  # au04 brow lowerer
        X[i, 3] = np.clip(true_engagement * 0.4 + noise(0.08), 0, 1)  # au06 cheek raiser
        X[i, 4] = np.clip(true_engagement * 0.5 - true_frustration * 0.2 + noise(0.1), 0, 1)  # au12 smile
        X[i, 5] = np.clip(true_frustration * 0.4 + true_boredom * 0.2 + noise(0.06), 0, 1)  # au15 frown
        X[i, 6] = np.clip(0.1 + true_confusion * 0.2 + noise(0.05), 0, 1)  # au25
        X[i, 7] = np.clip(true_confusion * 0.15 + noise(0.04), 0, 1)  # au26

        # Gaze & Head
        X[i, 8] = np.clip(0.3 + true_engagement * 0.6 - true_boredom * 0.3 + noise(0.1), 0, 1)  # gaze
        X[i, 9] = np.clip(5 + (1 - true_engagement) * 15 + noise(3), 0, 40)  # yaw
        X[i, 10] = np.clip(4 + (1 - true_engagement) * 10 + noise(2), 0, 30)  # pitch
        X[i, 11] = np.clip(2 + true_boredom * 8 + noise(1.5), 0, 20)  # roll
        X[i, 12] = np.clip(0.3 + true_engagement * 0.5 - true_boredom * 0.2 + noise(0.1), 0, 1)  # stability
        X[i, 13] = np.clip(0.2 + 0.1 * (1 - true_boredom) + noise(0.03), 0.1, 0.4)  # EAR

        # Blink & Mouth
        X[i, 14] = np.clip(15 + true_boredom * 15 - true_engagement * 5 + noise(3), 5, 40)  # blink rate
        X[i, 15] = np.clip(true_confusion * 0.3 + noise(0.05), 0, 1)  # mouth

        # Behavioral
        X[i, 16] = np.clip(true_engagement * 0.4 + noise(0.08), 0, 1)  # keyboard
        X[i, 17] = np.clip(0.2 + true_engagement * 0.3 + noise(0.08), 0, 1)  # mouse
        X[i, 18] = np.clip(0.5 + true_engagement * 0.4 - true_frustration * 0.3 + noise(0.1), 0, 1)  # tab visible
        X[i, 19] = np.clip(1.0 + true_boredom * 0.8 - true_engagement * 0.3 + noise(0.15), 0.5, 3.0)  # speed
        X[i, 20] = np.clip(true_engagement * 0.35 + noise(0.06), 0, 1)  # notes

        # Temporal variance
        X[i, 21] = np.clip(0.01 + (1 - true_engagement) * 0.05 + noise(0.01), 0, 0.2)  # gaze var
        X[i, 22] = np.clip(0.01 + true_boredom * 0.04 + noise(0.01), 0, 0.15)  # head var
        X[i, 23] = np.clip(3 + true_boredom * 10 + noise(2), 0, 30)  # blink var

        # --- Generate labels (0-3 scale, matching DAiSEE) ---
        y[i, 0] = np.clip(round(true_boredom * 3 + noise(0.3)), 0, 3)
        y[i, 1] = np.clip(round(true_engagement * 3 + noise(0.3)), 0, 3)
        y[i, 2] = np.clip(round(true_confusion * 3 + noise(0.3)), 0, 3)
        y[i, 3] = np.clip(round(true_frustration * 3 + noise(0.3)), 0, 3)

    return X, y.astype(np.int32)


def features_from_landmarks(X_landmarks: np.ndarray, y_labels: np.ndarray) -> tuple:
    """
    Convert raw MediaPipe landmarks (478 x 3) into engineered features.
    This bridges the DAiSEE dataset extraction with our feature format.
    
    X_landmarks: shape (N, seq_len, 1434) - 478 landmarks x 3 coords
    y_labels: shape (N, 4) - [boredom, engagement, confusion, frustration]
    """
    n_samples = X_landmarks.shape[0]
    seq_len = X_landmarks.shape[1]
    n_features = len(FEATURE_NAMES)
    X_features = np.zeros((n_samples, n_features), dtype=np.float32)

    # Key landmark indices for feature extraction
    # MediaPipe Face Mesh indices (478 landmarks, 0-indexed)
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    LEFT_BROW = [276, 283, 282, 295, 300]
    RIGHT_BROW = [46, 53, 52, 65, 70]
    MOUTH_TOP = 13
    MOUTH_BOTTOM = 14
    NOSE_TIP = 1
    CHIN = 152
    LEFT_TEMPLE = 234
    RIGHT_TEMPLE = 454
    LEFT_IRIS = 468  # With refine_landmarks
    RIGHT_IRIS = 473

    for i in range(n_samples):
        frames = X_landmarks[i]  # (seq_len, 1434)
        
        # Per-frame features
        frame_gaze = []
        frame_ear = []
        frame_blink = []
        frame_mouth = []
        frame_brow = []
        frame_stability = []
        prev_nose = None

        for t in range(seq_len):
            lm = frames[t].reshape(478, 3)

            if np.all(lm == 0):
                continue

            # EAR (Eye Aspect Ratio) - proxy for eye openness
            def ear_eye(indices):
                p = lm[indices]
                v1 = np.linalg.norm(p[1] - p[5])
                v2 = np.linalg.norm(p[2] - p[4])
                h = np.linalg.norm(p[0] - p[3])
                return (v1 + v2) / (2.0 * max(h, 1e-6))

            left_ear = ear_eye(LEFT_EYE)
            right_ear = ear_eye(RIGHT_EYE)
            frame_ear.append((left_ear + right_ear) / 2)

            # Gaze estimation from iris position relative to eye corners
            if LEFT_IRIS < 478:
                iris_l = lm[LEFT_IRIS]
                eye_l_center = np.mean(lm[LEFT_EYE], axis=0)
                gaze_dev = np.linalg.norm(iris_l[:2] - eye_l_center[:2])
                frame_gaze.append(max(0, 1.0 - gaze_dev * 10))
            else:
                frame_gaze.append(0.5)

            # Mouth openness
            mouth_open = np.linalg.norm(lm[MOUTH_TOP] - lm[MOUTH_BOTTOM])
            face_height = np.linalg.norm(lm[NOSE_TIP] - lm[CHIN])
            frame_mouth.append(mouth_open / max(face_height, 1e-6))

            # Brow lowering (au04 proxy)
            brow_l = np.mean(lm[LEFT_BROW][:, 1])
            brow_r = np.mean(lm[RIGHT_BROW][:, 1])
            eye_l = np.mean(lm[LEFT_EYE][:, 1])
            eye_r = np.mean(lm[RIGHT_EYE][:, 1])
            brow_dist = ((brow_l - eye_l) + (brow_r - eye_r)) / 2
            frame_brow.append(brow_dist)

            # Head pose stability
            nose_pos = lm[NOSE_TIP]
            if prev_nose is not None:
                movement = np.linalg.norm(nose_pos - prev_nose)
                frame_stability.append(max(0, 1.0 - movement * 20))
            prev_nose = nose_pos.copy()

        # Aggregate to features
        if frame_gaze:
            X_features[i, 8] = np.mean(frame_gaze)  # gaze_score
            X_features[i, 21] = np.var(frame_gaze)  # gaze_variance

        if frame_ear:
            X_features[i, 13] = np.mean(frame_ear)  # eye_aspect_ratio
            # Blink detection: EAR drops
            ear_arr = np.array(frame_ear)
            blinks = np.sum(np.diff(ear_arr < 0.2).astype(int) > 0)
            X_features[i, 14] = blinks * (60 / max(seq_len * 0.1, 1))  # blink rate (per min)
            X_features[i, 23] = np.var(ear_arr) * 100

        if frame_mouth:
            X_features[i, 15] = np.mean(frame_mouth)

        if frame_brow:
            brow_arr = np.array(frame_brow)
            X_features[i, 2] = np.clip(np.mean(brow_arr) * 10, 0, 1)  # au04
            X_features[i, 0] = np.clip(np.std(brow_arr) * 5, 0, 1)  # au01
            X_features[i, 1] = np.clip(np.std(brow_arr) * 3, 0, 1)  # au02

        if frame_stability:
            X_features[i, 12] = np.mean(frame_stability)
            X_features[i, 22] = np.var(frame_stability)

        # Smile proxy from EAR + mouth
        if frame_ear and frame_mouth:
            X_features[i, 4] = np.clip(np.mean(frame_ear) * 2, 0, 1)  # au12

        # Fill remaining AUs with noise (would need full AU extraction in production)
        X_features[i, 3] = np.clip(np.random.normal(0.2, 0.1), 0, 1)  # au06
        X_features[i, 5] = np.clip(np.random.normal(0.1, 0.05), 0, 1)  # au15
        X_features[i, 6] = np.clip(np.random.normal(0.1, 0.05), 0, 1)  # au25
        X_features[i, 7] = np.clip(np.random.normal(0.05, 0.03), 0, 1)  # au26

        # Head pose (from nose/temple positions)
        # Simplified: use nose x/y as rough yaw/pitch estimates
        if not np.all(frames[seq_len // 2] == 0):
            mid_lm = frames[seq_len // 2].reshape(478, 3)
            X_features[i, 9] = abs(mid_lm[NOSE_TIP][0] - 0.5) * 50  # yaw
            X_features[i, 10] = abs(mid_lm[NOSE_TIP][1] - 0.5) * 30  # pitch
            X_features[i, 11] = abs(mid_lm[LEFT_TEMPLE][1] - mid_lm[RIGHT_TEMPLE][1]) * 20  # roll

        # Behavioral features (not available from video, use defaults + noise)
        X_features[i, 16] = np.clip(np.random.normal(0.15, 0.1), 0, 1)
        X_features[i, 17] = np.clip(np.random.normal(0.3, 0.1), 0, 1)
        X_features[i, 18] = np.clip(np.random.normal(0.85, 0.1), 0, 1)
        X_features[i, 19] = np.clip(np.random.normal(1.0, 0.2), 0.5, 3)
        X_features[i, 20] = np.clip(np.random.normal(0.1, 0.08), 0, 1)

    return X_features, y_labels


def train_models(X: np.ndarray, y: np.ndarray, output_dir: str = MODEL_DIR,
                 X_test: np.ndarray = None, y_test: np.ndarray = None):
    """
    Train XGBoost models for each engagement dimension.
    Uses cross-validation and weighted loss for class imbalance.
    If X_test/y_test provided, reports held-out test accuracy.
    """
    import xgboost as xgb
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    import joblib
    import shap

    os.makedirs(output_dir, exist_ok=True)

    results = {}

    for dim_idx, dim_name in enumerate(DIMENSION_NAMES):
        print(f"\n{'='*60}")
        print(f"Training model for: {dim_name.upper()}")
        print(f"{'='*60}")

        y_dim = y[:, dim_idx]

        # Class weight computation for imbalance (DAiSEE is imbalanced)
        classes, counts = np.unique(y_dim, return_counts=True)
        total = len(y_dim)
        weights = {c: total / (len(classes) * count) for c, count in zip(classes, counts)}
        sample_weights = np.array([weights[label] for label in y_dim])

        print(f"Class distribution: {dict(zip(classes.astype(int), counts))}")
        print(f"Sample weights: {weights}")

        # XGBoost model
        model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            gamma=0.1,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective='multi:softmax',
            num_class=4,
            eval_metric='mlogloss',
            random_state=42,
            n_jobs=-1,
            use_label_encoder=False,
        )

        # Cross-validation
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = []
        for train_idx, val_idx in skf.split(X, y_dim):
            X_cv_train, X_cv_val = X[train_idx], X[val_idx]
            y_cv_train, y_cv_val = y_dim[train_idx], y_dim[val_idx]
            sw_cv = sample_weights[train_idx]
            model_cv = xgb.XGBClassifier(**model.get_params())
            model_cv.fit(X_cv_train, y_cv_train, sample_weight=sw_cv)
            cv_scores.append(accuracy_score(y_cv_val, model_cv.predict(X_cv_val)))
        cv_scores = np.array(cv_scores)
        print(f"CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # Train on full data
        model.fit(X, y_dim, sample_weight=sample_weights)

        # Evaluate on training set (will report CV score above for real eval)
        y_pred = model.predict(X)
        train_acc = accuracy_score(y_dim, y_pred)
        train_f1 = f1_score(y_dim, y_pred, average='weighted')

        print(f"Train Accuracy: {train_acc:.4f}")
        print(f"Train F1 (weighted): {train_f1:.4f}")
        print(f"\nClassification Report:")
        print(classification_report(y_dim, y_pred, zero_division=0))

        # Feature importance
        importance = model.feature_importances_
        top_features = sorted(
            zip(FEATURE_NAMES, importance),
            key=lambda x: x[1], reverse=True
        )[:10]
        print(f"Top features for {dim_name}:")
        for feat, imp in top_features:
            print(f"  {feat}: {imp:.4f}")

        # Save model
        model_path = os.path.join(output_dir, f"xgb_{dim_name}.joblib")
        joblib.dump(model, model_path)
        print(f"Model saved to: {model_path}")

        # Test set evaluation
        test_acc = None
        test_f1 = None
        if X_test is not None and y_test is not None:
            y_test_dim = y_test[:, dim_idx]
            y_test_pred = model.predict(X_test)
            test_acc = accuracy_score(y_test_dim, y_test_pred)
            test_f1 = f1_score(y_test_dim, y_test_pred, average='weighted')
            print(f"\n*** TEST SET ***")
            print(f"Test Accuracy: {test_acc:.4f}")
            print(f"Test F1 (weighted): {test_f1:.4f}")
            print(classification_report(y_test_dim, y_test_pred, zero_division=0))

        # SHAP analysis
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X[:100])

        results[dim_name] = {
            "cv_accuracy": float(cv_scores.mean()),
            "cv_std": float(cv_scores.std()),
            "train_accuracy": float(train_acc),
            "train_f1": float(train_f1),
            "test_accuracy": float(test_acc) if test_acc is not None else None,
            "test_f1": float(test_f1) if test_f1 is not None else None,
            "top_features": [(f, float(i)) for f, i in top_features],
        }

    # Save training metadata
    metadata = {
        "trained_at": datetime.now().isoformat(),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "feature_names": FEATURE_NAMES,
        "dimension_names": DIMENSION_NAMES,
        "results": results,
    }
    with open(os.path.join(output_dir, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n{'='*60}")
    print(f"ALL MODELS TRAINED SUCCESSFULLY")
    print(f"{'='*60}")
    for dim, res in results.items():
        print(f"  {dim}: CV={res['cv_accuracy']:.4f} +/- {res['cv_std']:.4f}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Train engagement models")
    parser.add_argument("--data_dir", type=str, default=None,
                       help="Path to mediapipe_processed directory with .npy files")
    parser.add_argument("--synthetic", action="store_true",
                       help="Use synthetic data for bootstrapping")
    parser.add_argument("--n_samples", type=int, default=5000,
                       help="Number of synthetic samples")
    args = parser.parse_args()

    if args.data_dir and os.path.exists(args.data_dir):
        print("Loading extracted MediaPipe data...")
        X_train = np.load(os.path.join(args.data_dir, "X_train.npy"))
        y_train = np.load(os.path.join(args.data_dir, "y_train.npy"))

        print(f"Raw landmarks: X={X_train.shape}, y={y_train.shape}")
        print("Converting landmarks to engineered features...")
        X_features, y_labels = features_from_landmarks(X_train, y_train)
        print(f"Engineered features: X={X_features.shape}")

        # If validation data exists, append it to training
        val_path = os.path.join(args.data_dir, "X_val.npy")
        if os.path.exists(val_path):
            X_val = np.load(val_path)
            y_val = np.load(os.path.join(args.data_dir, "y_val.npy"))
            X_val_feat, y_val_labels = features_from_landmarks(X_val, y_val)
            X_features = np.vstack([X_features, X_val_feat])
            y_labels = np.vstack([y_labels, y_val_labels])
            print(f"With validation: X={X_features.shape}")

        # Load test set if available
        X_test_feat, y_test_labels = None, None
        test_path = os.path.join(args.data_dir, "X_test.npy")
        if os.path.exists(test_path):
            X_test = np.load(test_path)
            y_test = np.load(os.path.join(args.data_dir, "y_test.npy"))
            print(f"Test set: X={X_test.shape}, y={y_test.shape}")
            X_test_feat, y_test_labels = features_from_landmarks(X_test, y_test)
            print(f"Test features: X={X_test_feat.shape}")

    elif args.synthetic:
        print(f"Generating {args.n_samples} synthetic training samples...")
        X_features, y_labels = generate_synthetic_dataset(args.n_samples)
        X_test_feat, y_test_labels = None, None
        print(f"Synthetic data: X={X_features.shape}, y={y_labels.shape}")
    else:
        print("No data source specified. Using synthetic data (5000 samples).")
        X_features, y_labels = generate_synthetic_dataset(5000)
        X_test_feat, y_test_labels = None, None

    train_models(X_features, y_labels, X_test=X_test_feat, y_test=y_test_labels)


if __name__ == "__main__":
    main()
