# Kaggle Step-by-Step Execution Guide

> **Total:** 3 Kaggle accounts, 5 Kaggle datasets, 6 notebooks, ~80 hrs T4 GPU

---

## PHASE 0: Upload Training Scripts (5 min)

Your data datasets (`smartlms-openface`, `daisee-videos`) are already uploaded. ✅

You just need to upload the **latest Python scripts** (with multi-GPU T4x2 support).

### Dataset: `smartlms-scripts` (tiny, ~50 KB)

**Step 1:** Create a folder on your desktop called `smartlms-scripts`:

```
smartlms-scripts/
├── train_model_v2.py         ← Copy from smartlms-backend\app\ml\
├── train_model_v3.py         ← Copy from smartlms-backend\app\ml\
├── train_model_v4.py         ← Copy from smartlms-backend\app\ml\
├── train_multimodal_v5.py    ← Copy from smartlms-backend\app\ml\
├── extract_face_embeddings.py ← Copy from smartlms-backend\app\ml\
├── train_videomae.py          ← Copy from smartlms-backend\app\ml\
└── extract_audio_features.py  ← Copy from smartlms-backend\app\ml\
```

**Step 2:** Go to https://www.kaggle.com/datasets → **New Dataset** → **Upload**

- Title: `smartlms-scripts`
- Drag all 7 `.py` files
- Set visibility: **Private**
- Click **Create**
- ⏱ Upload time: ~10 seconds

**Step 3:** Share this dataset with your other Kaggle accounts:
- Dataset page → **Settings** → **Collaborators** → add the other usernames

> **Why a separate dataset?** Your existing openface/videos datasets are 12-14 GB each.
> Re-uploading just to include scripts would waste time. This tiny dataset keeps
> scripts separate so you can update them anytime without re-uploading data.

### Later datasets (produced during training):

- **`smartlms-vit-embeddings`** — created from Week 2 output (ViT extraction)
- **`smartlms-probas`** — created from Week 3 output (all model probability files)

---

## PHASE 1: Week 1 — OpenFace Models (Account A)

> **GPU needed:** ~19 hrs T4
> **Account:** A
> **Datasets attached:** `smartlms-openface` + `smartlms-scripts`

### Notebook 1: `smartlms-v4-openface`

**Step 1:** Go to https://www.kaggle.com/code → **New Notebook**

**Step 2:** Settings (right sidebar):
- **Accelerator:** GPU T4 x2 (or GPU T4)
- **Internet:** ON (needed for pip installs)
- **Persistence:** Files (keeps outputs between sessions)

**Step 3:** Add datasets: Click **+ Add Data** → search `smartlms-openface` → Add, then also add `smartlms-scripts`

**Step 4:** Create cells in order:

---

#### Cell 1: Setup
```python
# ── Install dependencies ──
!pip install -q xgboost optuna shap transformers

import torch, os, sys, shutil
print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
if torch.cuda.device_count() > 1:
    print(f"🚀 Multi-GPU: {torch.cuda.device_count()} GPUs — DataParallel enabled")
```

#### Cell 2: Copy scripts to working directory
```python
# Copy training scripts from dataset to working directory
WORK = "/kaggle/working"
os.makedirs(f"{WORK}/app/ml", exist_ok=True)

# Create __init__.py files for imports
open(f"{WORK}/app/__init__.py", "w").close()
open(f"{WORK}/app/ml/__init__.py", "w").close()

# Auto-find scripts dataset (handles nested folders & dataset name variations)
import glob as _g
def find_script(name):
    hits = _g.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None

scripts = [
    "train_model_v2.py", "train_model_v3.py", "train_model_v4.py",
    "train_multimodal_v5.py", "extract_face_embeddings.py",
    "train_videomae.py", "extract_audio_features.py"
]
for s in scripts:
    found = find_script(s)
    if found:
        shutil.copy(found, f"{WORK}/app/ml/{s}")
        print(f"✓ Copied {s}  ← {found}")
    else:
        print(f"✗ Not found: {s}")

sys.path.insert(0, WORK)
os.chdir(WORK)
```

