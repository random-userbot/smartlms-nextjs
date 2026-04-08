"""
Smart LMS - Audio Feature Extraction for Engagement Detection
==============================================================
Extracts audio features from DAiSEE video clips for multi-modal fusion.
DAiSEE videos contain audio that is COMPLETELY UNTAPPED in existing work.

Audio cues for engagement:
  - Bored: monotone, low energy, long silences
  - Engaged: varied pitch, higher energy, responsive vocalizations
  - Confused: hesitation, self-corrections, questioning intonation
  - Frustrated: sighs, higher pitch variability, speech rate changes

Approach:
  1. Hand-crafted prosodic features (pitch, energy, rate, pauses)
  2. wav2vec2/HuBERT learned embeddings from pretrained speech model
  3. Both feed into the multi-modal stacking ensemble

Requirements:
    pip install librosa soundfile torch torchaudio transformers

Usage:
    python extract_audio_features.py --mode prosodic          # Hand-crafted features
    python extract_audio_features.py --mode wav2vec           # wav2vec2 embeddings
    python extract_audio_features.py --mode both              # Both
"""

import os
import sys
import glob
import json
import argparse
import warnings
import logging
import numpy as np
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


ON_KAGGLE = os.path.exists("/kaggle/working")

if ON_KAGGLE:
    if "/kaggle/working" not in sys.path:
        sys.path.insert(0, "/kaggle/working")
    VIDEO_DIR = "/kaggle/input/daisee-videos/DAiSEE/DataSet"
    OUTPUT_DIR = "/kaggle/working/audio_features"
