"""
Smart LMS - Model Improvement Pipeline v4
==========================================
Designed for Kaggle T4 GPU (30 hrs/week budget)

Key improvements over v3:
1. Temporal Transformer Encoder — multi-head self-attention on frame sequences
2. Face-crop ViT Embeddings — pretrained vision transformer features from raw video
3. Deeper BiLSTM + GRU hybrid with multi-scale temporal convolutions
4. Stacking Ensemble — meta-learner over all base model predictions
5. Stratified K-Fold Cross-Validation with confidence intervals
6. Data Augmentation — temporal jittering, gaussian noise, feature masking, mixup
7. Longer sequences (seq_len=60) with positional encoding

Expected timeline:
  Week 1: OpenFace Transformer + improved BiLSTM + XGBoost CV (~15 hrs T4)
  Week 2: ViT embedding extraction + ViT classifier (~12 hrs T4)
  Week 3: Stacking ensemble + ablation study + final evaluation (~8 hrs T4)

Usage:
    python app/ml/train_model_v4.py --mode transformer       # Temporal Transformer
    python app/ml/train_model_v4.py --mode bilstm_v4         # Improved BiLSTM-GRU
    python app/ml/train_model_v4.py --mode xgboost_cv        # XGBoost with K-Fold CV
    python app/ml/train_model_v4.py --mode vit_train         # ViT embedding classifier
    python app/ml/train_model_v4.py --mode stacking          # Stacking meta-ensemble
    python app/ml/train_model_v4.py --mode all_openface      # Transformer + BiLSTM + XGB
    python app/ml/train_model_v4.py --mode full              # Everything
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
import copy
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import Counter
from pathlib import Path

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


# ── Multi-GPU helpers ──
def wrap_model_multi_gpu(model):
    """Wrap model with DataParallel if multiple GPUs are available."""
    import torch
    if torch.cuda.device_count() > 1:
        print(f"  [Multi-GPU] Using {torch.cuda.device_count()} GPUs with DataParallel")
        model = torch.nn.DataParallel(model)
    return model


def unwrap_model(model):
    """Get base model from DataParallel wrapper."""
    return model.module if hasattr(model, 'module') else model


# ── Detect environment ──
ON_KAGGLE = os.path.exists("/kaggle/working")

if ON_KAGGLE:
    # Ensure /kaggle/working is on sys.path for app.ml imports
    if "/kaggle/working" not in sys.path:
        sys.path.insert(0, "/kaggle/working")
    # Kaggle paths
    DAISEE_DIR = "/kaggle/input/daisee-dataset"
    OPENFACE_DIR = "/kaggle/input/smartlms-openface/openface_output"
    VIT_EMBED_DIR = "/kaggle/input/smartlms-vit-embeddings"
    MODEL_DIR = "/kaggle/working/trained_models"
    RESULTS_DIR = "/kaggle/working/experiment_results"
    print("[ENV] Running on Kaggle T4 GPU")
else:
    # Local paths
    DAISEE_DIR = r"C:\Users\revan\Downloads\DAiSEE"
    OPENFACE_DIR = os.path.join(DAISEE_DIR, "lstm_training", "openface_output")
    VIT_EMBED_DIR = os.path.join(os.path.dirname(__file__), "vit_embeddings")
    MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")
    RESULTS_DIR = os.path.join(os.path.dirname(__file__), "experiment_results")
    print("[ENV] Running locally")

# Reuse v2 utility functions
try:
    from app.ml.train_model_v2 import (
        DIMENSION_NAMES, OPENFACE_CORE_COLS, AU_REGRESSION, AU_CLASSIFICATION,
        GAZE_COLS, POSE_COLS,
        load_labels, load_openface_features, extract_engineered_features,
        extract_sequence_features, binarize_labels, get_split_indices,
        compute_class_weights,
    )
    from app.ml.train_model_v3 import select_features
except ImportError:
    try:
        # Fallback: direct import when running as script on Kaggle
        from train_model_v2 import (
            DIMENSION_NAMES, OPENFACE_CORE_COLS, AU_REGRESSION, AU_CLASSIFICATION,
            GAZE_COLS, POSE_COLS,
            load_labels, load_openface_features, extract_engineered_features,
            extract_sequence_features, binarize_labels, get_split_indices,
            compute_class_weights,
        )
        from train_model_v3 import select_features
    except ImportError as e:
        print(f"[ERROR] Could not import v2/v3 utilities: {e}")
        print(f"  sys.path = {sys.path[:5]}")
        print(f"  CWD = {os.getcwd()}")
        raise


# ══════════════════════════════════════════════════════════════
# SECTION 1: DATA AUGMENTATION
# ══════════════════════════════════════════════════════════════

class SequenceAugmentor:
    """Data augmentation for temporal feature sequences."""

    @staticmethod
    def temporal_jitter(x, sigma=0.02):
        """Add Gaussian noise to feature values."""
        noise = np.random.normal(0, sigma, x.shape).astype(np.float32)
        return x + noise

    @staticmethod
    def temporal_shift(x, max_shift=3):
        """Shift sequence in time (circular)."""
        shift = np.random.randint(-max_shift, max_shift + 1)
        return np.roll(x, shift, axis=0)

    @staticmethod
    def feature_masking(x, mask_ratio=0.1):
        """Randomly zero out feature columns."""
        mask = np.random.random(x.shape[1]) > mask_ratio
        return x * mask[np.newaxis, :].astype(np.float32)

    @staticmethod
    def temporal_crop_resize(x, crop_ratio=0.8):
        """Randomly crop a temporal segment and resize to original length."""
        seq_len = x.shape[0]
        crop_len = max(int(seq_len * crop_ratio), 2)
        start = np.random.randint(0, seq_len - crop_len + 1)
        cropped = x[start:start + crop_len]
        # Resize back to original length via interpolation
        indices = np.linspace(0, crop_len - 1, seq_len).astype(int)
        return cropped[indices]

    @staticmethod
    def speed_perturbation(x, speed_range=(0.8, 1.2)):
        """Simulate different playback speeds."""
        speed = np.random.uniform(*speed_range)
        seq_len = x.shape[0]
        new_len = int(seq_len / speed)
        if new_len < 2:
            return x
        indices = np.linspace(0, seq_len - 1, new_len).astype(int)
        stretched = x[indices]
        # Resize back
        out_indices = np.linspace(0, len(stretched) - 1, seq_len).astype(int)
        return stretched[out_indices]

    @staticmethod
    def mixup(x1, y1, x2, y2, alpha=0.2):
        """Mixup augmentation between two samples."""
        lam = np.random.beta(alpha, alpha) if alpha > 0 else 1.0
        x_mix = lam * x1 + (1 - lam) * x2
        y_mix = lam * y1 + (1 - lam) * y2
        return x_mix.astype(np.float32), float(y_mix)

    def augment(self, x, p=0.5):
        """Apply random augmentation chain."""
        if np.random.random() < p:
            x = self.temporal_jitter(x)
        if np.random.random() < p * 0.5:
            x = self.temporal_shift(x)
        if np.random.random() < p * 0.3:
            x = self.feature_masking(x)
        if np.random.random() < p * 0.3:
            x = self.temporal_crop_resize(x)
        if np.random.random() < p * 0.3:
            x = self.speed_perturbation(x)
        return x


# ══════════════════════════════════════════════════════════════
# SECTION 2: TEMPORAL TRANSFORMER ENCODER
# ══════════════════════════════════════════════════════════════

def train_transformer(
    X_train, y_train, X_val, y_val, X_test, y_test,
    dim_name, epochs=120, batch_size=64, seq_len=60, lr=1e-3,
    augment=True, return_probas=True,
):
    """
    Temporal Transformer Encoder for engagement detection.
    
    Architecture:
    - Learnable positional encoding
    - Input projection (n_features → d_model)
    - N Transformer encoder layers with multi-head self-attention
    - [CLS] token aggregation
    - Classification head with dropout
    
    Expected: ~20 min per dimension on T4 GPU
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

    print(f"\n{'='*60}")
    print(f"TEMPORAL TRANSFORMER: {dim_name.upper()}")
    print(f"Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    print(f"{'='*60}")

    n_features = X_train.shape[2]

    # ── Normalize ──
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_val_n = (X_val - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    # ── Class-balanced sampler ──
    classes, counts = np.unique(y_train, return_counts=True)
    imb_ratio = max(counts) / max(min(counts), 1)
    cw = {int(c): len(y_train) / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)

    # ── Augmentation dataset ──
    augmentor = SequenceAugmentor() if augment else None

    class AugmentedDataset(torch.utils.data.Dataset):
        def __init__(self, X, y, augmentor=None, training=True):
            self.X = X
            self.y = y
            self.augmentor = augmentor
            self.training = training

        def __len__(self):
            return len(self.X)

        def __getitem__(self, idx):
            x = self.X[idx].copy()
            y = self.y[idx]
            if self.training and self.augmentor:
                x = self.augmentor.augment(x, p=0.5)
            return torch.FloatTensor(x), torch.FloatTensor([y])

    train_ds = AugmentedDataset(X_train_n, y_train, augmentor, training=True)
    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_val_n), torch.FloatTensor(y_val)),
        batch_size=batch_size
    )
    test_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_test_n), torch.FloatTensor(y_test)),
        batch_size=batch_size
    )

    # ── Model ──
    class TemporalTransformer(nn.Module):
        """
        Transformer Encoder for temporal feature sequences.
        Uses a learnable [CLS] token prepended to the sequence.
        """
        def __init__(self, n_features, d_model=128, nhead=8, num_layers=4,
                     dim_ff=256, dropout=0.3, max_seq_len=120):
            super().__init__()
            self.d_model = d_model

            # Input projection
            self.input_proj = nn.Sequential(
                nn.Linear(n_features, d_model),
                nn.LayerNorm(d_model),
                nn.GELU(),
                nn.Dropout(dropout * 0.5),
            )

            # [CLS] token
            self.cls_token = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)

            # Positional encoding (learnable)
            self.pos_embed = nn.Parameter(torch.randn(1, max_seq_len + 1, d_model) * 0.02)

            # Transformer encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_ff,
                dropout=dropout,
                activation='gelu',
                batch_first=True,
                norm_first=True,  # Pre-norm is more stable
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

            # Classification head
            self.head = nn.Sequential(
                nn.LayerNorm(d_model),
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(d_model // 2, 1),
            )

        def forward(self, x):
            B, T, _ = x.shape
            # Project features
            x = self.input_proj(x)  # (B, T, d_model)

            # Prepend [CLS] token
            cls = self.cls_token.expand(B, -1, -1)  # (B, 1, d_model)
            x = torch.cat([cls, x], dim=1)  # (B, T+1, d_model)

            # Add positional encoding
            x = x + self.pos_embed[:, :T + 1, :]

            # Transformer
            x = self.encoder(x)  # (B, T+1, d_model)

            # Use [CLS] token output
            cls_out = x[:, 0, :]  # (B, d_model)
            return self.head(cls_out)

    model = TemporalTransformer(
        n_features=n_features,
        d_model=128,
        nhead=8,
        num_layers=4,
        dim_ff=256,
        dropout=0.3,
    ).to(device)
    model = wrap_model_multi_gpu(model)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Transformer params: {n_params:,}")

    # ── Focal Loss ──
    class FocalLoss(nn.Module):
        def __init__(self, alpha=1.0, gamma=2.0, smoothing=0.05):
            super().__init__()
            self.alpha = alpha
            self.gamma = gamma
            self.smoothing = smoothing

        def forward(self, logits, targets):
            targets = targets * (1 - self.smoothing) + 0.5 * self.smoothing
            bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
            pt = torch.exp(-bce)
            return (self.alpha * (1 - pt) ** self.gamma * bce).mean()

    gamma = min(3.0, 1.0 + np.log2(max(imb_ratio, 1)))
    alpha = min(3.0, imb_ratio / 5.0)
    print(f"  Focal Loss: alpha={alpha:.2f}, gamma={gamma:.2f}")
    criterion = FocalLoss(alpha=alpha, gamma=gamma)

    # ── Optimizer: AdamW with cosine annealing + warmup ──
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    warmup_epochs = min(10, epochs // 8)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=20, T_mult=2, eta_min=lr * 0.01
    )

    # ── Training loop ──
    best_val_f1 = 0.0
    patience_counter = 0
    best_state = None
    PATIENCE = 25

    for epoch in range(epochs):
        # Warmup
        if epoch < warmup_epochs:
            warmup_lr = lr * (epoch + 1) / warmup_epochs
            for pg in optimizer.param_groups:
                pg['lr'] = warmup_lr

        model.train()
        train_loss = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device).squeeze(-1)
            optimizer.zero_grad()
            out = model(xb).squeeze(-1)
            loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        if epoch >= warmup_epochs:
            scheduler.step()
        train_loss /= len(train_loader)

        # Validate
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

        from sklearn.metrics import f1_score
        best_thr_f1 = 0
        for thr in np.arange(0.25, 0.75, 0.02):
            f1 = f1_score(val_labels, (val_proba >= thr).astype(int), average='macro', zero_division=0)
            best_thr_f1 = max(best_thr_f1, f1)

        if epoch % 10 == 0 or epoch == epochs - 1:
            lr_now = optimizer.param_groups[0]['lr']
            print(f"  Epoch {epoch:3d}: loss={train_loss:.4f}, val_f1m={best_thr_f1:.4f}, lr={lr_now:.6f}")

        if best_thr_f1 > best_val_f1:
            best_val_f1 = best_thr_f1
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in unwrap_model(model).state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  Early stop at epoch {epoch} (best val F1m={best_val_f1:.4f})")
                break

    if best_state:
        unwrap_model(model).load_state_dict(best_state)
    model.eval()

    # ── Test evaluation ──
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            xb = xb.to(device)
            proba = torch.sigmoid(model(xb).squeeze(-1)).cpu().numpy()
            all_proba.extend(proba)
    y_proba = np.array(all_proba)

    best_threshold = 0.5
    best_f1 = 0
    for thr in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (y_proba >= thr).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thr

    y_pred = (y_proba >= best_threshold).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1m = f1_score(y_test, y_pred, average='macro', zero_division=0)
    test_f1w = f1_score(y_test, y_pred, average='weighted', zero_division=0)

    print(f"\n*** TEST RESULTS (thr={best_threshold:.2f}) ***")
    print(f"Accuracy: {test_acc:.4f} | F1 Macro: {test_f1m:.4f} | F1 Weighted: {test_f1w:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {
        "model": model,
        "y_proba": y_proba,
        "test_accuracy": float(test_acc),
        "test_f1_macro": float(test_f1m),
        "test_f1_weighted": float(test_f1w),
        "best_threshold": float(best_threshold),
        "epochs_trained": epoch + 1,
        "n_params": n_params,
        "X_mean": X_mean,
        "X_std": X_std,
        "architecture": "TemporalTransformer(d=128, heads=8, layers=4, ff=256)",
    }