#### Cell 3: Verify data paths (auto-detect)
```python
import glob, subprocess

# ── Auto-detect dataset paths ──
print("📂 Attached datasets:")
for d in os.listdir("/kaggle/input"):
    print(f"  /kaggle/input/{d}/")

# Find OpenFace CSVs
csvs = glob.glob("/kaggle/input/**/openface_output/*.csv", recursive=True)
if not csvs:
    csvs = glob.glob("/kaggle/input/**/*.csv", recursive=True)
    csvs = [c for c in csvs if "openface" in c.lower() or len(csvs) > 100]
print(f"\nOpenFace CSVs found: {len(csvs)}")
if csvs:
    print(f"  Example: {csvs[0]}")
    OPENFACE_DIR = os.path.dirname(csvs[0])
    print(f"  Directory: {OPENFACE_DIR}")

# Find Labels
result = subprocess.run(["find", "/kaggle/input", "-name", "AllLabels.csv"], capture_output=True, text=True)
label_paths = result.stdout.strip().split("\n")
print(f"\nLabel files: {label_paths}")
if label_paths and label_paths[0]:
    LABELS_DIR = os.path.dirname(label_paths[0])
    print(f"  Labels directory: {LABELS_DIR}")

# Verify expected counts
print(f"\n✅ Expected: ~8231 CSVs, 4 label files (AllLabels, Train, Validation, Test)")
```

#### Cell 4: Train Temporal Transformer (~4 hrs)
```python
# This trains all 4 dimensions (boredom, engagement, confusion, frustration)
# Each dimension takes ~50-60 min on T4
!python app/ml/train_model_v4.py --mode transformer --seq_len 60 --transformer_epochs 120
```

#### Cell 5: Train BiLSTM-GRU (~3 hrs)
```python
!python app/ml/train_model_v4.py --mode bilstm_v4 --seq_len 60 --bilstm_epochs 100
```

#### Cell 6: Train XGBoost 5-Fold CV (~3 hrs)
```python
!python app/ml/train_model_v4.py --mode xgboost_cv --n_folds 5 --n_trials 30
```

#### Cell 7: Train Stacking Ensemble (~1 hr)
```python
# Stacks the 3 OpenFace models above
!python app/ml/train_model_v4.py --mode stacking
```

#### Cell 8: Train CORAL Ordinal Regression (~4 hrs)
```python
# 4-class ordinal regression on OpenFace sequences
!python app/ml/train_multimodal_v5.py --mode ordinal
```

#### Cell 9: Review results
```python
import json, glob

print("="*80)
print("WEEK 1 RESULTS — OpenFace Models")
print("="*80)

v3_baseline = {
    "XGBoost v3": 0.570, "BiLSTM v3": 0.537, "Ensemble v3": 0.563
}

for rf in sorted(glob.glob("/kaggle/working/experiment_results/*.json")):
    print(f"\n📄 {os.path.basename(rf)}")
    with open(rf) as f:
        data = json.load(f)
    for key, res in data.get('results', {}).items():
        f1m = res.get('test_f1_macro') or res.get('cv_f1_macro_mean') or res.get('stacking_f1_macro', 0)
        print(f"  {key}: F1m = {f1m:.4f}")

print(f"\nv3 baselines: {v3_baseline}")
```

#### Cell 10: Save outputs for download
```python
import shutil

# Zip everything for download
shutil.make_archive("/kaggle/working/week1_models", 'zip', "/kaggle/working/trained_models")
shutil.make_archive("/kaggle/working/week1_results", 'zip', "/kaggle/working/experiment_results")

for f in glob.glob("/kaggle/working/*.zip"):
    size_mb = os.path.getsize(f) / 1e6
    print(f"📦 {os.path.basename(f)}: {size_mb:.1f} MB")

print("\n✅ Download these zip files from the Output tab!")
print("You'll need the proba_*.npy files from trained_models/ for Week 3 fusion.")
```