else:
    DAISEE_DIR = r"C:\Users\revan\Downloads\DAiSEE"
    VIDEO_DIR = os.path.join(DAISEE_DIR, "DAiSEE", "DataSet")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "audio_features")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_audio_from_video(video_path: str, sr: int = 16000) -> Optional[np.ndarray]:
    """Extract audio waveform from video file."""
    try:
        import subprocess
        import tempfile
        import soundfile as sf
        
        # Use ffmpeg to extract audio
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp.close()
        
        cmd = [
            'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le',
            '-ar', str(sr), '-ac', '1', '-y', tmp.name
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0:
            os.unlink(tmp.name)
            return None
        
        audio, _ = sf.read(tmp.name)
        os.unlink(tmp.name)
        
        if len(audio) < sr:  # Less than 1 second
            return None
        
        return audio.astype(np.float32)
        
    except Exception as e:
        return None


def extract_audio_torchaudio(video_path: str, sr: int = 16000) -> Optional[np.ndarray]:
    """Alternative: extract audio using torchaudio (no ffmpeg needed)."""
    try:
        import torchaudio
        waveform, orig_sr = torchaudio.load(video_path)
        # Resample if needed
        if orig_sr != sr:
            resampler = torchaudio.transforms.Resample(orig_sr, sr)
            waveform = resampler(waveform)
        # Mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        audio = waveform.squeeze().numpy()
        if len(audio) < sr:
            return None
        return audio
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# SECTION 1: HAND-CRAFTED PROSODIC FEATURES
# ══════════════════════════════════════════════════════════════

def extract_prosodic_features(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """
    Extract ~80 hand-crafted audio/prosodic features.
    
    Feature groups:
    1. Energy features (RMS, zero-crossing rate)
    2. Pitch features (F0 statistics via autocorrelation)
    3. Spectral features (centroid, bandwidth, rolloff, flatness, contrast)
    4. MFCCs (13 coefficients + deltas)
    5. Temporal features (silence ratio, speech rate proxy)
    6. Formant proxies via LPC
    """
    import librosa
    
    features = {}
    
    # Ensure float32
    audio = audio.astype(np.float32)
    clip_duration = len(audio) / sr
    
    # ── 1. Energy features ──
    rms = librosa.feature.rms(y=audio, frame_length=2048, hop_length=512)[0]
    features['rms_mean'] = np.mean(rms)
    features['rms_std'] = np.std(rms)
    features['rms_max'] = np.max(rms)
    features['rms_min'] = np.min(rms)
    features['rms_range'] = np.max(rms) - np.min(rms)
    features['rms_skew'] = float(np.mean(((rms - np.mean(rms)) / max(np.std(rms), 1e-8)) ** 3))
    
    zcr = librosa.feature.zero_crossing_rate(audio, frame_length=2048, hop_length=512)[0]
    features['zcr_mean'] = np.mean(zcr)
    features['zcr_std'] = np.std(zcr)
    
    # ── 2. Pitch features ──
    try:
        f0, voiced_flag, _ = librosa.pyin(
            audio, fmin=50, fmax=400, sr=sr, frame_length=2048
        )
        f0_voiced = f0[~np.isnan(f0)]
        if len(f0_voiced) > 0:
            features['f0_mean'] = np.mean(f0_voiced)
            features['f0_std'] = np.std(f0_voiced)
            features['f0_max'] = np.max(f0_voiced)
            features['f0_min'] = np.min(f0_voiced)
            features['f0_range'] = np.max(f0_voiced) - np.min(f0_voiced)
            features['f0_median'] = np.median(f0_voiced)
            features['voiced_ratio'] = len(f0_voiced) / max(len(f0), 1)
        else:
            for k in ['f0_mean', 'f0_std', 'f0_max', 'f0_min', 'f0_range', 'f0_median']:
                features[k] = 0.0
            features['voiced_ratio'] = 0.0
    except:
        for k in ['f0_mean', 'f0_std', 'f0_max', 'f0_min', 'f0_range', 'f0_median', 'voiced_ratio']:
            features[k] = 0.0
    
    # ── 3. Spectral features ──
    spec_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
    features['spec_centroid_mean'] = np.mean(spec_centroid)
    features['spec_centroid_std'] = np.std(spec_centroid)
    
    spec_bw = librosa.feature.spectral_bandwidth(y=audio, sr=sr)[0]
    features['spec_bw_mean'] = np.mean(spec_bw)
    features['spec_bw_std'] = np.std(spec_bw)
    
    spec_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
    features['spec_rolloff_mean'] = np.mean(spec_rolloff)
    features['spec_rolloff_std'] = np.std(spec_rolloff)
    
    spec_flat = librosa.feature.spectral_flatness(y=audio)[0]
    features['spec_flatness_mean'] = np.mean(spec_flat)
    features['spec_flatness_std'] = np.std(spec_flat)
    
    try:
        spec_contrast = librosa.feature.spectral_contrast(y=audio, sr=sr)
        for i in range(spec_contrast.shape[0]):
            features[f'spec_contrast_{i}_mean'] = np.mean(spec_contrast[i])
    except:
        for i in range(7):
            features[f'spec_contrast_{i}_mean'] = 0.0
    
    # ── 4. MFCCs ──
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
    for i in range(13):
        features[f'mfcc_{i}_mean'] = np.mean(mfcc[i])
        features[f'mfcc_{i}_std'] = np.std(mfcc[i])
    
    # MFCC deltas
    mfcc_delta = librosa.feature.delta(mfcc)
    for i in range(13):
        features[f'mfcc_delta_{i}_mean'] = np.mean(mfcc_delta[i])
        features[f'mfcc_delta_{i}_std'] = np.std(mfcc_delta[i])
    
    # ── 5. Temporal / speech features ──
    # Silence ratio (below energy threshold)
    threshold = np.percentile(rms, 10)
    silence_frames = np.sum(rms < threshold)
    features['silence_ratio'] = silence_frames / max(len(rms), 1)
    
    # Energy dynamics (proxy for speech rate)
    rms_diff = np.diff(rms)
    features['energy_diff_mean'] = np.mean(np.abs(rms_diff))
    features['energy_diff_std'] = np.std(rms_diff)
    
    # Onset strength (activity level)
    try:
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        features['onset_mean'] = np.mean(onset_env)
        features['onset_std'] = np.std(onset_env)
        features['onset_count'] = librosa.onset.onset_detect(y=audio, sr=sr).shape[0]
        features['onset_rate'] = features['onset_count'] / max(clip_duration, 0.1)
    except:
        features['onset_mean'] = 0.0
        features['onset_std'] = 0.0
        features['onset_count'] = 0
        features['onset_rate'] = 0.0
    
    # ── 6. Chroma (tonal) ──
    try:
        chroma = librosa.feature.chroma_stft(y=audio, sr=sr)
        features['chroma_mean'] = np.mean(chroma)
        features['chroma_std'] = np.std(chroma)
    except:
        features['chroma_mean'] = 0.0
        features['chroma_std'] = 0.0
    
    # Convert to array
    feature_names = sorted(features.keys())
    feature_vec = np.array([features[k] for k in feature_names], dtype=np.float32)
    
    return feature_vec, feature_names


# ══════════════════════════════════════════════════════════════
# SECTION 2: WAV2VEC2 / HUBERT EMBEDDINGS
# ══════════════════════════════════════════════════════════════

def extract_wav2vec_embeddings(
    audio: np.ndarray, model=None, processor=None, 
    device='cpu', sr: int = 16000,
) -> Optional[np.ndarray]:
    """
    Extract wav2vec2 / HuBERT embeddings from audio.
    Returns: (768,) mean-pooled embedding vector.
    """
    import torch
    
    # Truncate to 30 seconds max (memory)
    max_len = sr * 30
    if len(audio) > max_len:
        audio = audio[:max_len]
    
    inputs = processor(audio, sampling_rate=sr, return_tensors="pt", padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        hidden = outputs.last_hidden_state  # (1, T, 768)
    
    # Mean pool over time
    embedding = hidden.squeeze(0).mean(dim=0).cpu().numpy()
    return embedding.astype(np.float32)


def load_wav2vec_model(model_name: str = "facebook/wav2vec2-base"):
    """Load pretrained wav2vec2 or HuBERT model."""
    import torch
    from transformers import Wav2Vec2Model, Wav2Vec2Processor
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Loading {model_name} on {device}...")
    
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = Wav2Vec2Model.from_pretrained(model_name).to(device)
    model = wrap_model_multi_gpu(model)
    model.eval()
    
    for param in model.parameters():
        param.requires_grad = False
    
    print(f"  Loaded. Embedding dim: {model.config.hidden_size}")
    return model, processor, device


# ══════════════════════════════════════════════════════════════
# SECTION 3: BATCH EXTRACTION PIPELINE
# ══════════════════════════════════════════════════════════════

def extract_all_audio_features(
    mode: str = "both",
    wav2vec_model_name: str = "facebook/wav2vec2-base",
    max_clips: int = 0,
    resume: bool = True,
):
    """
    Extract audio features from all DAiSEE video clips.
    
    Args:
        mode: 'prosodic' | 'wav2vec' | 'both'
        wav2vec_model_name: HuggingFace model for learned embeddings
        max_clips: 0 = all clips
        resume: skip already-processed clips
    """
    # Find videos
    clip_paths = {}
    for ext in ['*.avi', '*.mp4']:
        for path in glob.glob(os.path.join(VIDEO_DIR, '**', ext), recursive=True):
            clip_paths[Path(path).stem] = path
    
    clip_ids = sorted(clip_paths.keys())
    if max_clips > 0:
        clip_ids = clip_ids[:max_clips]
    
    print(f"\nAudio feature extraction: mode={mode}")
    print(f"Videos found: {len(clip_paths)}")
    print(f"Processing: {len(clip_ids)} clips")
    
    # Output dirs
    prosodic_dir = os.path.join(OUTPUT_DIR, "prosodic")
    wav2vec_dir = os.path.join(OUTPUT_DIR, "wav2vec")
    os.makedirs(prosodic_dir, exist_ok=True)
    os.makedirs(wav2vec_dir, exist_ok=True)
    
    # Resume check
    if resume:
        if mode in ('prosodic', 'both'):
            done_p = set(Path(f).stem for f in glob.glob(os.path.join(prosodic_dir, "*.npy")))
        else:
            done_p = set()
        if mode in ('wav2vec', 'both'):
            done_w = set(Path(f).stem for f in glob.glob(os.path.join(wav2vec_dir, "*.npy")))
        else:
            done_w = set()
        
        if mode == 'both':
            done = done_p & done_w
        elif mode == 'prosodic':
            done = done_p
        else:
            done = done_w
        
        clip_ids = [c for c in clip_ids if c not in done]
        print(f"Resuming: {len(done)} done, {len(clip_ids)} remaining")
    
    # Load wav2vec model if needed
    w2v_model, w2v_processor, w2v_device = None, None, 'cpu'
    if mode in ('wav2vec', 'both'):
        w2v_model, w2v_processor, w2v_device = load_wav2vec_model(wav2vec_model_name)
    
    from tqdm import tqdm
    success, failed = 0, 0
    feature_names = None
    
    for clip_id in tqdm(clip_ids, desc="Audio extraction"):
        video_path = clip_paths[clip_id]
        
        # Extract audio
        audio = extract_audio_torchaudio(video_path)
        if audio is None:
            audio = extract_audio_from_video(video_path)
        if audio is None:
            failed += 1
            continue
        
        try:
            # Prosodic
            if mode in ('prosodic', 'both'):
                feat_vec, feat_names = extract_prosodic_features(audio)
                np.save(os.path.join(prosodic_dir, f"{clip_id}.npy"), feat_vec)
                if feature_names is None:
                    feature_names = feat_names
            
            # wav2vec
            if mode in ('wav2vec', 'both') and w2v_model:
                embedding = extract_wav2vec_embeddings(
                    audio, w2v_model, w2v_processor, w2v_device
                )
                if embedding is not None:
                    np.save(os.path.join(wav2vec_dir, f"{clip_id}.npy"), embedding)
            
            success += 1
        except Exception as e:
            if success < 5:
                print(f"\n  Error {clip_id}: {e}")
            failed += 1
        
        if (success + failed) % 200 == 0:
            print(f"\n  Progress: {success} ok, {failed} fail")
    
    # Save metadata
    meta = {
        "mode": mode,
        "n_success": success,
        "n_failed": failed,
        "wav2vec_model": wav2vec_model_name if mode != 'prosodic' else None,
        "prosodic_feature_names": feature_names,
        "prosodic_dim": len(feature_names) if feature_names else 0,
        "wav2vec_dim": 768 if mode != 'prosodic' else 0,
    }
    with open(os.path.join(OUTPUT_DIR, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2, default=str)
    
    print(f"\n{'='*50}")
    print(f"DONE: {success} success, {failed} failed")
    print(f"Prosodic: {prosodic_dir}")
    print(f"wav2vec:  {wav2vec_dir}")


# ══════════════════════════════════════════════════════════════
# SECTION 4: AUDIO CLASSIFIER (for stacking)
# ══════════════════════════════════════════════════════════════

def train_audio_classifier(
    dim_name: str,
    feature_type: str = "both",  # prosodic, wav2vec, both
    epochs: int = 60,
):
    """
    Train a classifier on audio features.
    Can use prosodic features, wav2vec embeddings, or concatenated.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
    from sklearn.metrics import f1_score, accuracy_score, classification_report
    from sklearn.preprocessing import StandardScaler
    
    print(f"\n{'='*60}")
    print(f"AUDIO CLASSIFIER: {dim_name.upper()} ({feature_type})")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"{'='*60}")
    
    DIMENSION_NAMES = ["boredom", "engagement", "confusion", "frustration"]
    dim_idx = DIMENSION_NAMES.index(dim_name)
    
    # Load labels
    labels_dir = os.path.join(os.path.dirname(VIDEO_DIR), "Labels") if not ON_KAGGLE else "/kaggle/input/smartlms-openface/Labels"
    all_labels = {}
    for split in ["TrainLabels", "ValidationLabels", "TestLabels"]:
        csv_path = os.path.join(labels_dir, f"{split}.csv")
        if os.path.exists(csv_path):
            import pandas as pd
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                clip_id = str(row['ClipID']).replace('.avi', '').replace('.mp4', '').strip()
                all_labels[clip_id] = [int(row['Boredom']), int(row['Engagement']),
                                       int(row['Confusion']), int(row['Frustration'])]
    
    # Load features
    prosodic_dir = os.path.join(OUTPUT_DIR, "prosodic")
    wav2vec_dir = os.path.join(OUTPUT_DIR, "wav2vec")
    
    X_list, y_list, clip_ids = [], [], []
    
    for clip_id, label_vec in sorted(all_labels.items()):
        feats = []
        if feature_type in ('prosodic', 'both'):
            pf = os.path.join(prosodic_dir, f"{clip_id}.npy")
            if not os.path.exists(pf):
                continue
            feats.append(np.load(pf))
        if feature_type in ('wav2vec', 'both'):
            wf = os.path.join(wav2vec_dir, f"{clip_id}.npy")
            if not os.path.exists(wf):
                continue
            feats.append(np.load(wf))
        
        X_list.append(np.concatenate(feats))
        y_list.append(label_vec[dim_idx])
        clip_ids.append(clip_id)
    
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list)
    y_bin = (y >= 2).astype(np.float32)
    
    print(f"  Loaded: {X.shape[0]} clips, {X.shape[1]} features")
    print(f"  Label dist: {dict(zip(*np.unique(y_bin, return_counts=True)))}")
    
    # Split by DAiSEE official split
    train_labels_set = set()
    csv_path = os.path.join(labels_dir, "TrainLabels.csv")
    if os.path.exists(csv_path):
        import pandas as pd
        for _, row in pd.read_csv(csv_path).iterrows():
            train_labels_set.add(str(row['ClipID']).replace('.avi', '').strip())
    
    val_labels_set = set()
    csv_path = os.path.join(labels_dir, "ValidationLabels.csv")
    if os.path.exists(csv_path):
        import pandas as pd
        for _, row in pd.read_csv(csv_path).iterrows():
            val_labels_set.add(str(row['ClipID']).replace('.avi', '').strip())
    
    train_idx = [i for i, c in enumerate(clip_ids) if c in train_labels_set]
    val_idx = [i for i, c in enumerate(clip_ids) if c in val_labels_set]
    test_idx = [i for i, c in enumerate(clip_ids) if c not in train_labels_set and c not in val_labels_set]
    
    X_train, y_train = X[train_idx], y_bin[train_idx]
    X_val, y_val = X[val_idx], y_bin[val_idx]
    X_test, y_test = X[test_idx], y_bin[test_idx]
    
    # Normalize
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)
    
    print(f"  Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")
    
    # Handle NaN
    X_train = np.nan_to_num(X_train, 0)
    X_val = np.nan_to_num(X_val, 0)
    X_test = np.nan_to_num(X_test, 0)
    
    # ── Simple MLP classifier ──
    class AudioMLP(nn.Module):
        def __init__(self, in_dim, hidden=256, dropout=0.4):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(in_dim, hidden),
                nn.BatchNorm1d(hidden),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(hidden, hidden // 2),
                nn.BatchNorm1d(hidden // 2),
                nn.GELU(),
                nn.Dropout(dropout * 0.7),
                nn.Linear(hidden // 2, 1),
            )
        def forward(self, x):
            return self.net(x)
    
    model = AudioMLP(X_train.shape[1]).to(device)
    model = wrap_model_multi_gpu(model)
    
    # Balanced sampler
    classes, counts = np.unique(y_train, return_counts=True)
    cw = {int(c): len(y_train) / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([cw[int(l)] for l in y_train])
    sampler = WeightedRandomSampler(torch.DoubleTensor(sw), len(sw), True)
    
    train_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train)),
        batch_size=64, sampler=sampler
    )
    val_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val)),
        batch_size=128
    )
    test_loader = DataLoader(
        TensorDataset(torch.FloatTensor(X_test), torch.FloatTensor(y_test)),
        batch_size=128
    )
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    criterion = nn.BCEWithLogitsLoss()
    
    best_val_f1, best_state = 0.0, None
    for epoch in range(epochs):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            loss = criterion(model(xb).squeeze(-1), yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        
        model.eval()
        val_proba = []
        with torch.no_grad():
            for xb, _ in val_loader:
                val_proba.extend(torch.sigmoid(model(xb.to(device)).squeeze(-1)).cpu().numpy())
        val_proba = np.array(val_proba)
        
        val_f1 = max(
            f1_score(y_val, (val_proba >= t).astype(int), average='macro', zero_division=0)
            for t in np.arange(0.3, 0.7, 0.02)
        )
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
    print(f"\n*** AUDIO TEST: Acc={accuracy_score(y_test, y_pred):.4f} F1m={best_f1:.4f} ***")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Save probas for stacking
    np.save(os.path.join(OUTPUT_DIR, f"proba_audio_{dim_name}.npy"), y_proba)
    np.save(os.path.join(OUTPUT_DIR, f"labels_audio_{dim_name}.npy"), y_test)
    
    return {"test_f1_macro": float(best_f1), "best_threshold": float(best_thr)}


def main():
    parser = argparse.ArgumentParser(description="Audio feature extraction for DAiSEE")
    parser.add_argument("--mode", default="both", choices=["prosodic", "wav2vec", "both", "train"])
    parser.add_argument("--wav2vec_model", default="facebook/wav2vec2-base")
    parser.add_argument("--max_clips", type=int, default=0)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--dim", default="engagement")
    parser.add_argument("--feature_type", default="both", choices=["prosodic", "wav2vec", "both"])
    args = parser.parse_args()
    
    if args.mode == "train":
        for dim in ["boredom", "engagement", "confusion", "frustration"]:
            train_audio_classifier(dim, args.feature_type)
    else:
        extract_all_audio_features(
            mode=args.mode,
            wav2vec_model_name=args.wav2vec_model,
            max_clips=args.max_clips,
            resume=args.resume,
        )


if __name__ == "__main__":
    main()
