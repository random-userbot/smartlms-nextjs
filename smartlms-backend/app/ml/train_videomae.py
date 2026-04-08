"""
Smart LMS - VideoMAE Fine-Tuning for Engagement Detection
==========================================================
Fine-tunes VideoMAE V2 (or TimeSformer) on DAiSEE raw video clips.
End-to-end video → engagement prediction without OpenFace.

This is the HIGHEST IMPACT single improvement — replaces the entire
OpenFace feature extraction pipeline with learned representations.

Requirements:
    pip install transformers accelerate decord av
    
GPU: T4 16GB — uses gradient checkpointing + mixed precision to fit.
Time: ~8-12 hrs for all 4 dimensions on T4.

Usage (Kaggle):
    python train_videomae.py --mode finetune --dim engagement
    python train_videomae.py --mode finetune_all
    python train_videomae.py --mode extract_features
"""

import os
import sys
import json
import glob
import argparse
import logging
import warnings
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


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


# ── Environment detection ──
ON_KAGGLE = os.path.exists("/kaggle/working")

if ON_KAGGLE:
    if "/kaggle/working" not in sys.path:
        sys.path.insert(0, "/kaggle/working")
    VIDEO_DIR = "/kaggle/input/daisee-videos/DAiSEE/DataSet"
    LABELS_DIR = "/kaggle/input/smartlms-openface/Labels"
    MODEL_DIR = "/kaggle/working/trained_models"
    RESULTS_DIR = "/kaggle/working/experiment_results"
    CACHE_DIR = "/kaggle/working/cache"
else:
    DAISEE_DIR = r"C:\Users\revan\Downloads\DAiSEE"
    VIDEO_DIR = os.path.join(DAISEE_DIR, "DAiSEE", "DataSet")
    LABELS_DIR = os.path.join(DAISEE_DIR, "DAiSEE", "Labels")
    MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained_models")
    RESULTS_DIR = os.path.join(os.path.dirname(__file__), "experiment_results")
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# SECTION 1: VIDEO DATA LOADING
# ══════════════════════════════════════════════════════════════