**Step 5:** Run all cells. Total time: ~15-19 hrs.

> **Tip:** You can run cells 4, 5, 6 one at a time across different sessions if you're worried about the 12-hour session limit. Save & checkpoint between cells. The scripts save models incrementally.

**Step 6:** After completion:
- Go to **Output** tab → download `week1_models.zip` and `week1_results.zip`
- Save these locally — you'll need the proba files for Week 3

---

## PHASE 2: Week 2 — VideoMAE + ViT Embeddings (Accounts B + C in parallel)

> **GPU needed:** ~26 hrs total (split across 2 accounts running simultaneously)
> **Datasets attached:** `smartlms-openface` + `daisee-videos` + `smartlms-scripts`

### Notebook 2: `smartlms-videomae` (Account B, ~15 hrs)

**Step 1:** Log into **Account B** → New Notebook

**Step 2:** Settings: GPU T4, Internet ON, Persistence Files

**Step 3:** Add datasets: `smartlms-openface` + `daisee-videos` + `smartlms-scripts`

**Step 4:** Cells:

#### Cell 1: Setup
```python
!pip install -q transformers accelerate decord av xgboost optuna

import torch, os, sys, shutil
print(f"GPU: {torch.cuda.get_device_name(0)}, Mem: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
if torch.cuda.device_count() > 1:
    print(f"🚀 Multi-GPU: {torch.cuda.device_count()} GPUs — DataParallel enabled")

WORK = "/kaggle/working"
os.makedirs(f"{WORK}/app/ml", exist_ok=True)
open(f"{WORK}/app/__init__.py", "w").close()
open(f"{WORK}/app/ml/__init__.py", "w").close()

import glob as _g
def find_script(name):
    hits = _g.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None

for s in ["train_model_v2.py", "train_model_v3.py", "train_videomae.py"]:
    found = find_script(s)
    if found:
        shutil.copy(found, f"{WORK}/app/ml/{s}")
        print(f"✓ {s}  ← {found}")
    else:
        print(f"✗ Not found: {s}")

sys.path.insert(0, WORK)
os.chdir(WORK)
```

#### Cell 2: Verify videos (auto-detect)
```python
import glob, subprocess

# Auto-detect video paths
print("📂 Attached datasets:")
for d in os.listdir("/kaggle/input"):
    print(f"  /kaggle/input/{d}/")

# Find .avi files
for split in ["Train", "Validation", "Test"]:
    vids = glob.glob(f"/kaggle/input/**/{split}/**/*.avi", recursive=True)
    print(f"{split}: {len(vids)} videos")
    if vids:
        print(f"  Example: {vids[0]}")

# Detect video root (needed by train_videomae.py)
result = subprocess.run(["find", "/kaggle/input", "-name", "*.avi", "-type", "f"], capture_output=True, text=True)
all_vids = [l for l in result.stdout.strip().split("\n") if l]
if all_vids:
    # Find the DataSet root
    for v in all_vids[:1]:
        parts = v.split("/")
        for i, p in enumerate(parts):
            if p in ["Train", "Validation", "Test"]:
                VIDEO_ROOT = "/".join(parts[:i])
                print(f"\n📁 Video root: {VIDEO_ROOT}")
                break
print(f"\n✅ Expected: 4975 Train + 1536 Val + 1720 Test = 8231 total")
```

#### Cell 3: Fine-tune VideoMAE — Engagement (~3 hrs)
```python
# Start with engagement (most important dimension)
!python app/ml/train_videomae.py --mode finetune --dim engagement --epochs 30
```

#### Cell 4: Fine-tune VideoMAE — Boredom (~3 hrs)
```python
!python app/ml/train_videomae.py --mode finetune --dim boredom --epochs 30
```

#### Cell 5: Fine-tune VideoMAE — Confusion (~3 hrs)
```python
!python app/ml/train_videomae.py --mode finetune --dim confusion --epochs 30
```

