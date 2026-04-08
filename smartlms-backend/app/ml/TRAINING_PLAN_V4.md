# Smart LMS v5 — SOTA Model Improvement Training Plan
## GPU Budget: 80 hrs/week T4 (multiple Kaggle accounts)

## Current Baseline (v3)

| Model | Boredom | Engagement | Confusion | Frustration | **Avg F1m** |
|-------|---------|------------|-----------|-------------|-------------|
| XGBoost+Optuna v3 | 0.575 | 0.616 | 0.551 | 0.538 | **0.570** |
| BiLSTM+Attn+Focal v3 | 0.532 | 0.566 | 0.525 | 0.526 | **0.537** |
| Ensemble (equal) v3 | 0.573 | 0.601 | 0.555 | 0.521 | **0.563** |

**Target:** Push from **0.563 → 0.65+** F1-macro (**SOTA** for DAiSEE)

---

## 9 Improvements (expanded from 5 → 9 with 80hr budget)

### Stream A: OpenFace Features (v4 — carry forward)
1. **Temporal Transformer** — 4-layer, 8-head self-attention on frame sequences
2. **BiLSTM-GRU Hybrid** — Multi-scale conv + SE block + 3-layer BiLSTM→GRU
3. **XGBoost with 5-Fold CV** — Optuna-tuned with confidence intervals

### Stream B: End-to-End Video (NEW with 80hrs)
4. **VideoMAE V2 Fine-Tuning** — Pretrained video transformer, fine-tuned on DAiSEE
   - Biggest single improvement: replaces entire OpenFace pipeline
   - Uses gradient checkpointing + mixed precision for T4 16GB
   - ~8-12 hrs for all 4 dimensions
5. **ViT/DINOv2 Face Embeddings** — Per-frame face crops → pretrained ViT → classifier

### Stream C: Audio (NEW with 80hrs)
6. **Prosodic Features** — Pitch, energy, MFCCs, speech rate, silence ratio (~80 features)
7. **wav2vec2 Embeddings** — Pretrained speech model → 768-dim learned audio features
   - Bored = monotone/silent; Engaged = varied pitch/active speech

### Stream D: Advanced Techniques (NEW with 80hrs)
8. **CORAL Ordinal Regression** — 4-class ordered prediction instead of binary
   - Models P(y>0), P(y>1), P(y>2) jointly with shared backbone
   - Preserves label ordering that binarization destroys
9. **Multi-Modal Stacking + Ablation Study** — XGBoost meta-learner over ALL 6 streams

### Bonus: Data Augmentation (all deep models)
- Temporal jittering, shifting, masking, crop-resize, speed perturbation
- Video: horizontal flip, brightness, noise
- Mixup (α=0.2) for regularization

---

## 4-Week Training Schedule (80 hrs T4/week, split across accounts)

### Week 1: OpenFace Models (~20 hrs)
> **Account A** (30 hrs available)

| Day | Task | GPU Hrs | Account |
|-----|------|---------|---------|
| Mon | Upload OpenFace dataset + scripts to Kaggle | 0 | — |
| Mon | Run Temporal Transformer (4 dims, 120 epochs) | 4 | A |
| Tue | Run BiLSTM-GRU v4 (4 dims, 100 epochs) | 3 | A |
| Wed | Run XGBoost 5-fold CV (4 dims, 30 Optuna trials) | 3 | A |
| Thu | Run Stacking Ensemble (3 OpenFace models) | 1 | A |
| Fri | Hyperparameter tuning (repeat best config) | 4 | A |
| Sat | CORAL ordinal regression on OpenFace sequences | 4 | A |
| **Subtotal** | | **~19 hrs** | |

**Checkpoint:** 3 OpenFace models + CORAL trained. Stacking shows initial gains.

### Week 2: VideoMAE + ViT Embeddings (~25 hrs)
> **Account B + C** (30 hrs each available)

| Day | Task | GPU Hrs | Account |
|-----|------|---------|---------|
| Mon | Upload raw DAiSEE videos as Kaggle dataset | 0 | — |
| Mon | VideoMAE fine-tune: boredom + engagement | 5 | B |
| Mon | ViT face embedding extraction (Train split) | 5 | C |
| Tue | VideoMAE fine-tune: confusion + frustration | 5 | B |
| Tue | ViT embedding extraction (Val + Test split) | 3 | C |
| Wed | Train ViT classifier (4 dims) | 3 | C |
| Thu | VideoMAE feature extraction (for stacking) | 3 | B |
| Fri | Buffer / re-runs | 2 | B/C |
| **Subtotal** | | **~26 hrs** | |