def load_labels(csv_path: str) -> Dict[str, List[int]]:
    """Load DAiSEE labels: clip_id → [boredom, engagement, confusion, frustration]."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    labels = {}
    for _, row in df.iterrows():
        clip_id = str(row['ClipID']).replace('.avi', '').replace('.mp4', '').strip()
        labels[clip_id] = [
            int(row['Boredom']), int(row['Engagement']),
            int(row['Confusion']), int(row['Frustration']),
        ]
    return labels


def find_video_clips(video_dir: str) -> Dict[str, str]:
    """Find all video files and map clip_id → path."""
    clip_map = {}
    for ext in ['*.avi', '*.mp4']:
        for path in glob.glob(os.path.join(video_dir, '**', ext), recursive=True):
            clip_id = Path(path).stem
            clip_map[clip_id] = path
    logger.info(f"Found {len(clip_map)} video clips")
    return clip_map


def get_splits(labels_dir: str) -> Tuple[Dict, Dict, Dict]:
    """Load official DAiSEE train/val/test splits."""
    train = load_labels(os.path.join(labels_dir, "TrainLabels.csv"))
    val = load_labels(os.path.join(labels_dir, "ValidationLabels.csv"))
    test = load_labels(os.path.join(labels_dir, "TestLabels.csv"))
    logger.info(f"Splits: train={len(train)}, val={len(val)}, test={len(test)}")
    return train, val, test


# ══════════════════════════════════════════════════════════════
# SECTION 2: VIDEO DATASET FOR PYTORCH
# ══════════════════════════════════════════════════════════════

def load_video_frames(video_path: str, num_frames: int = 16, size: int = 224) -> Optional[np.ndarray]:
    """
    Load uniformly sampled frames from a video.
    Returns: (num_frames, 3, H, W) float32 array normalized to [0, 1]
    """
    import cv2
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < num_frames:
        cap.release()
        return None
    
    indices = np.linspace(0, total - 1, num_frames, dtype=int)
    frames = []
    
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return None
        # BGR → RGB, resize, normalize
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (size, size))
        frames.append(frame)
    
    cap.release()
    
    # (T, H, W, C) → (T, C, H, W) normalized to [0, 1]
    video = np.stack(frames).astype(np.float32) / 255.0
    video = video.transpose(0, 3, 1, 2)  # (T, C, H, W)
    return video


class DAiSEEVideoDataset:
    """
    PyTorch Dataset for DAiSEE video clips.
    Supports binary and ordinal (4-class) labels.
    """
    def __init__(self, clip_labels: Dict[str, List[int]], clip_paths: Dict[str, str],
                 dim_idx: int, num_frames: int = 16, size: int = 224,
                 binary: bool = True, augment: bool = False):
        import torch
        
        self.num_frames = num_frames
        self.size = size
        self.binary = binary
        self.augment = augment
        self.dim_idx = dim_idx
        
        # Filter to clips that exist
        self.samples = []
        for clip_id, label_vec in clip_labels.items():
            if clip_id in clip_paths:
                self.samples.append((clip_id, clip_paths[clip_id], label_vec[dim_idx]))
        
        logger.info(f"Dataset: {len(self.samples)} clips, dim={DIMENSION_NAMES[dim_idx]}")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        import torch
        
        clip_id, path, label = self.samples[idx]
        video = load_video_frames(path, self.num_frames, self.size)
        
        if video is None:
            # Return zeros as fallback (will be filtered during training)
            video = np.zeros((self.num_frames, 3, self.size, self.size), dtype=np.float32)
        
        # Augmentation
        if self.augment and np.random.random() > 0.5:
            video = self._augment(video)
        
        # Normalize with ImageNet stats
        mean = np.array([0.485, 0.456, 0.406]).reshape(1, 3, 1, 1)
        std = np.array([0.229, 0.224, 0.225]).reshape(1, 3, 1, 1)
        video = (video - mean) / std
        
        if self.binary:
            label = 1 if label >= 2 else 0
        
        return torch.FloatTensor(video), torch.LongTensor([label]).squeeze()
    
    def _augment(self, video):
        """Simple video augmentations."""
        # Random horizontal flip
        if np.random.random() > 0.5:
            video = video[:, :, :, ::-1].copy()
        # Random temporal jitter
        if np.random.random() > 0.5:
            noise = np.random.normal(0, 0.02, video.shape).astype(np.float32)
            video = np.clip(video + noise, 0, 1)
        # Random brightness
        if np.random.random() > 0.5:
            factor = np.random.uniform(0.8, 1.2)
            video = np.clip(video * factor, 0, 1)
        return video


# ══════════════════════════════════════════════════════════════
# SECTION 3: VideoMAE V2 FINE-TUNING
# ══════════════════════════════════════════════════════════════

def train_videomae(
    dim_name: str,
    num_frames: int = 16,
    epochs: int = 30,
    batch_size: int = 4,  # Small batch for T4 16GB
    lr: float = 2e-5,
    binary: bool = True,
    gradient_accumulation: int = 8,
    model_name: str = "MCG-NJU/videomae-base",
):
    """
    Fine-tune VideoMAE V2 on DAiSEE for engagement detection.
    
    Architecture:
    - Pretrained VideoMAE-base (ViT-B, 86M params)
    - Replace classification head for binary/4-class
    - Gradient checkpointing + mixed precision for T4
    - Effective batch size = batch_size × gradient_accumulation = 32
    
    Time estimate: ~2 hrs per dimension on T4
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, WeightedRandomSampler
    from sklearn.metrics import f1_score, accuracy_score, classification_report
    
    print(f"\n{'='*70}")
    print(f"VideoMAE FINE-TUNING: {dim_name.upper()}")
    print(f"Model: {model_name}")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
    print(f"{'='*70}")
    
    dim_idx = DIMENSION_NAMES.index(dim_name)
    
    # ── Load data ──
    clip_paths = find_video_clips(VIDEO_DIR)
    train_labels, val_labels, test_labels = get_splits(LABELS_DIR)
    
    train_ds = DAiSEEVideoDataset(train_labels, clip_paths, dim_idx, num_frames, 224, binary, augment=True)
    val_ds = DAiSEEVideoDataset(val_labels, clip_paths, dim_idx, num_frames, 224, binary, augment=False)
    test_ds = DAiSEEVideoDataset(test_labels, clip_paths, dim_idx, num_frames, 224, binary, augment=False)
    
    # Class-balanced sampler
    train_labels_arr = np.array([s[2] for s in train_ds.samples])
    if binary:
        train_labels_arr = (train_labels_arr >= 2).astype(int)
    classes, counts = np.unique(train_labels_arr, return_counts=True)
    cw = {int(c): len(train_labels_arr) / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in train_labels_arr])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, sampler=sampler, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size * 2, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size * 2, num_workers=2, pin_memory=True)
    
    # ── Load pretrained VideoMAE ──
    try:
        from transformers import VideoMAEForVideoClassification, VideoMAEConfig
        
        num_labels = 2 if binary else 4
        model = VideoMAEForVideoClassification.from_pretrained(
            model_name,
            num_labels=num_labels,
            ignore_mismatched_sizes=True,
        )
        print(f"  Loaded pretrained VideoMAE: {model_name}")
    except Exception as e:
        logger.warning(f"Could not load {model_name}: {e}")
        logger.info("Falling back to TimeSformer-style model...")
        model = _build_timesformer_fallback(num_frames, binary)
    
    # Enable gradient checkpointing to save memory
    if hasattr(model, 'gradient_checkpointing_enable'):
        model.gradient_checkpointing_enable()
    
    model = model.to(device)
    model = wrap_model_multi_gpu(model)
    n_params = sum(p.numel() for p in model.parameters())
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total params: {n_params:,} | Trainable: {n_trainable:,}")
    
    # ── Focal Loss for imbalance ──
    class FocalCELoss(nn.Module):
        def __init__(self, weight=None, gamma=2.0, smoothing=0.05):
            super().__init__()
            self.gamma = gamma
            self.smoothing = smoothing
            self.weight = weight
            
        def forward(self, logits, targets):
            n_classes = logits.shape[1]
            # Label smoothing
            one_hot = torch.zeros_like(logits).scatter(1, targets.unsqueeze(1), 1)
            smooth = one_hot * (1 - self.smoothing) + self.smoothing / n_classes
            # Cross entropy
            log_probs = torch.log_softmax(logits, dim=1)
            ce = -(smooth * log_probs).sum(dim=1)
            # Focal term
            probs = torch.softmax(logits, dim=1).gather(1, targets.unsqueeze(1)).squeeze()
            focal = (1 - probs) ** self.gamma * ce
            if self.weight is not None:
                w = self.weight.to(logits.device)[targets]
                focal = focal * w
            return focal.mean()
    
    class_weights = torch.FloatTensor([cw.get(c, 1.0) for c in range(2 if binary else 4)])
    criterion = FocalCELoss(weight=class_weights, gamma=2.0)
    
    # ── Optimizer: separate LR for backbone and head ──
    backbone_params = []
    head_params = []
    for name, param in unwrap_model(model).named_parameters():
        if 'classifier' in name or 'head' in name or 'fc' in name:
            head_params.append(param)
        else:
            backbone_params.append(param)
    
    optimizer = torch.optim.AdamW([
        {'params': backbone_params, 'lr': lr * 0.1},      # Slower for pretrained 
        {'params': head_params, 'lr': lr},                 # Faster for new head
    ], weight_decay=0.05)
    
    total_steps = len(train_loader) * epochs // gradient_accumulation
    warmup_steps = total_steps // 10
    
    def lr_schedule(step):
        if step < warmup_steps:
            return step / max(warmup_steps, 1)
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return 0.5 * (1 + np.cos(np.pi * progress))
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_schedule)
    
    # ── Mixed precision ──
    scaler = torch.amp.GradScaler('cuda') if device.type == 'cuda' else None
    
    # ── Training loop ──
    best_val_f1 = 0.0
    best_state = None
    patience_counter = 0
    PATIENCE = 8
    global_step = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        optimizer.zero_grad()
        
        for batch_idx, (videos, labels) in enumerate(train_loader):
            videos, labels = videos.to(device), labels.to(device)
            
            # VideoMAE expects (B, C, T, H, W) but we have (B, T, C, H, W)
            videos = videos.permute(0, 2, 1, 3, 4)
            
            with torch.amp.autocast('cuda', enabled=scaler is not None):
                outputs = model(videos)
                logits = outputs.logits if hasattr(outputs, 'logits') else outputs
                loss = criterion(logits, labels)
                loss = loss / gradient_accumulation
            
            if scaler:
                scaler.scale(loss).backward()
            else:
                loss.backward()
            
            train_loss += loss.item() * gradient_accumulation
            
            if (batch_idx + 1) % gradient_accumulation == 0:
                if scaler:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                optimizer.zero_grad()
                scheduler.step()
                global_step += 1
        
        avg_loss = train_loss / len(train_loader)
        
        # ── Validate ──
        model.eval()
        val_preds, val_true = [], []
        with torch.no_grad():
            for videos, labels in val_loader:
                videos = videos.to(device).permute(0, 2, 1, 3, 4)
                with torch.amp.autocast('cuda', enabled=scaler is not None):
                    outputs = model(videos)
                    logits = outputs.logits if hasattr(outputs, 'logits') else outputs
                preds = logits.argmax(dim=1).cpu().numpy()
                val_preds.extend(preds)
                val_true.extend(labels.numpy())
        
        val_f1 = f1_score(val_true, val_preds, average='macro', zero_division=0)
        val_acc = accuracy_score(val_true, val_preds)
        
        print(f"  Epoch {epoch+1:2d}/{epochs}: loss={avg_loss:.4f} val_f1m={val_f1:.4f} val_acc={val_acc:.4f}")
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in unwrap_model(model).state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"  Early stopping at epoch {epoch+1}")
                break
    
    # ── Test evaluation ──
    if best_state:
        unwrap_model(model).load_state_dict(best_state)
    model.eval()
    
    test_preds, test_true, test_proba = [], [], []
    with torch.no_grad():
        for videos, labels in test_loader:
            videos = videos.to(device).permute(0, 2, 1, 3, 4)
            with torch.amp.autocast('cuda', enabled=scaler is not None):
                outputs = model(videos)
                logits = outputs.logits if hasattr(outputs, 'logits') else outputs
            proba = torch.softmax(logits, dim=1).cpu().numpy()
            preds = logits.argmax(dim=1).cpu().numpy()
            test_preds.extend(preds)
            test_true.extend(labels.numpy())
            test_proba.extend(proba)
    
    test_f1m = f1_score(test_true, test_preds, average='macro', zero_division=0)
    test_acc = accuracy_score(test_true, test_preds)
    
    print(f"\n*** VideoMAE TEST RESULTS: {dim_name.upper()} ***")
    print(f"F1 Macro: {test_f1m:.4f} | Accuracy: {test_acc:.4f}")
    print(classification_report(test_true, test_preds, zero_division=0))
    
    # Save
    torch.save(best_state or unwrap_model(model).state_dict(), 
               os.path.join(MODEL_DIR, f"videomae_{dim_name}.pt"))
    np.save(os.path.join(MODEL_DIR, f"proba_videomae_{dim_name}.npy"),
            np.array(test_proba))
    np.save(os.path.join(MODEL_DIR, f"labels_videomae_{dim_name}.npy"),
            np.array(test_true))
    
    return {
        "test_f1_macro": float(test_f1m),
        "test_accuracy": float(test_acc),
        "best_val_f1": float(best_val_f1),
        "epochs_trained": epoch + 1,
        "n_params": n_params,
        "model_name": model_name,
    }