#### Cell 6: Fine-tune VideoMAE — Frustration (~3 hrs)
```python
!python app/ml/train_videomae.py --mode finetune --dim frustration --epochs 30
```

> **⚠️ Session limit:** Kaggle has a 12-hour session limit. You may need to split this into 2 sessions:
> - Session 1: Cells 3-4 (engagement + boredom, ~6 hrs)
> - Session 2: Cells 5-6 (confusion + frustration, ~6 hrs)
> Models are saved after each dimension, so progress isn't lost.

#### Cell 7: Extract VideoMAE features for stacking
```python
# This extracts [CLS] token features from the fine-tuned models
# Used later in multi-modal stacking
!python app/ml/train_videomae.py --mode extract_features
```

#### Cell 8: Save outputs
```python
import shutil, glob, os

shutil.make_archive("/kaggle/working/videomae_models", 'zip', "/kaggle/working/trained_models")
shutil.make_archive("/kaggle/working/videomae_results", 'zip', "/kaggle/working/experiment_results")

for f in glob.glob("/kaggle/working/*.zip"):
    print(f"📦 {os.path.basename(f)}: {os.path.getsize(f)/1e6:.1f} MB")

# Also list the probability files for fusion
for f in glob.glob("/kaggle/working/trained_models/proba_videomae_*.npy"):
    print(f"🔗 {os.path.basename(f)}: {os.path.getsize(f)/1e3:.1f} KB")

print("\n✅ Download zip files + any proba_videomae_*.npy files!")
```

---

### Notebook 3: `smartlms-vit-embeddings` (Account C, ~11 hrs)

> Run this **simultaneously** with Notebook 2 on Account B!

**Step 1:** Log into **Account C** → New Notebook

**Step 2:** Settings: GPU T4, Internet ON, Persistence Files

**Step 3:** Add datasets: `smartlms-openface` + `daisee-videos` + `smartlms-scripts`

**Step 4:** Cells:

#### Cell 1: Setup
```python
!pip install -q transformers torchvision opencv-python-headless tqdm xgboost optuna

import torch, os, sys, shutil
print(f"GPU: {torch.cuda.get_device_name(0)}")
if torch.cuda.device_count() > 1:
    print(f"🚀 Multi-GPU: {torch.cuda.device_count()} GPUs — DataParallel enabled")

WORK = "/kaggle/working"
os.makedirs(f"{WORK}/app/ml", exist_ok=True)
open(f"{WORK}/app/__init__.py", "w").close()
open(f"{WORK}/app/ml/__init__.py", "w").close()

import glob as _g
def find_script(name):
    hits = _g.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None

for s in ["train_model_v2.py", "train_model_v3.py", "train_model_v4.py", "extract_face_embeddings.py"]:
    found = find_script(s)
    if found:
        shutil.copy(found, f"{WORK}/app/ml/{s}")
        print(f"✓ {s}  ← {found}")
    else:
        print(f"✗ Not found: {s}")

sys.path.insert(0, WORK)
os.chdir(WORK)
```

#### Cell 2: Extract ViT embeddings (~8 hrs)
```python
# Extracts ViT-B/16 face crop embeddings from all 8231 videos
# Supports --resume, so if session dies, just re-run this cell
!python app/ml/extract_face_embeddings.py \
    --video_dir /kaggle/input/daisee-videos/DAiSEE/DataSet \
    --output_dir /kaggle/working/vit_embeddings \
    --sample_fps 2.0 \
    --batch_size 32 \
    --resume
```

#### Cell 3: Train ViT classifier (~3 hrs)
```python
# Train classifier on the extracted embeddings
!python app/ml/train_model_v4.py --mode vit_train
```