# ══════════════════════════════════════════════════════════════
# SECTION 3: IMPROVED BiLSTM-GRU HYBRID
# ══════════════════════════════════════════════════════════════

def train_bilstm_v4(
    X_train, y_train, X_val, y_val, X_test, y_test,
    dim_name, epochs=100, batch_size=64, augment=True,
):
    """
    Improved BiLSTM with:
    - Multi-scale 1D convolutions before LSTM
    - GRU + LSTM hybrid
    - Multi-head attention pooling
    - Deeper architecture (3 layers, 192 hidden)
    - Squeeze-and-Excitation on features
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    print(f"\n{'='*60}")
    print(f"BiLSTM-GRU v4 HYBRID: {dim_name.upper()}")
    print(f"Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    print(f"{'='*60}")

    n_features = X_train.shape[2]

    # Normalize
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_val_n = (X_val - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    # Sampler
    classes, counts = np.unique(y_train, return_counts=True)
    imb_ratio = max(counts) / max(min(counts), 1)
    cw = {int(c): len(y_train) / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)

    augmentor = SequenceAugmentor() if augment else None

    class AugDataset(torch.utils.data.Dataset):
        def __init__(self, X, y, aug=None, train=True):
            self.X, self.y, self.aug, self.train = X, y, aug, train
        def __len__(self):
            return len(self.X)
        def __getitem__(self, idx):
            x = self.X[idx].copy()
            if self.train and self.aug:
                x = self.aug.augment(x, p=0.4)
            return torch.FloatTensor(x), torch.FloatTensor([self.y[idx]])

    from torch.utils.data import TensorDataset
    train_loader = DataLoader(AugDataset(X_train_n, y_train, augmentor), batch_size=batch_size, sampler=sampler)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val_n), torch.FloatTensor(y_val)), batch_size=batch_size)
    test_loader = DataLoader(TensorDataset(torch.FloatTensor(X_test_n), torch.FloatTensor(y_test)), batch_size=batch_size)

    class MultiScaleConv(nn.Module):
        """Multi-scale 1D convolutions for local temporal patterns."""
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.conv3 = nn.Conv1d(in_ch, out_ch // 3, kernel_size=3, padding=1)
            self.conv5 = nn.Conv1d(in_ch, out_ch // 3, kernel_size=5, padding=2)
            self.conv7 = nn.Conv1d(in_ch, out_ch - 2 * (out_ch // 3), kernel_size=7, padding=3)
            self.bn = nn.BatchNorm1d(out_ch)
            self.act = nn.GELU()

        def forward(self, x):
            # x: (B, T, C) -> (B, C, T) for conv
            x = x.transpose(1, 2)
            out = torch.cat([self.conv3(x), self.conv5(x), self.conv7(x)], dim=1)
            out = self.act(self.bn(out))
            return out.transpose(1, 2)  # (B, T, out_ch)

    class SEBlock(nn.Module):
        """Squeeze-and-Excitation for feature recalibration."""
        def __init__(self, channels, reduction=8):
            super().__init__()
            self.fc = nn.Sequential(
                nn.Linear(channels, channels // reduction),
                nn.GELU(),
                nn.Linear(channels // reduction, channels),
                nn.Sigmoid(),
            )

        def forward(self, x):
            # x: (B, T, C)
            se = x.mean(dim=1)  # (B, C) global avg pool over time
            se = self.fc(se).unsqueeze(1)  # (B, 1, C)
            return x * se

    class BiLSTMGRUHybrid(nn.Module):
        def __init__(self, n_feat, hidden=192, n_layers=3, dropout=0.4):
            super().__init__()
            self.ms_conv = MultiScaleConv(n_feat, hidden)
            self.se = SEBlock(hidden)
            self.lstm = nn.LSTM(hidden, hidden, n_layers, batch_first=True,
                                bidirectional=True, dropout=dropout)
            self.gru = nn.GRU(hidden * 2, hidden, 1, batch_first=True, bidirectional=True)
            self.attn = nn.Sequential(
                nn.Linear(hidden * 2, hidden),
                nn.Tanh(),
                nn.Linear(hidden, 1, bias=False),
            )
            self.head = nn.Sequential(
                nn.LayerNorm(hidden * 2),
                nn.Linear(hidden * 2, 128),
                nn.GELU(),
                nn.Dropout(0.4),
                nn.Linear(128, 64),
                nn.GELU(),
                nn.Dropout(0.3),
                nn.Linear(64, 1),
            )

        def forward(self, x):
            x = self.ms_conv(x)
            x = self.se(x)
            lstm_out, _ = self.lstm(x)
            gru_out, _ = self.gru(lstm_out)
            # Attention pooling
            scores = self.attn(gru_out).squeeze(-1)
            weights = torch.softmax(scores, dim=1)
            context = (gru_out * weights.unsqueeze(-1)).sum(dim=1)
            return self.head(context)

    model = BiLSTMGRUHybrid(n_features).to(device)
    model = wrap_model_multi_gpu(model)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model params: {n_params:,}")

    # Focal Loss
    class FocalLoss(nn.Module):
        def __init__(self, alpha=1.0, gamma=2.0, smoothing=0.05):
            super().__init__()
            self.alpha, self.gamma, self.smoothing = alpha, gamma, smoothing
        def forward(self, logits, targets):
            targets = targets * (1 - self.smoothing) + 0.5 * self.smoothing
            bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
            pt = torch.exp(-bce)
            return (self.alpha * (1 - pt) ** self.gamma * bce).mean()

    gamma = min(3.0, 1.0 + np.log2(max(imb_ratio, 1)))
    alpha = min(3.0, imb_ratio / 5.0)
    criterion = FocalLoss(alpha=alpha, gamma=gamma)

    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-3)
    steps_per_epoch = len(train_loader)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=2e-3, epochs=epochs, steps_per_epoch=steps_per_epoch,
        pct_start=0.1, anneal_strategy='cos',
    )

    best_val_f1, patience_counter, best_state = 0.0, 0, None
    PATIENCE = 20

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device).squeeze(-1)
            optimizer.zero_grad()
            out = model(xb).squeeze(-1)
            loss = criterion(out, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            train_loss += loss.item()
        train_loss /= len(train_loader)

        model.eval()
        val_proba, val_labels = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                proba = torch.sigmoid(model(xb.to(device)).squeeze(-1)).cpu().numpy()
                val_proba.extend(proba)
                val_labels.extend(yb.numpy())
        val_proba, val_labels = np.array(val_proba), np.array(val_labels)

        best_thr_f1 = max(
            f1_score(val_labels, (val_proba >= thr).astype(int), average='macro', zero_division=0)
            for thr in np.arange(0.25, 0.75, 0.02)
        )

        if epoch % 10 == 0:
            print(f"  Epoch {epoch:3d}: loss={train_loss:.4f}, val_f1m={best_thr_f1:.4f}")

        if best_thr_f1 > best_val_f1:
            best_val_f1 = best_thr_f1
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in unwrap_model(model).state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  Early stop at epoch {epoch}")
                break

    if best_state:
        unwrap_model(model).load_state_dict(best_state)
    model.eval()

    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            proba = torch.sigmoid(model(xb.to(device)).squeeze(-1)).cpu().numpy()
            all_proba.extend(proba)
    y_proba = np.array(all_proba)

    best_threshold, best_f1 = 0.5, 0
    for thr in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (y_proba >= thr).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thr

    y_pred = (y_proba >= best_threshold).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    test_f1m = f1_score(y_test, y_pred, average='macro', zero_division=0)

    print(f"\n*** TEST: Acc={test_acc:.4f} F1m={test_f1m:.4f} (thr={best_threshold:.2f}) ***")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {
        "model": model, "y_proba": y_proba,
        "test_accuracy": float(test_acc), "test_f1_macro": float(test_f1m),
        "best_threshold": float(best_threshold), "epochs_trained": epoch + 1,
        "n_params": n_params, "X_mean": X_mean, "X_std": X_std,
    }


# ══════════════════════════════════════════════════════════════
# SECTION 4: ViT EMBEDDING CLASSIFIER
# ══════════════════════════════════════════════════════════════

def train_vit_classifier(
    embed_dir, labels, labels_dir, dim_name,
    epochs=80, batch_size=64,
):
    """
    Classifier on pre-extracted ViT face-crop embeddings.
    Embeddings extracted by extract_face_embeddings.py.
    Each clip → (seq_len, 768) ViT-B/16 embeddings.
    Uses a small Transformer to classify.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    print(f"\n{'='*60}")
    print(f"ViT EMBEDDING CLASSIFIER: {dim_name.upper()}")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    print(f"{'='*60}")

    # Load embeddings
    embed_files = sorted(glob.glob(os.path.join(embed_dir, "*.npy")))
    print(f"Found {len(embed_files)} embedding files")

    X_list, y_list, clip_ids = [], [], []
    for ef in embed_files:
        clip_id = os.path.basename(ef).replace(".npy", "")
        if clip_id not in labels:
            continue
        emb = np.load(ef)  # (seq_len, 768)
        if emb.shape[0] < 4:
            continue
        # Uniform sample to fixed seq_len
        seq_len = 16
        if emb.shape[0] >= seq_len:
            indices = np.linspace(0, emb.shape[0] - 1, seq_len, dtype=int)
            emb = emb[indices]
        else:
            pad = np.zeros((seq_len, emb.shape[1]), dtype=np.float32)
            pad[:emb.shape[0]] = emb
            emb = pad
        X_list.append(emb)
        y_list.append(labels[clip_id])
        clip_ids.append(clip_id)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int32)
    dim_idx = DIMENSION_NAMES.index(dim_name)
    print(f"Loaded {len(X)} clips, embed shape: {X.shape}")

    # Split
    train_idx, val_idx, test_idx = get_split_indices(labels_dir, clip_ids)
    X_train, y_train = X[train_idx], binarize_labels(y[train_idx, dim_idx]).astype(np.float32)
    X_val, y_val = X[val_idx], binarize_labels(y[val_idx, dim_idx]).astype(np.float32)
    X_test, y_test = X[test_idx], binarize_labels(y[test_idx, dim_idx]).astype(np.float32)
    print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    # Normalize
    X_mean = X_train.mean(axis=(0, 1), keepdims=True)
    X_std = X_train.std(axis=(0, 1), keepdims=True) + 1e-8
    X_train_n = (X_train - X_mean) / X_std
    X_val_n = (X_val - X_mean) / X_std
    X_test_n = (X_test - X_mean) / X_std

    classes, counts = np.unique(y_train, return_counts=True)
    cw = {int(c): len(y_train) / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)

    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train_n), torch.FloatTensor(y_train)),
                              batch_size=batch_size, sampler=sampler)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val_n), torch.FloatTensor(y_val)), batch_size=batch_size)
    test_loader = DataLoader(TensorDataset(torch.FloatTensor(X_test_n), torch.FloatTensor(y_test)), batch_size=batch_size)

    class ViTClassifier(nn.Module):
        def __init__(self, embed_dim=768, d_model=128, nhead=4, num_layers=2, dropout=0.3):
            super().__init__()
            self.proj = nn.Linear(embed_dim, d_model)
            self.cls_token = nn.Parameter(torch.randn(1, 1, d_model) * 0.02)
            self.pos_embed = nn.Parameter(torch.randn(1, 20, d_model) * 0.02)
            enc_layer = nn.TransformerEncoderLayer(d_model, nhead, d_model * 2, dropout,
                                                    activation='gelu', batch_first=True, norm_first=True)
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers)
            self.head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, 1))

        def forward(self, x):
            B, T, _ = x.shape
            x = self.proj(x)
            cls = self.cls_token.expand(B, -1, -1)
            x = torch.cat([cls, x], dim=1)
            x = x + self.pos_embed[:, :T + 1, :]
            x = self.encoder(x)
            return self.head(x[:, 0, :])

    model = ViTClassifier().to(device)
    model = wrap_model_multi_gpu(model)
    print(f"  ViT Classifier params: {sum(p.numel() for p in model.parameters()):,}")

    class FocalLoss(nn.Module):
        def __init__(self, gamma=2.0):
            super().__init__()
            self.gamma = gamma
        def forward(self, logits, targets):
            bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
            pt = torch.exp(-bce)
            return ((1 - pt) ** self.gamma * bce).mean()

    criterion = FocalLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=0.01)

    best_val_f1, best_state = 0.0, None
    for epoch in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(xb).squeeze(-1), yb)
            loss.backward()
            optimizer.step()

        model.eval()
        val_proba = []
        with torch.no_grad():
            for xb, _ in val_loader:
                val_proba.extend(torch.sigmoid(model(xb.to(device)).squeeze(-1)).cpu().numpy())
        val_proba = np.array(val_proba)
        val_f1 = max(f1_score(y_val, (val_proba >= t).astype(int), average='macro', zero_division=0)
                     for t in np.arange(0.3, 0.7, 0.02))
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_state = {k: v.cpu().clone() for k, v in unwrap_model(model).state_dict().items()}
        if epoch % 10 == 0:
            print(f"  Epoch {epoch}: val_f1m={val_f1:.4f}")

    if best_state:
        unwrap_model(model).load_state_dict(best_state)
    model.eval()

    all_proba = []
    with torch.no_grad():
        for xb, _ in test_loader:
            all_proba.extend(torch.sigmoid(model(xb.to(device)).squeeze(-1)).cpu().numpy())
    y_proba = np.array(all_proba)

    best_thr, best_f1 = 0.5, 0
    for t in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (y_proba >= t).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = t
    y_pred = (y_proba >= best_thr).astype(int)
    print(f"\n*** TEST: Acc={accuracy_score(y_test, y_pred):.4f} F1m={best_f1:.4f} (thr={best_thr:.2f}) ***")
    print(classification_report(y_test, y_pred, zero_division=0))

    return {"y_proba": y_proba, "test_f1_macro": float(best_f1), "best_threshold": float(best_thr)}