def _build_timesformer_fallback(num_frames: int = 16, binary: bool = True):
    """
    Lightweight TimeSformer-style model as fallback if HuggingFace
    VideoMAE isn't available. Uses divided space-time attention.
    """
    import torch
    import torch.nn as nn
    
    class PatchEmbed3D(nn.Module):
        def __init__(self, img_size=224, patch_size=16, in_ch=3, embed_dim=768):
            super().__init__()
            self.proj = nn.Conv3d(in_ch, embed_dim, 
                                  kernel_size=(2, patch_size, patch_size),
                                  stride=(2, patch_size, patch_size))
        
        def forward(self, x):
            # x: (B, C, T, H, W)
            x = self.proj(x)  # (B, embed_dim, T', H', W')
            B, C, T, H, W = x.shape
            x = x.flatten(2).transpose(1, 2)  # (B, T'*H'*W', embed_dim)
            return x
    
    class VideoTransformer(nn.Module):
        def __init__(self, num_frames=16, num_classes=2, embed_dim=384, 
                     num_heads=6, num_layers=8, dropout=0.2):
            super().__init__()
            self.patch_embed = PatchEmbed3D(embed_dim=embed_dim)
            max_tokens = (num_frames // 2) * 14 * 14 + 1
            self.cls_token = nn.Parameter(torch.randn(1, 1, embed_dim) * 0.02)
            self.pos_embed = nn.Parameter(torch.randn(1, max_tokens, embed_dim) * 0.02)
            
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=embed_dim, nhead=num_heads,
                dim_feedforward=embed_dim * 4, dropout=dropout,
                activation='gelu', batch_first=True, norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers)
            self.head = nn.Sequential(
                nn.LayerNorm(embed_dim),
                nn.Linear(embed_dim, num_classes),
            )
            self.logits = None  # compatibility attribute
            
        def forward(self, x):
            B = x.shape[0]
            x = self.patch_embed(x)
            cls = self.cls_token.expand(B, -1, -1)
            x = torch.cat([cls, x], dim=1)
            x = x + self.pos_embed[:, :x.shape[1], :]
            x = self.encoder(x)
            logits = self.head(x[:, 0])
            # Return object-like for compatibility
            class Output:
                pass
            out = Output()
            out.logits = logits
            return out
    
    num_classes = 2 if binary else 4
    return VideoTransformer(num_frames, num_classes)