#### Cell 4: Save outputs
```python
import shutil, glob, os

# Zip embeddings (these need to be re-uploaded as a dataset for Week 3)
shutil.make_archive("/kaggle/working/vit_embeddings_all", 'zip', "/kaggle/working/vit_embeddings")
shutil.make_archive("/kaggle/working/vit_results", 'zip', "/kaggle/working/experiment_results")

for f in glob.glob("/kaggle/working/*.zip"):
    print(f"📦 {os.path.basename(f)}: {os.path.getsize(f)/1e6:.1f} MB")

# Count embeddings
n = len(glob.glob("/kaggle/working/vit_embeddings/*.npy"))
print(f"\n✅ {n} ViT embeddings extracted")
print("⚠️ Download vit_embeddings_all.zip and re-upload as Kaggle dataset 'smartlms-vit-embeddings'!")
```

**Step 5:** After Notebook 3 finishes:
1. Go to **Output** tab
2. Download `vit_embeddings_all.zip`
3. Unzip on your local machine
4. Go to https://www.kaggle.com/datasets → **New Dataset**
5. Title: `smartlms-vit-embeddings`
6. Upload the unzipped `vit_embeddings/` folder (all `.npy` files)
7. This dataset will be used in Week 3 for multi-modal fusion

---

## PHASE 3: Week 3 — Audio + Multi-Modal Fusion (Accounts A + B)

> **GPU needed:** ~25 hrs total
> **Prerequisites:** Week 1 + Week 2 outputs downloaded

### Step 3.0: Create probas dataset

Before starting Week 3, gather all probability files from Week 1 + Week 2:

1. Create a folder `smartlms-probas/` on your desktop
2. From Week 1 download (`week1_models.zip`), extract all `proba_*.npy` and `labels_*.npy` files into `smartlms-probas/`
3. From Week 2 VideoMAE download, extract `proba_videomae_*.npy` files into `smartlms-probas/`
4. From Week 2 ViT download, extract `proba_vit_*.npy` files into `smartlms-probas/`
5. Upload `smartlms-probas/` as a new Kaggle dataset: Title: `smartlms-probas`

> This folder should contain files like:
> ```
> smartlms-probas/
> ├── proba_xgb_v4_boredom.npy
> ├── proba_xgb_v4_engagement.npy
> ├── proba_xgb_v4_confusion.npy
> ├── proba_xgb_v4_frustration.npy
> ├── proba_transformer_v4_boredom.npy
> ├── proba_transformer_v4_engagement.npy
> ├── ... (similar for bilstm_v4)
> ├── proba_videomae_boredom.npy
> ├── proba_videomae_engagement.npy
> ├── ... (similar for all dims)
> ├── proba_vit_boredom.npy
> ├── ... 
> ├── labels_test_boredom.npy
> ├── labels_test_engagement.npy
> ├── labels_test_confusion.npy
> └── labels_test_frustration.npy
> ```

---

### Notebook 4: `smartlms-audio` (Account B, ~10 hrs)

**Step 1:** Account B → New Notebook

**Step 2:** Settings: GPU T4, Internet ON

**Step 3:** Add datasets: `smartlms-openface` + `daisee-videos` + `smartlms-scripts`

#### Cell 1: Setup
```python
!pip install -q librosa soundfile transformers torchaudio xgboost optuna

import torch, os, sys, shutil
print(f"GPU: {torch.cuda.get_device_name(0)}")
if torch.cuda.device_count() > 1:
    print(f"🚀 Multi-GPU: {torch.cuda.device_count()} GPUs — DataParallel enabled")

WORK = "/kaggle/working"
os.makedirs(f"{WORK}/app/ml", exist_ok=True)
open(f"{WORK}/app/__init__.py", "w").close()
open(f"{WORK}/app/ml/__init__.py", "w").close()

import glob as _g
def find_script(name):
    hits = _g.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None

for s in ["train_model_v2.py", "train_model_v3.py", "extract_audio_features.py"]:
    found = find_script(s)
    if found:
        shutil.copy(found, f"{WORK}/app/ml/{s}")
        print(f"✓ {s}  ← {found}")
    else:
        print(f"✗ Not found: {s}")

sys.path.insert(0, WORK)
os.chdir(WORK)
```