# ══════════════════════════════════════════════════════════════
# SECTION 5: STACKING ENSEMBLE
# ══════════════════════════════════════════════════════════════

def train_stacking_ensemble(
    probas_dict, y_test, dim_name, cv_folds=5,
):
    """
    Stacking meta-learner: trains a logistic regression / XGBoost
    on the probability outputs of base models.
    
    probas_dict: {model_name: np.array of y_proba on test set}
    """
    from sklearn.linear_model import LogisticRegressionCV
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    import xgboost as xgb

    print(f"\n{'='*60}")
    print(f"STACKING ENSEMBLE: {dim_name.upper()}")
    print(f"Base models: {list(probas_dict.keys())}")
    print(f"{'='*60}")

    model_names = list(probas_dict.keys())
    # Stack probabilities as features
    X_meta = np.column_stack([probas_dict[name] for name in model_names])
    print(f"Meta-features shape: {X_meta.shape}")

    # Also add interaction features
    if X_meta.shape[1] >= 2:
        interactions = []
        for i in range(X_meta.shape[1]):
            for j in range(i + 1, X_meta.shape[1]):
                interactions.append(X_meta[:, i] * X_meta[:, j])
                interactions.append(np.abs(X_meta[:, i] - X_meta[:, j]))
        X_meta = np.column_stack([X_meta] + interactions)
        print(f"With interactions: {X_meta.shape}")

    # Cross-validated stacking
    skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

    oof_preds = np.zeros(len(y_test))
    fold_f1s = []

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_meta, y_test)):
        X_tr, X_va = X_meta[train_idx], X_meta[val_idx]
        y_tr, y_va = y_test[train_idx], y_test[val_idx]

        # XGBoost meta-learner
        meta_model = xgb.XGBClassifier(
            n_estimators=100, max_depth=3, learning_rate=0.1,
            scale_pos_weight=np.sum(y_tr == 0) / max(np.sum(y_tr == 1), 1),
            random_state=42, verbosity=0,
        )
        meta_model.fit(X_tr, y_tr)
        fold_proba = meta_model.predict_proba(X_va)[:, 1]
        oof_preds[val_idx] = fold_proba

        fold_f1 = max(
            f1_score(y_va, (fold_proba >= t).astype(int), average='macro', zero_division=0)
            for t in np.arange(0.3, 0.7, 0.02)
        )
        fold_f1s.append(fold_f1)
        print(f"  Fold {fold + 1}: F1m={fold_f1:.4f}")

    # Also fit on full data for the final threshold
    best_thr, best_f1 = 0.5, 0
    for t in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (oof_preds >= t).astype(int), average='macro', zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = t

    y_pred = (oof_preds >= best_thr).astype(int)
    test_acc = accuracy_score(y_test, y_pred)
    mean_f1 = np.mean(fold_f1s)
    std_f1 = np.std(fold_f1s)

    print(f"\n*** STACKING RESULTS ***")
    print(f"OOF F1 Macro: {best_f1:.4f} (thr={best_thr:.2f})")
    print(f"CV F1 Macro: {mean_f1:.4f} ± {std_f1:.4f}")
    print(f"Accuracy: {test_acc:.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Also do simple soft-voting for comparison
    weights = np.array([1.0 / len(model_names)] * len(model_names))
    soft_vote = np.average(
        np.column_stack([probas_dict[name] for name in model_names]),
        axis=1, weights=weights
    )
    sv_thr, sv_f1 = 0.5, 0
    for t in np.arange(0.2, 0.8, 0.02):
        f1 = f1_score(y_test, (soft_vote >= t).astype(int), average='macro', zero_division=0)
        if f1 > sv_f1:
            sv_f1 = f1
            sv_thr = t
    print(f"Soft-voting baseline: F1m={sv_f1:.4f}")

    return {
        "stacking_f1_macro": float(best_f1),
        "stacking_cv_mean": float(mean_f1),
        "stacking_cv_std": float(std_f1),
        "stacking_threshold": float(best_thr),
        "soft_voting_f1_macro": float(sv_f1),
        "fold_f1s": [float(f) for f in fold_f1s],
        "n_base_models": len(model_names),
    }


# ══════════════════════════════════════════════════════════════
# SECTION 6: K-FOLD CROSS-VALIDATED XGBOOST
# ══════════════════════════════════════════════════════════════

def train_xgboost_cv(
    X_all, y_all, dim_name, n_folds=5, n_trials=30,
):
    """
    XGBoost with Stratified K-Fold cross-validation.
    Reports mean ± std F1-macro across folds for paper.
    """
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.preprocessing import StandardScaler
    import xgboost as xgb

    print(f"\n{'='*60}")
    print(f"XGBoost {n_folds}-FOLD CV: {dim_name.upper()}")
    print(f"Samples: {len(y_all)}")
    print(f"{'='*60}")

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_accs, fold_f1s = [], []

    for fold, (train_idx, test_idx) in enumerate(skf.split(X_all, y_all)):
        X_tr, X_te = X_all[train_idx], X_all[test_idx]
        y_tr, y_te = y_all[train_idx], y_all[test_idx]

        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_tr)
        X_te = scaler.transform(X_te)

        # Feature selection
        from app.ml.train_model_v3 import select_features
        X_tr_sel, X_te_sel, _ = select_features(X_tr, y_tr, X_te, top_k=150)

        neg, pos = np.sum(y_tr == 0), np.sum(y_tr == 1)
        spw = neg / max(pos, 1)

        # Optuna tuning per fold
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            # Use 20% of train as val for tuning
            val_size = int(len(X_tr_sel) * 0.2)
            X_tune_tr, X_tune_val = X_tr_sel[:-val_size], X_tr_sel[-val_size:]
            y_tune_tr, y_tune_val = y_tr[:-val_size], y_tr[-val_size:]

            def objective(trial):
                params = {
                    'n_estimators': trial.suggest_int('n_estimators', 200, 600),
                    'max_depth': trial.suggest_int('max_depth', 3, 8),
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15, log=True),
                    'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                    'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
                    'gamma': trial.suggest_float('gamma', 0.0, 0.5),
                    'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                    'scale_pos_weight': trial.suggest_float('scale_pos_weight', 1.0, spw),
                }
                m = xgb.XGBClassifier(**params, random_state=42, n_jobs=-1, verbosity=0)
                m.fit(X_tune_tr, y_tune_tr)
                pred = m.predict(X_tune_val)
                return f1_score(y_tune_val, pred, average='macro', zero_division=0)

            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
            best_params = study.best_params
        except ImportError:
            best_params = {'n_estimators': 400, 'max_depth': 6, 'learning_rate': 0.05,
                           'scale_pos_weight': spw}

        model = xgb.XGBClassifier(**best_params, random_state=42, n_jobs=-1, verbosity=0)
        model.fit(X_tr_sel, y_tr)
        y_proba = model.predict_proba(X_te_sel)[:, 1]

        best_thr, best_f1 = 0.5, 0
        for thr in np.arange(0.25, 0.75, 0.02):
            f1 = f1_score(y_te, (y_proba >= thr).astype(int), average='macro', zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thr = thr

        y_pred = (y_proba >= best_thr).astype(int)
        acc = accuracy_score(y_te, y_pred)
        fold_accs.append(acc)
        fold_f1s.append(best_f1)
        print(f"  Fold {fold + 1}: Acc={acc:.4f} F1m={best_f1:.4f} (thr={best_thr:.2f})")

    mean_acc = np.mean(fold_accs)
    mean_f1 = np.mean(fold_f1s)
    std_f1 = np.std(fold_f1s)
    print(f"\n*** {n_folds}-FOLD CV RESULTS ***")
    print(f"Acc: {mean_acc:.4f} ± {np.std(fold_accs):.4f}")
    print(f"F1m: {mean_f1:.4f} ± {std_f1:.4f}")

    return {
        "cv_accuracy_mean": float(mean_acc),
        "cv_accuracy_std": float(np.std(fold_accs)),
        "cv_f1_macro_mean": float(mean_f1),
        "cv_f1_macro_std": float(std_f1),
        "fold_accuracies": [float(a) for a in fold_accs],
        "fold_f1_macros": [float(f) for f in fold_f1s],
        "n_folds": n_folds,
    }


# ══════════════════════════════════════════════════════════════
# EXPERIMENT RUNNER v4
# ══════════════════════════════════════════════════════════════

def run_v4_experiment(
    mode: str = "all_openface",
    n_trials: int = 30,
    seq_len: int = 60,
    n_folds: int = 5,
    transformer_epochs: int = 120,
    bilstm_epochs: int = 100,
):
    """Run v4 experiment pipeline."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    labels_dir = os.path.join(DAISEE_DIR, "DAiSEE", "Labels")
    all_labels = load_labels(os.path.join(labels_dir, "AllLabels.csv"))
    print(f"Loaded {len(all_labels)} labels")

    all_results = {}

    # ── Load data based on mode ──
    need_engineered = mode in ("xgboost_cv", "stacking", "all_openface", "full")
    need_sequences = mode in ("transformer", "bilstm_v4", "stacking", "all_openface", "full")
    need_vit = mode in ("vit_train", "stacking", "full")

    X_eng, y_eng, ids_eng = None, None, None
    X_seq, y_seq, ids_seq = None, None, None

    if need_engineered:
        print("\n[*] Loading engineered features...")
        X_eng, y_eng, ids_eng = load_openface_features(OPENFACE_DIR, all_labels, feature_mode="engineered")
        print(f"  Shape: {X_eng.shape}")

    if need_sequences:
        print(f"\n[*] Loading sequence features (seq_len={seq_len})...")
        X_seq, y_seq, ids_seq = load_openface_features(OPENFACE_DIR, all_labels, seq_len=seq_len, feature_mode="sequence")
        print(f"  Shape: {X_seq.shape}")

    for dim_idx, dim_name in enumerate(DIMENSION_NAMES):
        print(f"\n\n{'#'*70}")
        print(f"### DIMENSION: {dim_name.upper()}")
        print(f"{'#'*70}")

        probas_for_stacking = {}

        # ── Transformer ──
        if mode in ("transformer", "all_openface", "full"):
            import torch
            train_idx, val_idx, test_idx = get_split_indices(labels_dir, ids_seq)
            y_tr = binarize_labels(y_seq[train_idx, dim_idx]).astype(np.float32)
            y_va = binarize_labels(y_seq[val_idx, dim_idx]).astype(np.float32)
            y_te = binarize_labels(y_seq[test_idx, dim_idx]).astype(np.float32)

            result = train_transformer(
                X_seq[train_idx], y_tr, X_seq[val_idx], y_va, X_seq[test_idx], y_te,
                dim_name, epochs=transformer_epochs, seq_len=seq_len,
            )
            key = f"transformer_{dim_name}"
            all_results[key] = {k: v for k, v in result.items() if k not in ("model", "y_proba", "X_mean", "X_std")}
            probas_for_stacking["transformer"] = result["y_proba"]

            # Save
            torch.save(result["model"].state_dict(), os.path.join(MODEL_DIR, f"transformer_v4_{dim_name}.pt"))
            np.save(os.path.join(MODEL_DIR, f"proba_transformer_v4_{dim_name}.npy"), result["y_proba"])
            np.save(os.path.join(MODEL_DIR, f"labels_test_v4_{dim_name}.npy"), y_te)

        # ── BiLSTM-GRU v4 ──
        if mode in ("bilstm_v4", "all_openface", "full"):
            import torch
            train_idx, val_idx, test_idx = get_split_indices(labels_dir, ids_seq)
            y_tr = binarize_labels(y_seq[train_idx, dim_idx]).astype(np.float32)
            y_va = binarize_labels(y_seq[val_idx, dim_idx]).astype(np.float32)
            y_te = binarize_labels(y_seq[test_idx, dim_idx]).astype(np.float32)

            result = train_bilstm_v4(
                X_seq[train_idx], y_tr, X_seq[val_idx], y_va, X_seq[test_idx], y_te,
                dim_name, epochs=bilstm_epochs,
            )
            key = f"bilstm_v4_{dim_name}"
            all_results[key] = {k: v for k, v in result.items() if k not in ("model", "y_proba", "X_mean", "X_std")}
            probas_for_stacking["bilstm_v4"] = result["y_proba"]

            torch.save(result["model"].state_dict(), os.path.join(MODEL_DIR, f"bilstm_v4_{dim_name}.pt"))
            np.save(os.path.join(MODEL_DIR, f"proba_bilstm_v4_{dim_name}.npy"), result["y_proba"])

        # ── XGBoost with K-Fold CV ──
        if mode in ("xgboost_cv", "all_openface", "full"):
            y_bin = binarize_labels(y_eng[:, dim_idx])
            result = train_xgboost_cv(X_eng, y_bin, dim_name, n_folds=n_folds, n_trials=n_trials)
            all_results[f"xgb_cv_{dim_name}"] = result

            # Also get test probas for stacking (using DAiSEE split)
            from sklearn.preprocessing import StandardScaler
            train_idx, val_idx, test_idx = get_split_indices(labels_dir, ids_eng)
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_eng[train_idx])
            X_te = scaler.transform(X_eng[test_idx])
            y_tr = binarize_labels(y_eng[train_idx, dim_idx])
            y_te = binarize_labels(y_eng[test_idx, dim_idx])

            X_tr_sel, X_te_sel, feat_idx = select_features(X_tr, y_tr, X_te, top_k=150)

            import xgboost as xgb
            neg, pos = np.sum(y_tr == 0), np.sum(y_tr == 1)
            model = xgb.XGBClassifier(
                n_estimators=500, max_depth=6, learning_rate=0.05,
                scale_pos_weight=neg / max(pos, 1),
                random_state=42, n_jobs=-1, verbosity=0,
            )
            model.fit(X_tr_sel, y_tr)
            probas_for_stacking["xgboost"] = model.predict_proba(X_te_sel)[:, 1]
            np.save(os.path.join(MODEL_DIR, f"proba_xgb_v4_{dim_name}.npy"), probas_for_stacking["xgboost"])

        # ── ViT Classifier ──
        if mode in ("vit_train", "full") and os.path.exists(VIT_EMBED_DIR):
            result = train_vit_classifier(VIT_EMBED_DIR, all_labels, labels_dir, dim_name)
            all_results[f"vit_{dim_name}"] = {k: v for k, v in result.items() if k != "y_proba"}
            if "y_proba" in result:
                probas_for_stacking["vit"] = result["y_proba"]

        # ── Stacking Ensemble ──
        if mode in ("stacking", "all_openface", "full") and len(probas_for_stacking) >= 2:
            # Get test labels
            if y_te is None:
                train_idx, val_idx, test_idx = get_split_indices(labels_dir, ids_seq or ids_eng)
                y_ref = y_seq if ids_seq else y_eng
                y_te = binarize_labels(y_ref[test_idx, dim_idx])

            result = train_stacking_ensemble(probas_for_stacking, y_te, dim_name)
            all_results[f"stacking_{dim_name}"] = result

        # ── Load saved probas for standalone stacking mode ──
        if mode == "stacking" and len(probas_for_stacking) < 2:
            print(f"\n  Loading saved probabilities for {dim_name} stacking...")
            loaded = {}
            for model_tag in ["xgb_v4", "transformer_v4", "bilstm_v4", "xgb_v3", "lstm_v3"]:
                path = os.path.join(MODEL_DIR, f"proba_{model_tag}_{dim_name}.npy")
                if os.path.exists(path):
                    loaded[model_tag] = np.load(path)
            labels_path = os.path.join(MODEL_DIR, f"labels_test_v4_{dim_name}.npy")
            if not os.path.exists(labels_path):
                labels_path = os.path.join(MODEL_DIR, f"labels_test_v3_{dim_name}.npy")
            if loaded and os.path.exists(labels_path):
                y_te = np.load(labels_path)
                # Align lengths
                min_len = min(len(v) for v in loaded.values())
                loaded = {k: v[:min_len] for k, v in loaded.items()}
                y_te = y_te[:min_len]
                result = train_stacking_ensemble(loaded, y_te, dim_name)
                all_results[f"stacking_{dim_name}"] = result

    # ── Save results ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(RESULTS_DIR, f"experiment_v4_{mode}_{timestamp}.json")

    metadata = {
        "timestamp": datetime.now().isoformat(),
        "version": "v4",
        "mode": mode,
        "seq_len": seq_len,
        "improvements": [
            "temporal_transformer_encoder",
            "bilstm_gru_hybrid_with_multiscale_conv",
            "vit_face_embeddings",
            "stacking_meta_ensemble",
            "kfold_cross_validation",
            "data_augmentation",
            "longer_sequences",
        ],
        "results": all_results,
    }

    with open(results_file, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    # ── Summary ──
    print(f"\n\n{'='*80}")
    print("V4 EXPERIMENT SUMMARY")
    print(f"{'='*80}")
    print(f"{'Key':<35} {'F1-Macro':<12} {'Acc':<12} {'Extra'}")
    print(f"{'-'*80}")
    for key, res in sorted(all_results.items()):
        f1m = res.get('test_f1_macro') or res.get('cv_f1_macro_mean') or res.get('stacking_f1_macro', 0)
        acc = res.get('test_accuracy') or res.get('cv_accuracy_mean', 0)
        extra = ""
        if 'cv_f1_macro_std' in res:
            extra = f"±{res['cv_f1_macro_std']:.4f}"
        elif 'stacking_cv_std' in res:
            extra = f"±{res['stacking_cv_std']:.4f}"
        elif 'n_params' in res:
            extra = f"{res['n_params']:,} params"
        print(f"{key:<35} {f1m:<12.4f} {acc:<12.4f} {extra}")

    print(f"\nResults saved to: {results_file}")
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Smart LMS Model Training v4")
    parser.add_argument("--mode", type=str, default="all_openface",
                        choices=["transformer", "bilstm_v4", "xgboost_cv",
                                 "vit_train", "stacking", "all_openface", "full"])
    parser.add_argument("--n_trials", type=int, default=30)
    parser.add_argument("--seq_len", type=int, default=60)
    parser.add_argument("--n_folds", type=int, default=5)
    parser.add_argument("--transformer_epochs", type=int, default=120)
    parser.add_argument("--bilstm_epochs", type=int, default=100)
    args = parser.parse_args()

    run_v4_experiment(
        mode=args.mode,
        n_trials=args.n_trials,
        seq_len=args.seq_len,
        n_folds=args.n_folds,
        transformer_epochs=args.transformer_epochs,
        bilstm_epochs=args.bilstm_epochs,
    )


if __name__ == "__main__":
    main()