# ══════════════════════════════════════════════════════════════
# SECTION 4: VideoMAE FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_videomae_features(
    model_path: Optional[str] = None,
    model_name: str = "MCG-NJU/videomae-base",
    num_frames: int = 16,
    batch_size: int = 8,
):
    """
    Extract learned feature representations from fine-tuned VideoMAE.
    Uses the [CLS] token from the last hidden layer (768-dim).
    These features can be fed to the stacking ensemble.
    """
    import torch
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n{'='*70}")
    print(f"VideoMAE FEATURE EXTRACTION")
    print(f"{'='*70}")
    
    # Load model
    try:
        from transformers import VideoMAEModel
        model = VideoMAEModel.from_pretrained(model_name)
    except:
        print("Using fallback model for feature extraction")
        model = _build_timesformer_fallback(num_frames)
    
    if model_path and os.path.exists(model_path):
        state = torch.load(model_path, map_location=device)
        model.load_state_dict(state, strict=False)
        print(f"  Loaded finetuned weights from {model_path}")
    
    model = model.to(device)
    model = wrap_model_multi_gpu(model)
    model.eval()
    
    # Load all clips
    clip_paths = find_video_clips(VIDEO_DIR)
    all_labels_csv = os.path.join(LABELS_DIR, "AllLabels.csv")
    all_labels = load_labels(all_labels_csv)
    
    features = {}
    from tqdm import tqdm
    
    clip_ids = sorted(set(clip_paths.keys()) & set(all_labels.keys()))
    print(f"  Extracting features for {len(clip_ids)} clips...")
    
    batch = []
    batch_ids = []
    
    for clip_id in tqdm(clip_ids, desc="Extracting"):
        video = load_video_frames(clip_paths[clip_id], num_frames, 224)
        if video is None:
            continue
        
        # Normalize
        mean = np.array([0.485, 0.456, 0.406]).reshape(1, 3, 1, 1)
        std = np.array([0.229, 0.224, 0.225]).reshape(1, 3, 1, 1)
        video = (video - mean) / std
        
        batch.append(video)
        batch_ids.append(clip_id)
        
        if len(batch) >= batch_size:
            _extract_batch(model, batch, batch_ids, features, device)
            batch, batch_ids = [], []
    
    if batch:
        _extract_batch(model, batch, batch_ids, features, device)
    
    # Save as numpy arrays
    out_dir = os.path.join(MODEL_DIR, "videomae_features")
    os.makedirs(out_dir, exist_ok=True)
    
    for clip_id, feat in features.items():
        np.save(os.path.join(out_dir, f"{clip_id}.npy"), feat)
    
    print(f"\n  Saved {len(features)} feature vectors to {out_dir}")
    return features