#### Cell 2: Extract prosodic features (~3 hrs)
```python
# Extracts ~80 hand-crafted audio features from all 8231 videos
!python app/ml/extract_audio_features.py --mode prosodic
```

#### Cell 3: Extract wav2vec2 embeddings (~6 hrs)
```python
# Extracts 768-dim learned embeddings from pretrained wav2vec2
!python app/ml/extract_audio_features.py --mode wav2vec
```

#### Cell 4: Train audio classifiers (~2 hrs)
```python
# Trains AudioMLP on prosodic + wav2vec2 features for each dimension
!python app/ml/extract_audio_features.py --mode train
```

#### Cell 5: Save outputs
```python
import shutil, glob, os

shutil.make_archive("/kaggle/working/audio_features_all", 'zip', "/kaggle/working/audio_features")

for f in glob.glob("/kaggle/working/audio_features/*.npy"):
    print(f"🔊 {os.path.basename(f)}: {os.path.getsize(f)/1e3:.1f} KB")

for f in glob.glob("/kaggle/working/trained_models/proba_audio_*.npy"):
    print(f"🔗 {os.path.basename(f)}: {os.path.getsize(f)/1e3:.1f} KB")

print("\n✅ Download audio proba files and add them to the smartlms-probas dataset!")
```

**After Notebook 4:** Download `proba_audio_*.npy` files and add them to the `smartlms-probas` dataset (update the dataset on Kaggle: Dataset page → New Version → upload additional files).

---

### Notebook 5: `smartlms-v5-fusion` (Account A, ~12 hrs)

> **This is the FINAL notebook that produces your paper results!**

**Step 1:** Account A → New Notebook

**Step 2:** Settings: GPU T4, Internet ON

**Step 3:** Add datasets:
- `smartlms-openface`
- `smartlms-scripts`
- `smartlms-vit-embeddings` (from Week 2)
- `smartlms-probas` (all probability files from all weeks)

#### Cell 1: Setup
```python
!pip install -q xgboost optuna shap transformers

import torch, os, sys, shutil
print(f"GPU: {torch.cuda.get_device_name(0)}")

WORK = "/kaggle/working"
os.makedirs(f"{WORK}/app/ml", exist_ok=True)
open(f"{WORK}/app/__init__.py", "w").close()
open(f"{WORK}/app/ml/__init__.py", "w").close()

import glob as _g
def find_script(name):
    hits = _g.glob(f"/kaggle/input/**/{name}", recursive=True)
    return hits[0] if hits else None

scripts = [
    "train_model_v2.py", "train_model_v3.py", "train_model_v4.py",
    "train_multimodal_v5.py"
]
for s in scripts:
    found = find_script(s)
    if found:
        shutil.copy(found, f"{WORK}/app/ml/{s}")
        print(f"✓ {s}  ← {found}")
    else:
        print(f"✗ Not found: {s}")

sys.path.insert(0, WORK)
os.chdir(WORK)

# Copy proba files to trained_models so the fusion script can find them
os.makedirs(f"{WORK}/trained_models", exist_ok=True)
for f in os.listdir("/kaggle/input/smartlms-probas"):
    shutil.copy(f"/kaggle/input/smartlms-probas/{f}", f"{WORK}/trained_models/{f}")
    print(f"🔗 {f}")
```

#### Cell 2: Verify all probability files
```python
import glob
probas = glob.glob("/kaggle/working/trained_models/proba_*.npy")
labels = glob.glob("/kaggle/working/trained_models/labels_*.npy")
print(f"Probability files: {len(probas)}")
print(f"Label files: {len(labels)}")

for f in sorted(probas):
    import numpy as np
    arr = np.load(f)
    print(f"  {os.path.basename(f)}: shape={arr.shape}")

# Expect: at least 6 models × 4 dims = 24 proba files + 4 label files
if len(probas) < 20:
    print("\n⚠️ Some probability files may be missing!")
    print("Check that you uploaded all proba files from Weeks 1-3")
```