**Checkpoint:** VideoMAE trained (HUGE expected gains), ViT embeddings ready.

### Week 3: Audio + Multi-Modal Fusion (~25 hrs)
> **Account A + B**

| Day | Task | GPU Hrs | Account |
|-----|------|---------|---------|
| Mon | Audio: prosodic feature extraction (all clips) | 3 | A |
| Mon | Audio: wav2vec2 embedding extraction (all clips) | 6 | B |
| Tue | Train audio classifiers (4 dims, prosodic + w2v) | 2 | A |
| Wed | Multi-modal stacking (all 6 streams) | 3 | A |
| Thu | Ablation study (all modality combos) | 4 | A |
| Fri | CORAL ordinal + multi-modal fusion combined | 4 | B |
| Sat | Buffer / analysis | 3 | A/B |
| **Subtotal** | | **~25 hrs** | |

**Checkpoint:** All modalities combined. Final F1m numbers ready.

### Week 4: Paper-Ready Results (~10 hrs)
> **Account A**

| Day | Task | GPU Hrs | Account |
|-----|------|---------|---------|
| Mon | Final ensemble with tuned weights | 3 | A |
| Tue | Generate all paper figures + tables | 2 | A |
| Wed | SHAP analysis for interpretability | 3 | A |
| Thu | Statistical significance tests (McNemar's, bootstrap) | 2 | A |
| Fri | Update research paper | 0 | — |
| **Subtotal** | | **~10 hrs** | |

**Total GPU usage: ~80 hrs across 4 weeks** (fits within 80 hrs/week budget with margin)

---

## Kaggle Account Strategy

| Account | Week 1 | Week 2 | Week 3 | Week 4 | Total |
|---------|--------|--------|--------|--------|-------|
| **A** | OpenFace models (19h) | — | Audio + fusion (19h) | Final (10h) | ~48h |
| **B** | — | VideoMAE (15h) | wav2vec + CORAL (10h) | — | ~25h |
| **C** | — | ViT embeds (11h) | — | — | ~11h |

### Kaggle Datasets to Create

#### Dataset 1: `smartlms-openface` (Week 1)
```
openface_output/        # ~9000 CSVs
Labels/                 # 4 CSV files
train_model_v2.py       # Data utilities
train_model_v3.py       # Feature selection
train_model_v4.py       # v4 pipeline
train_multimodal_v5.py  # v5 fusion + CORAL
```

#### Dataset 2: `daisee-videos` (Week 2)
```
DAiSEE/DataSet/Train/       # ~5500 videos
DAiSEE/DataSet/Validation/  # ~1800 videos
DAiSEE/DataSet/Test/        # ~1800 videos
```

#### Dataset 3: `smartlms-vit-embeddings` (Week 2 → Week 3)
```
*.npy                   # ~9000 embedding files (produced by Account C)
```

#### Dataset 4: `smartlms-probas` (Week 3 → Week 4)
```
proba_*.npy             # All model probability outputs for stacking
labels_*.npy            # Test labels
```

---

## Expected Results (with 80hr budget)

| Model | Expected F1m | v3 Baseline | Gain |
|-------|:------------|:------------|:-----|
| Transformer v4 | 0.56-0.60 | 0.537 | +2-6% |
| BiLSTM-GRU v4 | 0.55-0.58 | 0.537 | +1-4% |
| XGBoost CV v4 | 0.57-0.60 | 0.570 | +0-3% |
| **VideoMAE** (NEW) | **0.58-0.64** | N/A | **Largest single** |
| ViT Classifier | 0.53-0.57 | N/A | Orthogonal signal |
| Audio Classifier | 0.50-0.55 | N/A | Untapped modality |
| CORAL Ordinal | 0.57-0.62 | N/A | Preserves label order |
| **6-Stream Stacking** | **0.63-0.68** | 0.563 | **+7-12%** |

### Why Multi-Modal Wins
- XGBoost understands **statistical patterns** in AU features
- Transformer captures **long-range temporal dynamics**
- VideoMAE learns **raw facial expressions** end-to-end
- Audio detects **vocal engagement cues** (completely different modality)
- CORAL preserves **ordinal label relationships**
- Stacking learns **when to trust each model**

---

## Architecture Comparison for Paper

| Approach | Modality | Input | Parameters | GPU Time |
|----------|----------|-------|-----------|----------|
| XGBoost+Optuna | OpenFace tabular | 350 features | ~500 trees | 2h (CPU) |
| Temporal Transformer | OpenFace sequences | (60, 49) | ~300K | 4h T4 |
| BiLSTM-GRU Hybrid | OpenFace sequences | (60, 49) | ~1.5M | 3h T4 |
| VideoMAE V2 | Raw video | (16, 3, 224, 224) | ~86M | 10h T4 |
| ViT-B/16 Classifier | Face crops → embeds | (16, 768) | ~150K | 3h T4 |
| Audio MLP | Prosodic + wav2vec | ~850 features | ~200K | 1h T4 |
| CORAL Transformer | OpenFace sequences | (60, 49) | ~300K | 4h T4 |
| Stacking Meta-Learner | All probabilities | 6+ features | ~200 trees | <1h |

---

## Hyperparameter Search Space

### Temporal Transformer
| Parameter | Range | Default |
|-----------|-------|---------|
| d_model | [64, 128, 256] | 128 |
| nhead | [4, 8] | 8 |
| num_layers | [2, 4, 6] | 4 |
| dim_ff | [128, 256, 512] | 256 |
| dropout | [0.2, 0.3, 0.4] | 0.3 |
| seq_len | [30, 60, 90] | 60 |

### VideoMAE Fine-Tuning
| Parameter | Range | Default |
|-----------|-------|---------|
| lr (backbone) | [1e-6, 2e-5] | 2e-6 |
| lr (head) | [1e-5, 2e-4] | 2e-5 |
| num_frames | [8, 16, 32] | 16 |
| gradient_accum | [4, 8, 16] | 8 |
| epochs | [15, 30, 50] | 30 |
| weight_decay | [0.01, 0.05, 0.1] | 0.05 |

### CORAL Ordinal
| Parameter | Range | Default |
|-----------|-------|---------|
| Same as Transformer | + ordinal-specific | — |

### XGBoost (Optuna auto-tuned)
| Parameter | Range |
|-----------|-------|
| n_estimators | [200, 600] |
| max_depth | [3, 8] |
| learning_rate | [0.01, 0.15] |
| subsample | [0.6, 1.0] |
| colsample_bytree | [0.5, 1.0] |

---

## Files Created

| File | Purpose | GPU Needed |
|------|---------|-----------|
| `app/ml/train_model_v4.py` | OpenFace: Transformer + BiLSTM-GRU + XGB CV + stacking | T4 ~20h |
| `app/ml/train_videomae.py` | VideoMAE V2 fine-tuning on raw DAiSEE video | T4 ~12h |
| `app/ml/extract_face_embeddings.py` | ViT-B/16 face crop embedding extraction | T4 ~8h |
| `app/ml/extract_audio_features.py` | Prosodic features + wav2vec2 audio embeddings | T4 ~10h |
| `app/ml/train_multimodal_v5.py` | CORAL ordinal + multi-modal stacking + ablation | T4 ~10h |
| `app/ml/TRAINING_PLAN_V4.md` | This document | — |

---

## Ablation Study Matrix (for paper Table)

The ablation study tests every combination of modalities:

| # | OpenFace XGB | OpenFace Transformer | OpenFace BiLSTM | VideoMAE | ViT | Audio | Expected F1m |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | ✓ | | | | | | 0.57 |
| 2 | | ✓ | | | | | 0.58 |
| 3 | | | | ✓ | | | 0.62 |
| 4 | ✓ | ✓ | ✓ | | | | 0.61 |
| 5 | ✓ | ✓ | ✓ | ✓ | | | 0.64 |
| 6 | ✓ | ✓ | ✓ | ✓ | ✓ | | 0.65 |
| 7 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **0.67** |

This shows that each modality adds incremental value → strong paper narrative.
