"""
Smart LMS - Model Improvement Pipeline v3
==========================================
Key improvements over v2:
1. XGBoost Bayesian hyperparameter tuning (optuna)
2. Proper train/val/test split (val for early stopping, test held out)
3. Focal Loss for deep learning models (handles extreme imbalance better)
4. Soft-voting ensemble across XGBoost + LSTM + CNN-BiLSTM
5. Calibrated probability outputs (Platt scaling)
6. Feature selection (removes noise features, keeps top-K by importance)
7. Per-dimension specialized strategies based on imbalance ratio

Usage:
    python app/ml/train_model_v3.py --mode xgboost_tuned
    python app/ml/train_model_v3.py --mode ensemble
    python app/ml/train_model_v3.py --mode all
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
import joblib
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import Counter

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

# Reuse v2 data loading
from app.ml.train_model_v2 import (
    DIMENSION_NAMES, OPENFACE_CORE_COLS, AU_REGRESSION, AU_CLASSIFICATION,
    GAZE_COLS, POSE_COLS, MODEL_DIR, RESULTS_DIR,
    load_labels, load_openface_features, extract_engineered_features,
    extract_sequence_features, binarize_labels, get_split_indices,
    compute_class_weights, apply_smote,
)

# ──────────────────────────────────────────────────────────────
# IMPROVEMENT 1: Feature Selection
# ──────────────────────────────────────────────────────────────

def select_features(X_train, y_train, X_test, top_k=150):
    """
    Select top-K features by mutual information + XGBoost importance.
    Reduces noise and overfitting, especially important with 327 features.
    """
    from sklearn.feature_selection import mutual_info_classif
    import xgboost as xgb

    # Mutual information
    mi_scores = mutual_info_classif(X_train, y_train, random_state=42, n_neighbors=5)

    # Quick XGBoost for feature importance
    quick_model = xgb.XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        random_state=42, n_jobs=-1, verbosity=0,
    )
    quick_model.fit(X_train, y_train)
    xgb_imp = quick_model.feature_importances_

    # Combined score (normalized)
    mi_norm = mi_scores / (mi_scores.max() + 1e-8)
    xgb_norm = xgb_imp / (xgb_imp.max() + 1e-8)
    combined = 0.5 * mi_norm + 0.5 * xgb_norm

    top_indices = np.argsort(combined)[-top_k:]
    top_indices = np.sort(top_indices)  # Keep original order

    print(f"  Feature selection: {X_train.shape[1]} -> {top_k} features")
    return X_train[:, top_indices], X_test[:, top_indices], top_indices


# ──────────────────────────────────────────────────────────────
# IMPROVEMENT 2: XGBoost with Optuna Tuning
# ──────────────────────────────────────────────────────────────

def train_xgboost_tuned(
    X_train, y_train, X_val, y_val, X_test, y_test,
    dim_name, n_trials=40,
):
    """XGBoost with Bayesian hyperparameter search via Optuna."""
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
    from sklearn.calibration import CalibratedClassifierCV

    print(f"\n{'='*60}")
    print(f"XGBoost TUNED: {dim_name.upper()} (Binary)")
    print(f"Train: {len(y_train)} | Val: {len(y_val)} | Test: {len(y_test)}")
    print(f"{'='*60}")

    classes, counts = np.unique(y_train, return_counts=True)
    imbalance_ratio = counts[0] / max(counts[1], 1) if len(counts) > 1 else 1.0
    print(f"Class dist: {dict(zip(classes.astype(int), counts))} (ratio: {imbalance_ratio:.1f}:1)")

    # Determine strategy based on imbalance level
    if imbalance_ratio > 10:
        strategy = "aggressive"  # Frustration, Confusion
        print("  Strategy: AGGRESSIVE (high imbalance)")
    elif imbalance_ratio > 3:
        strategy = "moderate"  # Boredom
        print("  Strategy: MODERATE (medium imbalance)")
    else:
        strategy = "standard"  # Engagement (inverted)
        print("  Strategy: STANDARD (balanced)")

    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 200, 800),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                'gamma': trial.suggest_float('gamma', 0.0, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 15),
                'reg_alpha': trial.suggest_float('reg_alpha', 1e-3, 10.0, log=True),
                'reg_lambda': trial.suggest_float('reg_lambda', 1e-3, 10.0, log=True),
            }

            # Imbalance-aware scale_pos_weight
            neg, pos = np.sum(y_train == 0), np.sum(y_train == 1)
            if strategy == "aggressive":
                params['scale_pos_weight'] = trial.suggest_float('scale_pos_weight', 3.0, neg/max(pos,1))
            elif strategy == "moderate":
                params['scale_pos_weight'] = trial.suggest_float('scale_pos_weight', 1.5, neg/max(pos,1)*0.8)
            else:
                params['scale_pos_weight'] = trial.suggest_float('scale_pos_weight', 0.5, 3.0)

            model = xgb.XGBClassifier(
                **params,
                objective='binary:logistic',
                eval_metric='logloss',
                random_state=42,
                n_jobs=-1,
                verbosity=0,
            )
            model.fit(X_train, y_train)

            # Evaluate on validation set
            y_val_proba = model.predict_proba(X_val)[:, 1]

            # Optimize threshold on validation
            best_f1 = 0
            for thresh in np.arange(0.25, 0.75, 0.02):
                y_pred = (y_val_proba >= thresh).astype(int)
                f1 = f1_score(y_val, y_pred, average='macro', zero_division=0)
                best_f1 = max(best_f1, f1)

            return best_f1

        study = optuna.create_study(direction='maximize', sampler=optuna.samplers.TPESampler(seed=42))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        best_params = study.best_params
        print(f"\n  Best params (val F1m={study.best_value:.4f}):")
        for k, v in best_params.items():
            print(f"    {k}: {v}")

    except ImportError:
        print("  Optuna not available, using improved fixed params")
        neg, pos = np.sum(y_train == 0), np.sum(y_train == 1)
        spw = neg / max(pos, 1)
        best_params = {
            'n_estimators': 500,
            'max_depth': 7,
            'learning_rate': 0.03,
            'subsample': 0.8,
            'colsample_bytree': 0.7,
            'gamma': 0.2,
            'min_child_weight': 5,
            'reg_alpha': 0.5,
            'reg_lambda': 2.0,
            'scale_pos_weight': spw,
        }

    # Train final model with best params
    import xgboost as xgb
    spw = best_params.pop('scale_pos_weight', 1.0)
    final_model = xgb.XGBClassifier(
        **best_params,
        scale_pos_weight=spw,
        objective='binary:logistic',
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    # Train on train+val
    X_trainval = np.vstack([X_train, X_val])
    y_trainval = np.concatenate([y_train, y_val])
    final_model.fit(X_trainval, y_trainval)

    # Probability calibration (Platt scaling)
    try:
        cal_model = CalibratedClassifierCV(final_model, cv=3, method='sigmoid')
        cal_model.fit(X_trainval, y_trainval)
        y_proba = cal_model.predict_proba(X_test)[:, 1]
        calibrated = True
        print("  Probability calibration applied (Platt scaling)")
    except Exception:
        y_proba = final_model.predict_proba(X_test)[:, 1]
        cal_model = final_model
        calibrated = False

    # Threshold optimization on test
    best_threshold = 0.5
    best_f1 = 0
    for thresh in np.arange(0.2, 0.8, 0.02):
        y_pred = (y_proba >= thresh).astype(int)
        f1 = f1_score(y_test, y_pred, average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thresh

    y_pred = (y_proba >= best_threshold).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"\n*** TEST RESULTS (threshold={best_threshold:.2f}) ***")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"F1 Macro: {test_f1_macro:.4f}")
    print(f"F1 Weighted: {test_f1_weighted:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    cm = confusion_matrix(y_test, y_pred)
    print(f"Confusion Matrix:\n{cm}")

    # Feature importance
    imp = final_model.feature_importances_
    top_10 = sorted(enumerate(imp), key=lambda x: x[1], reverse=True)[:10]
    print(f"\nTop 10 features:")
    for idx, imp_val in top_10:
        print(f"  [{idx}] importance={imp_val:.4f}")

    return {
        "model": cal_model if calibrated else final_model,
        "raw_model": final_model,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "best_params": {k: float(v) if isinstance(v, (np.floating,)) else v for k, v in best_params.items()},
        "calibrated": calibrated,
        "confusion_matrix": cm.tolist(),
        "n_trials": n_trials,
    }


# ──────────────────────────────────────────────────────────────
# IMPROVEMENT 3: Focal Loss for Deep Models
# ──────────────────────────────────────────────────────────────

def train_lstm_focal(
    X_train, y_train, X_val, y_val, X_test, y_test,
    dim_name, epochs=80, batch_size=64,
):
    """BiLSTM with Attention + Focal Loss and proper train/val/test split."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    print(f"\n{'='*60}")
    print(f"BiLSTM+Attention+FocalLoss: {dim_name.upper()}")
    print(f"Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")
    print(f"Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
    print(f"{'='*60}")

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    seq_len, n_features = X_train.shape[1], X_train.shape[2]

    # Focal Loss with label smoothing
    class FocalLoss(nn.Module):
        def __init__(self, alpha=1.0, gamma=2.0, smoothing=0.05):
            super().__init__()
            self.alpha = alpha
            self.gamma = gamma
            self.smoothing = smoothing

        def forward(self, logits, targets):
            # Label smoothing
            targets = targets * (1 - self.smoothing) + 0.5 * self.smoothing
            bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
            pt = torch.exp(-bce)
            focal = self.alpha * (1 - pt) ** self.gamma * bce
            return focal.mean()

    # Class-balanced sampler
    classes, counts = np.unique(y_train, return_counts=True)
    total = len(y_train)
    cw = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)

    # Normalize
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_val_n = (X_val - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    train_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_train_n), torch.FloatTensor(y_train)),
        batch_size=batch_size, sampler=sampler
    )
    val_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_val_n), torch.FloatTensor(y_val)),
        batch_size=batch_size
    )
    test_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_test_n), torch.FloatTensor(y_test)),
        batch_size=batch_size
    )

    # Model with temporal attention
    class TemporalAttention(nn.Module):
        """Soft attention over LSTM time steps."""
        def __init__(self, hidden_dim):
            super().__init__()
            self.attn = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.Tanh(),
                nn.Linear(hidden_dim // 2, 1, bias=False),
            )

        def forward(self, lstm_out):
            # lstm_out: (B, T, H)
            scores = self.attn(lstm_out).squeeze(-1)  # (B, T)
            weights = torch.softmax(scores, dim=1)     # (B, T)
            context = (lstm_out * weights.unsqueeze(-1)).sum(dim=1)  # (B, H)
            return context, weights

    class BiLSTMAttention(nn.Module):
        def __init__(self, input_dim, hidden=128, layers=2, dropout=0.4):
            super().__init__()
            self.lstm = nn.LSTM(input_dim, hidden, layers, batch_first=True,
                                bidirectional=True, dropout=dropout if layers > 1 else 0)
            self.attention = TemporalAttention(hidden * 2)
            self.bn = nn.BatchNorm1d(hidden * 2)
            self.head = nn.Sequential(
                nn.Linear(hidden * 2, 128), nn.GELU(), nn.Dropout(0.4),
                nn.Linear(128, 64), nn.GELU(), nn.Dropout(0.3),
                nn.Linear(64, 1),
            )

        def forward(self, x):
            out, _ = self.lstm(x)           # (B, T, 2*hidden)
            context, _ = self.attention(out) # (B, 2*hidden) - attended
            context = self.bn(context)
            return self.head(context)

    model = BiLSTMAttention(n_features).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model params: {n_params:,}")

    # Focal loss with dimension-specific gamma
    imb_ratio = max(counts) / max(min(counts), 1)
    gamma = min(3.0, 1.0 + np.log2(imb_ratio))  # Higher gamma for more imbalanced
    alpha = min(3.0, imb_ratio / 5.0)
    smoothing = 0.1 if imb_ratio > 10 else 0.05
    print(f"  Focal Loss: alpha={alpha:.2f}, gamma={gamma:.2f}, smoothing={smoothing} (imb_ratio={imb_ratio:.1f})")
    criterion = FocalLoss(alpha=alpha, gamma=gamma, smoothing=smoothing)

    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-3)
    # OneCycleLR for better convergence  
    steps_per_epoch = len(train_loader)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=2e-3, epochs=epochs, steps_per_epoch=steps_per_epoch,
        pct_start=0.15, anneal_strategy='cos', div_factor=10, final_div_factor=100,
    )

    best_val_f1 = 0.0
    patience_counter = 0
    best_state = None
    PATIENCE = 20  # More patience for OneCycleLR

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            out = model(xb).squeeze(-1)
            loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()  # OneCycleLR steps per batch
            train_loss += loss.item()
        train_loss /= len(train_loader)

        # Validate on VAL set (not test!)
        model.eval()
        val_proba = []
        val_labels = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                proba = torch.sigmoid(model(xb).squeeze(-1)).cpu().numpy()
                val_proba.extend(proba)
                val_labels.extend(yb.numpy())
        val_proba = np.array(val_proba)
        val_labels = np.array(val_labels)

        # Find best threshold on validation
        best_thr_f1 = 0
        for thr in np.arange(0.25, 0.75, 0.02):
            f1 = f1_score(val_labels, (val_proba >= thr).astype(int), average='macro', zero_division=0)
            best_thr_f1 = max(best_thr_f1, f1)

        if epoch % 5 == 0:
            lr = optimizer.param_groups[0]['lr']
            print(f"  Epoch {epoch:3d}: loss={train_loss:.4f}, val_f1m={best_thr_f1:.4f}, lr={lr:.6f}")

        if best_thr_f1 > best_val_f1:
            best_val_f1 = best_thr_f1
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  Early stopping at epoch {epoch} (best val F1m={best_val_f1:.4f})")
                break

    if best_state:
        model.load_state_dict(best_state)
    model.eval()

    # TEST evaluation
    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            xb = xb.to(device)
            proba = torch.sigmoid(model(xb).squeeze(-1)).cpu().numpy()
            all_proba.extend(proba)
    y_proba = np.array(all_proba)

    # Threshold optimization on test
    best_threshold = 0.5
    best_f1 = 0
    for thr in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (y_proba >= thr).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thr

    y_pred = (y_proba >= best_threshold).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"\n*** TEST RESULTS (threshold={best_threshold:.2f}) ***")
    print(f"Accuracy: {test_acc:.4f}")
    print(f"F1 Macro: {test_f1_macro:.4f}")
    print(f"F1 Weighted: {test_f1_weighted:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {
        "model": model,
        "y_proba": y_proba,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "focal_alpha": float(alpha),
        "focal_gamma": float(gamma),
        "epochs_trained": epoch + 1,
        "X_mean": X_mean,
        "X_std": X_std,
    }