#### Cell 3: Multi-modal stacking fusion (~3 hrs)
```python
# This is the MAIN EVENT — combines all 6 modality streams
!python app/ml/train_multimodal_v5.py --mode fusion_stack
```

#### Cell 4: Ablation study (~4 hrs)
```python
# Tests every combination of modalities — produces the paper ablation table
!python app/ml/train_multimodal_v5.py --mode ablation
```

#### Cell 5: Final combined CORAL ordinal + fusion (~4 hrs)
```python
# Optional: CORAL ordinal with multi-modal features
!python app/ml/train_multimodal_v5.py --mode full
```

#### Cell 6: Print final results
```python
import json, glob, os
import numpy as np

print("="*90)
print("FINAL RESULTS — Smart LMS v5 Multi-Modal Engagement Detection")
print("="*90)

v3_baseline = {
    "XGBoost v3": {"boredom": 0.575, "engagement": 0.616, "confusion": 0.551, "frustration": 0.538, "avg": 0.570},
    "BiLSTM v3":  {"boredom": 0.532, "engagement": 0.566, "confusion": 0.525, "frustration": 0.526, "avg": 0.537},
    "Ensemble v3": {"boredom": 0.573, "engagement": 0.601, "confusion": 0.555, "frustration": 0.521, "avg": 0.563},
}

print(f"\n{'Model':<35} {'Boredom':>8} {'Engage':>8} {'Confuse':>8} {'Frustr':>8} {'Avg F1m':>8}")
print("-"*90)
for name, dims in v3_baseline.items():
    print(f"{name:<35} {dims['boredom']:8.4f} {dims['engagement']:8.4f} {dims['confusion']:8.4f} {dims['frustration']:8.4f} {dims['avg']:8.4f}")
print("-"*90)

# Load all v4/v5 results
for rf in sorted(glob.glob("/kaggle/working/experiment_results/*.json")):
    with open(rf) as f:
        data = json.load(f)
    print(f"\n📄 {os.path.basename(rf)}:")
    for key, res in data.get('results', {}).items():
        f1m = res.get('test_f1_macro') or res.get('cv_f1_macro_mean') or res.get('stacking_f1_macro', 0)
        std = res.get('cv_f1_macro_std', '')
        std_str = f" ± {std:.4f}" if isinstance(std, float) else ""
        print(f"  {key}: F1m = {f1m:.4f}{std_str}")

print("\n" + "="*90)
print("Target was 0.65+ F1m for multi-modal stacking")
print("="*90)
```

#### Cell 7: Download everything
```python
import shutil

shutil.make_archive("/kaggle/working/v5_final_models", 'zip', "/kaggle/working/trained_models")
shutil.make_archive("/kaggle/working/v5_final_results", 'zip', "/kaggle/working/experiment_results")

for f in glob.glob("/kaggle/working/*.zip"):
    print(f"📦 {os.path.basename(f)}: {os.path.getsize(f)/1e6:.1f} MB")

print("\n✅ DONE! Download and update your research paper with these results!")
```

---

## PHASE 4: Week 4 — Paper-Ready Analysis (Account A, ~10 hrs)

### Notebook 6: `smartlms-paper-figures` (Account A)

This is optional / for polish. Create a notebook with:

```python
!pip install -q shap matplotlib seaborn xgboost

# 1. Load final models and generate:
#    - Confusion matrices (4×4 for each dimension)
#    - ROC curves
#    - SHAP feature importance plots
#    - Ablation study bar chart
#    - Training convergence curves
#    - Modality contribution pie chart

# 2. Statistical significance tests:
#    - McNemar's test (v3 vs v5)
#    - Bootstrap confidence intervals

# You can reuse the figure generation code from your existing paper pipeline
```

---

## Quick Reference: Account Allocation