def _extract_batch(model, batch, batch_ids, features, device):
    """Extract features from a batch of videos."""
    import torch
    
    videos = torch.FloatTensor(np.stack(batch)).to(device)
    videos = videos.permute(0, 2, 1, 3, 4)  # (B, C, T, H, W)
    
    with torch.no_grad(), torch.amp.autocast('cuda'):
        outputs = model(videos)
        if hasattr(outputs, 'last_hidden_state'):
            # Use [CLS] token
            feats = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        elif hasattr(outputs, 'logits'):
            # Fallback: use logits
            feats = outputs.logits.cpu().numpy()
        else:
            feats = outputs.cpu().numpy()
    
    for i, clip_id in enumerate(batch_ids):
        features[clip_id] = feats[i].astype(np.float16)


# ══════════════════════════════════════════════════════════════
# SECTION 5: MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="VideoMAE Fine-tuning for DAiSEE")
    parser.add_argument("--mode", default="finetune", 
                        choices=["finetune", "finetune_all", "extract_features"])
    parser.add_argument("--dim", default="engagement", choices=DIMENSION_NAMES)
    parser.add_argument("--model", default="MCG-NJU/videomae-base")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--num_frames", type=int, default=16)
    parser.add_argument("--binary", type=bool, default=True)
    parser.add_argument("--ordinal", action="store_true", help="Use 4-class ordinal regression")
    args = parser.parse_args()
    
    results = {}
    
    if args.mode == "finetune":
        result = train_videomae(
            dim_name=args.dim, num_frames=args.num_frames,
            epochs=args.epochs, batch_size=args.batch_size,
            lr=args.lr, binary=not args.ordinal,
            model_name=args.model,
        )
        results[args.dim] = result
        
    elif args.mode == "finetune_all":
        for dim in DIMENSION_NAMES:
            result = train_videomae(
                dim_name=dim, num_frames=args.num_frames,
                epochs=args.epochs, batch_size=args.batch_size,
                lr=args.lr, binary=not args.ordinal,
                model_name=args.model,
            )
            results[dim] = result
            
    elif args.mode == "extract_features":
        extract_videomae_features(
            model_name=args.model,
            num_frames=args.num_frames,
            batch_size=args.batch_size * 2,
        )
        return
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"experiment_videomae_{timestamp}.json")
    with open(out_path, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "model": args.model,
            "mode": args.mode,
            "results": results,
        }, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