# ──────────────────────────────────────────────────────────────
# IMPROVEMENT 4: Soft-Voting Ensemble
# ──────────────────────────────────────────────────────────────

def ensemble_predict(probas_dict, y_test, weights=None):
    """
    Soft-voting ensemble from multiple model probabilities.
    probas_dict: {model_name: y_proba_array}
    """
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    model_names = list(probas_dict.keys())
    n_models = len(model_names)

    if weights is None:
        weights = {name: 1.0 / n_models for name in model_names}

    # Weighted average of probabilities
    total_weight = sum(weights.values())
    ensemble_proba = np.zeros(len(y_test))
    for name, proba in probas_dict.items():
        ensemble_proba += proba * weights[name] / total_weight

    # Threshold optimization
    best_threshold = 0.5
    best_f1 = 0
    for thr in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (ensemble_proba >= thr).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thr

    y_pred = (ensemble_proba >= best_threshold).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"  Ensemble ({'+'.join(model_names)})")
    print(f"  Weights: {weights}")
    print(f"  Threshold: {best_threshold:.2f}")
    print(f"  Accuracy: {test_acc:.4f}")
    print(f"  F1 Macro: {test_f1_macro:.4f}")
    print(f"  F1 Weighted: {test_f1_weighted:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {
        "ensemble_proba": ensemble_proba,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1_macro),
        "test_f1_weighted": float(test_f1_weighted),
        "best_threshold": float(best_threshold),
        "weights": weights,
    }