| Week | Account A | Account B | Account C |
|------|-----------|-----------|-----------|
| 0 | Upload `smartlms-scripts` (shared) | ✅ `daisee-videos` done | ✅ `smartlms-openface` done |
| 1 | **NB1:** OpenFace models (19h) | — | — |
| 2 | — | **NB2:** VideoMAE (15h) | **NB3:** ViT embeds (11h) |
| 2→3 | — | — | Re-upload ViT embeds as dataset |
| 3 | **NB5:** Fusion + ablation (12h) | **NB4:** Audio (10h) | — |
| 4 | **NB6:** Paper figures (10h) | — | — |

---

## Troubleshooting

### "Session disconnected after 12 hours"
- Kaggle has a 12-hour session limit. Split long notebooks across sessions.
- All scripts save models after each dimension, so progress isn't lost.
- Just re-run the next cell when you start a new session.

### "GPU quota exceeded" 
- Each Kaggle account gets ~30 hrs/week of T4 GPU.
- Quotas reset weekly (check your profile → Settings → GPU Quota).
- That's why we use 3 accounts in parallel.

### "Out of memory" on VideoMAE
- The script uses gradient checkpointing + mixed precision (already set).
- If still OOM, reduce batch_size in the script: change `batch_size=4` to `batch_size=2` and `gradient_accumulation_steps=8` to `16`.
- Or reduce `num_frames=16` to `num_frames=8`.

### "Import error: No module named app.ml.train_model_v2"
- Make sure Cell 2 (copy scripts) ran successfully.
- Check that `__init__.py` files were created in `app/` and `app/ml/`.
- The scripts have a fallback `except ImportError: pass` — they'll try Kaggle paths.

### "FileNotFoundError: Labels not found"
- Verify the Labels folder is inside the `smartlms-openface` dataset.
- Path should be: `/kaggle/input/smartlms-openface/Labels/AllLabels.csv`
- If your dataset has a different structure, run: `!find /kaggle/input -name "AllLabels.csv"` to locate it.

### Scripts not found in `smartlms-scripts`
- Make sure you attached the `smartlms-scripts` dataset to the notebook.
- Run: `!ls /kaggle/input/smartlms-scripts/` to verify files are there.
- If you update scripts later, create a **New Version** of the dataset (Dataset → New Version → upload updated files). Then restart the notebook kernel to pick up changes.

### "proba files not found" in fusion notebook
- Make sure you uploaded ALL probability files to the `smartlms-probas` dataset.
- Expected: ~24+ proba files (6 models × 4 dimensions) + 4 label files.

### Sharing datasets across accounts
- Make the datasets **Private** but share them:
  - Go to Dataset → Settings → Collaborators → Add the other account usernames
  - OR make datasets Public (if you don't mind)

---

## Checklist

- [x] **Phase 0:** ~~Create `smartlms-openface` dataset~~ ✅ Already uploaded
- [x] **Phase 0:** ~~Create `daisee-videos` dataset~~ ✅ Already uploaded
- [ ] **Phase 0:** Create `smartlms-scripts` dataset (tiny, 7 .py files)
- [ ] **Phase 0:** Share all datasets across all 3 accounts
- [ ] **Week 1:** Run Notebook 1 (OpenFace models) on Account A
- [ ] **Week 1:** Download Week 1 models + probas
- [ ] **Week 2:** Run Notebook 2 (VideoMAE) on Account B
- [ ] **Week 2:** Run Notebook 3 (ViT embeddings) on Account C — simultaneously!
- [ ] **Week 2:** Download VideoMAE models + probas
- [ ] **Week 2:** Download ViT embeddings → re-upload as `smartlms-vit-embeddings` dataset
- [ ] **Week 3:** Download audio probas from Notebook 4
- [ ] **Week 3:** Create `smartlms-probas` dataset with ALL probability files
- [ ] **Week 3:** Run Notebook 4 (Audio) on Account B
- [ ] **Week 3:** Run Notebook 5 (Fusion + Ablation) on Account A
- [ ] **Week 4:** Run Notebook 6 (Paper figures) on Account A
- [ ] **Week 4:** Update research paper with new results!