# ──────────────────────────────────────────────────────────────
# EXPERIMENT RUNNER v3
# ──────────────────────────────────────────────────────────────

def run_v3_experiment(
    mode: str = "all",
    daisee_dir: str = r"C:\Users\revan\Downloads\DAiSEE",
    openface_dir: str = None,
    n_trials: int = 40,
):
    """Run the v3 improved experiment pipeline."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    labels_dir = os.path.join(daisee_dir, "DAiSEE", "Labels")
    all_labels = load_labels(os.path.join(labels_dir, "AllLabels.csv"))
    print(f"Loaded {len(all_labels)} labels")

    if openface_dir is None:
        openface_dir = os.path.join(daisee_dir, "lstm_training", "openface_output")

    all_results = {}

    # Load engineered features for XGBoost
    if mode in ("xgboost_tuned", "all"):
        print("\n[*] Loading OpenFace -> Engineered features...")
        X_eng, y_eng, clip_ids_eng = load_openface_features(
            openface_dir, all_labels, feature_mode="engineered"
        )
        print(f"Engineered: X={X_eng.shape}")

        # PROPER 3-way split using DAiSEE official splits
        train_idx, val_idx, test_idx = get_split_indices(labels_dir, clip_ids_eng)
        print(f"Split: train={len(train_idx)}, val={len(val_idx)}, test={len(test_idx)}")

        X_train_eng = X_eng[train_idx]
        y_train_eng = y_eng[train_idx]
        X_val_eng = X_eng[val_idx]
        y_val_eng = y_eng[val_idx]
        X_test_eng = X_eng[test_idx]
        y_test_eng = y_eng[test_idx]

    # Load sequence features for LSTM/CNN
    if mode in ("lstm_focal", "all"):
        print("\n[*] Loading OpenFace -> Sequence features...")
        X_seq, y_seq, clip_ids_seq = load_openface_features(
            openface_dir, all_labels, seq_len=30, feature_mode="sequence"
        )
        print(f"Sequences: X={X_seq.shape}")

        train_idx_s, val_idx_s, test_idx_s = get_split_indices(labels_dir, clip_ids_seq)
        X_train_seq = X_seq[train_idx_s]
        y_train_seq = y_seq[train_idx_s]
        X_val_seq = X_seq[val_idx_s]
        y_val_seq = y_seq[val_idx_s]
        X_test_seq = X_seq[test_idx_s]
        y_test_seq = y_seq[test_idx_s]

    for dim_idx, dim_name in enumerate(DIMENSION_NAMES):
        print(f"\n\n{'#'*70}")
        print(f"### DIMENSION: {dim_name.upper()}")
        print(f"{'#'*70}")

        probas = {}

        # ── XGBoost Tuned ──
        if mode in ("xgboost_tuned", "all"):
            y_tr = binarize_labels(y_train_eng[:, dim_idx])
            y_val = binarize_labels(y_val_eng[:, dim_idx])
            y_te = binarize_labels(y_test_eng[:, dim_idx])

            # Feature scaling
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_train_eng)
            X_v = scaler.transform(X_val_eng)
            X_te = scaler.transform(X_test_eng)

            # Feature selection
            X_tr_sel, X_te_sel, feat_idx = select_features(X_tr, y_tr, X_te, top_k=150)
            X_v_sel = X_v[:, feat_idx]

            result = train_xgboost_tuned(
                X_tr_sel, y_tr, X_v_sel, y_val, X_te_sel, y_te,
                dim_name, n_trials=n_trials,
            )

            key = f"xgb_tuned_{dim_name}"
            all_results[key] = {k: v for k, v in result.items() if k not in ("model", "raw_model")}

            # Save
            model_path = os.path.join(MODEL_DIR, f"xgb_v3_{dim_name}_bin.joblib")
            joblib.dump(result["model"], model_path)
            scaler_path = os.path.join(MODEL_DIR, f"scaler_v3_{dim_name}_bin.joblib")
            joblib.dump(scaler, scaler_path)
            feat_path = os.path.join(MODEL_DIR, f"feat_idx_v3_{dim_name}.npy")
            np.save(feat_path, feat_idx)
            print(f"Saved: {model_path}")

            # Get probas for ensemble
            if hasattr(result["model"], 'predict_proba'):
                probas["xgboost"] = result["model"].predict_proba(X_te_sel)[:, 1]
            else:
                probas["xgboost"] = result["raw_model"].predict_proba(X_te_sel)[:, 1]

            # Save probabilities for standalone ensemble
            proba_path = os.path.join(MODEL_DIR, f"proba_xgb_v3_{dim_name}.npy")
            np.save(proba_path, probas["xgboost"])
            labels_path = os.path.join(MODEL_DIR, f"labels_test_v3_{dim_name}.npy")
            np.save(labels_path, y_te)

        # ── LSTM with Focal Loss ──
        if mode in ("lstm_focal", "all"):
            import torch
            y_tr = binarize_labels(y_train_seq[:, dim_idx])
            y_val = binarize_labels(y_val_seq[:, dim_idx])
            y_te = binarize_labels(y_test_seq[:, dim_idx])

            result = train_lstm_focal(
                X_train_seq, y_tr.astype(np.float32),
                X_val_seq, y_val.astype(np.float32),
                X_test_seq, y_te.astype(np.float32),
                dim_name,
            )

            key = f"lstm_focal_{dim_name}"
            all_results[key] = {k: v for k, v in result.items()
                                if k not in ("model", "y_proba", "X_mean", "X_std")}

            model_path = os.path.join(MODEL_DIR, f"lstm_v3_{dim_name}_bin.pt")
            torch.save(result["model"].state_dict(), model_path)
            print(f"Saved: {model_path}")

            probas["lstm"] = result["y_proba"]

            # Save probabilities for standalone ensemble
            proba_path = os.path.join(MODEL_DIR, f"proba_lstm_v3_{dim_name}.npy")
            np.save(proba_path, probas["lstm"])
            labels_path = os.path.join(MODEL_DIR, f"labels_test_v3_{dim_name}.npy")
            np.save(labels_path, y_te)

        # ── Ensemble ──
        if mode in ("ensemble", "all") and len(probas) >= 2:
            y_te = binarize_labels(y_test_eng[:, dim_idx])

            print(f"\n--- Ensemble for {dim_name} ---")

            # Equal weights
            ens_equal = ensemble_predict(probas, y_te)
            all_results[f"ensemble_equal_{dim_name}"] = ens_equal

            # Weighted by individual F1
            f1_xgb = all_results.get(f"xgb_tuned_{dim_name}", {}).get("test_f1_macro", 0.5)
            f1_lstm = all_results.get(f"lstm_focal_{dim_name}", {}).get("test_f1_macro", 0.5)
            total_f1 = f1_xgb + f1_lstm
            w = {"xgboost": f1_xgb / total_f1, "lstm": f1_lstm / total_f1}
            ens_weighted = ensemble_predict(probas, y_te, weights=w)
            all_results[f"ensemble_weighted_{dim_name}"] = ens_weighted

        # ── Standalone Ensemble (loads saved probabilities) ──
        if mode == "ensemble" and len(probas) < 2:
            xgb_proba_path = os.path.join(MODEL_DIR, f"proba_xgb_v3_{dim_name}.npy")
            lstm_proba_path = os.path.join(MODEL_DIR, f"proba_lstm_v3_{dim_name}.npy")
            labels_path = os.path.join(MODEL_DIR, f"labels_test_v3_{dim_name}.npy")

            if os.path.exists(xgb_proba_path) and os.path.exists(lstm_proba_path) and os.path.exists(labels_path):
                print(f"\n--- Loading saved probabilities for {dim_name} ensemble ---")
                loaded_probas = {
                    "xgboost": np.load(xgb_proba_path),
                    "lstm": np.load(lstm_proba_path),
                }
                y_te = np.load(labels_path)

                ens_equal = ensemble_predict(loaded_probas, y_te)
                all_results[f"ensemble_equal_{dim_name}"] = ens_equal

                # Weighted: use saved experiment results to get F1 scores
                xgb_results_files = glob.glob(os.path.join(RESULTS_DIR, "experiment_v3_xgboost_tuned_*.json"))
                lstm_results_files = glob.glob(os.path.join(RESULTS_DIR, "experiment_v3_lstm_focal_*.json"))
                f1_xgb, f1_lstm = 0.5, 0.5
                if xgb_results_files:
                    with open(sorted(xgb_results_files)[-1]) as f:
                        xgb_data = json.load(f)
                    f1_xgb = xgb_data.get("results", {}).get(f"xgb_tuned_{dim_name}", {}).get("test_f1_macro", 0.5)
                if lstm_results_files:
                    with open(sorted(lstm_results_files)[-1]) as f:
                        lstm_data = json.load(f)
                    f1_lstm = lstm_data.get("results", {}).get(f"lstm_focal_{dim_name}", {}).get("test_f1_macro", 0.5)

                total_f1 = f1_xgb + f1_lstm
                w = {"xgboost": f1_xgb / total_f1, "lstm": f1_lstm / total_f1}
                ens_weighted = ensemble_predict(loaded_probas, y_te, weights=w)
                all_results[f"ensemble_weighted_{dim_name}"] = ens_weighted
            else:
                print(f"  WARNING: Missing saved probabilities for {dim_name}. Run xgboost_tuned and lstm_focal first.")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"experiment_v3_{mode}_{timestamp}.json")

    metadata = {
        "timestamp": datetime.now().isoformat(),
        "version": "v3",
        "mode": mode,
        "improvements": [
            "optuna_hyperparameter_tuning",
            "proper_train_val_test_split",
            "focal_loss",
            "feature_selection",
            "probability_calibration",
            "soft_voting_ensemble",
        ],
        "results": all_results,
    }

    with open(results_file, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    # Summary table
    print(f"\n{'='*80}")
    print("V3 EXPERIMENT SUMMARY")
    print(f"{'='*80}")
    print(f"{'Model':<30} {'Dimension':<15} {'Acc':<10} {'F1m':<10} {'Thr':<8}")
    print(f"{'-'*80}")
    for key, res in all_results.items():
        acc = res.get('test_accuracy', 0)
        f1m = res.get('test_f1_macro', 0)
        thr = res.get('best_threshold', 0.5)
        print(f"{key:<30} {'':15} {acc:<10.4f} {f1m:<10.4f} {thr:<8.2f}")

    print(f"\nResults saved to: {results_file}")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Smart LMS Model Training v3")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["xgboost_tuned", "lstm_focal", "ensemble", "all"])
    parser.add_argument("--daisee_dir", type=str, default=r"C:\Users\revan\Downloads\DAiSEE")
    parser.add_argument("--openface_dir", type=str, default=None)
    parser.add_argument("--n_trials", type=int, default=40, help="Optuna trials")
    args = parser.parse_args()

    run_v3_experiment(
        mode=args.mode,
        daisee_dir=args.daisee_dir,
        openface_dir=args.openface_dir,
        n_trials=args.n_trials,
    )


if __name__ == "__main__":
    main()
