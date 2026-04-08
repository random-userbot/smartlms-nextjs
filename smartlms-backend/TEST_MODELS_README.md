# SmartLMS - Live Engagement Model Tester

A real-time testing utility for the SmartLMS engagement detection models using live camera feed.

## Features

✅ **Live Camera Capture** - Real-time video feed from your webcam  
✅ **Facial Feature Extraction** - MediaPipe-powered face detection and landmark tracking  
✅ **Multi-Model Support** - XGBoost, LSTM, and CNN-BiLSTM models  
✅ **Soft Voting Ensemble** - Combined predictions from all available models  
✅ **Real-time Visualization** - On-screen overlay of features and predictions  
✅ **4-Dimension Classification** - Boredom, Engagement, Confusion, Frustration  
✅ **Error Tracking & Debugging** - Console logs and JSON debug output  

## Installation

### 1. Install Python Dependencies

```bash
# Navigate to the backend directory
cd smartlms-backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Install test requirements
pip install -r requirements_test.txt
```

### 2. Verify Trained Models Exist

The script expects models in `smartlms-backend/app/ml/trained_models/`:

```bash
# Check if models are present
ls app/ml/trained_models/xgb_v3_*.joblib  # Should list 4 XGBoost models
ls app/ml/trained_models/lstm_v3_*.pt     # Should list 4 LSTM models
ls app/ml/trained_models/cnn_bilstm_v2_*.pt  # Should list 4 CNN models
```

If models are missing:
- Train them first using `app/ml/train_model_v3.py`
- Or download from Kaggle dataset

### 3. Check Camera Access

```bash
# On Windows
# Camera should be listed in Device Manager > Imaging Devices
```

## Usage

### Basic Run

```bash
# From smartlms-backend directory
python test_models_live.py
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| **q** / **ESC** | Quit the application |
| **p** | Pause/Resume frame capture |
| **r** | Reset feature history |
| **s** | Save debug info (timestamp + metrics) |
| **h** | Show help screen |
| **1** | Toggle XGBoost predictions |
| **2** | Toggle LSTM predictions |
| **3** | Toggle CNN predictions |

### On-Screen Display

```
╔═══════════════════════════════════════════╗
║      ENGAGEMENT TESTER WINDOW             ║
├───────────────────────────────────────────┤
│ ✓ Face Detected                           │
│                                           │
│ Raw Features:                             │
│   EAR: 0.245                              │
│   Mouth: 0.120                            │
│   Yaw: 15.2°                              │
│   Pitch: -8.5°                            │
│                                           │
│ Model Predictions:                        │
│   XGB-Bor: 0.342 ✓                        │
│   XGB-Eng: 0.756 ✗                        │
│   ENS-Con: 0.412 ✓                        │
│   ENS-Fru: 0.254 ✗                        │
│                                           │
│ FPS: 28.5                                 │
│ RECORDING                                 │
│ q: Quit | p: Pause | h: Help              │
└───────────────────────────────────────────┘
```

**Legend:**
- ✓ = Above threshold (dimension is active)
- ✗ = Below threshold (dimension is inactive)
- Green = Dimension detected
- Red = Dimension not detected

## Output Formats

### 1. Real-Time Console Output

```
[2024-04-03 14:32:01] INFO: Camera opened. Press 'h' for help, 'q' to quit.
[2024-04-03 14:32:05] INFO: ✓ Loaded XGBoost v3 boredom
[2024-04-03 14:32:05] INFO: ✓ Loaded LSTM v3 engagement
[2024-04-03 14:32:45] INFO: Predictions computed: xgb={boredom: 0.34, ...}
[2024-04-03 14:32:50] INFO: Feature history reset
```

### 2. Debug JSON Output

Saved to `smartlms-backend/debug_logs/live_test/debug_20240403_143245.json`:

```json
{
  "timestamp": "2024-04-03_14:32:45",
  "frame_count": 1247,
  "history_size": 42,
  "models_loaded": {
    "xgboost": 4,
    "lstm": 4,
    "cnn": 0
  },
  "latest_features": {
    "eye_aspect_ratio_left": 0.245,
    "eye_aspect_ratio_right": 0.248,
    "head_pose_yaw": 12.5,
    "head_pose_pitch": -5.2
  },
  "latest_predictions": {
    "xgboost": {"boredom": 0.34, "engagement": 0.73, ...},
    "ensemble": {"boredom": 0.35, "engagement": 0.71, ...}
  }
}
```

Press **s** in the running application to save debug info.

## Features Extracted

### Core Facial Features (Real-time)

| Feature | How It's Used | Source |
|---------|---------------|--------|
| **Eye Aspect Ratio (EAR)** | Blink detection, alertness | MediaPipe face landmarks |
| **Head Pose (Yaw/Pitch/Roll)** | Interest signal, engagement | Landmark geometry |
| **Mouth Openness** | Confusion, frustration signals | AU25, AU26 estimation |
| **Brow Actions** | Surprise, confusion cues | AU01, AU04 estimation |
| **Face Detection** | Is face visible? Binary signal | MediaPipe detection |

### Aggregated Features (30-frame window)

For each signal above:
- **Mean** - Average value over window
- **Std Dev** - Signal variability
- **Min/Max** - Signal range
- **Range** - Max - Min
- **Slope** - Temporal trend
- **10th/90th Percentile** - Outlier-robust bounds

**Total: 71 features** (8 signals × 8 stats + 2 blink metrics + 5 behavioral features)

### Behavioral Features (Mocked)

```python
keyboard_pct = 0.2    # 20% keyboard activity assumed
mouse_pct = 0.1       # 10% mouse activity assumed
tab_visible_pct = 1.0 # Tab always visible (no browser/window detection)
playback_speed = 1.0  # Normal playback assumed
note_taking_pct = 0.3 # Note-taking detected 30% of time
```

## Model Architectures

### XGBoost v3 (Binary Classifiers)
- **Input**: 71 features (scaled)
- **Output**: Probability [0, 1]
- **Binary**: Engaged vs. Not Engaged for each dimension
- **Optimal Thresholds**:
  - Boredom: 0.62
  - Engagement: 0.30
  - Confusion: 0.48
  - Frustration: 0.36

### LSTM v3 (Sequence Models)
- **Input**: Sequence of 30 feature frames
- **Architecture**: BiLSTM with attention
- **Output**: 4 binary classifications
- **Status**: Checkpoint loading functional, inference in progress

### CNN-BiLSTM v2 (Hybrid Models)
- **Input**: 1D temporal convolutions + sequence
- **Architecture**: Multi-scale CNN + BiLSTM
- **Output**: 4 binary classifications
- **Status**: Weights loaded, inference pending

## Troubleshooting

### ❌ "Failed to open camera!"
- **Check**: Is your webcam in use by another app?
- **Fix**: Close Zoom, Teams, OBS, etc.
- **Alternative**: Try using a different camera index (edit `cv2.VideoCapture(0)` → `cv2.VideoCapture(1)`)

### ❌ "✗ No models loaded"
- **Check**: Are files in `app/ml/trained_models/`?
- **Fix**: Run training first: `python app/ml/train_model_v3.py`
- **Verify**: `ls app/ml/trained_models/xgb_v3_*.joblib` should list 4 files

### ❌ "✗ No Face Detected"
- **Check**: Is your face visible to the camera?
- **Fix**: Adjust lighting, move closer to camera, clean lens
- **Debug**: Look for green bounding box in video feed

### ❌ "CUDA out of memory"
- **Check**: GPU too small for model
- **Fix**: Falls back to CPU automatically (slower but works)
- **Speed**: CPU ~10-15 FPS, GPU ~25-30 FPS

### ❌ "ModuleNotFoundError: No module named 'mediapipe'"
- **Fix**: `pip install mediapipe`
- **Verify**: `python -c "import mediapipe; print(mediapipe.__version__)"`

### ❌ "KeyError: 'au01_inner_brow_raise'"
- **Cause**: Missing features in feature extraction
- **Fix**: Feature extractor provides defaults (0.0), this shouldn't happen
- **Debug**: Check `extract_features()` return values

### ⚠️ "Warning: PyTorch or definitions not found"
- **Fix**: `pip install torch torchvision`
- **Verify**: `python -c "import torch; print(torch.__version__)"`

### ⚠️ "LSTM predictions defaulting to 0.5"
- **Cause**: Sequence models need > 10 frames, still collecting
- **Fix**: Run the app for 1+ second before checking LSTM predictions
- **Status**: XGBoost will provide predictions immediately

### ⚠️ Low FPS (<10)
- **Check**: CPU usage (Resource Monitor)
- **Fix**: Close other apps
- **Note**: First few frames slower due to model loading

## Performance Notes

### Expected FPS
- **CPU (Intel i7)**: ~15-20 FPS
- **GPU (RTX 3060)**: ~25-30 FPS
- **Raspberry Pi**: ~5-8 FPS (not recommended)

### Bottlenecks
1. Face landmark detection: ~20ms per frame
2. Feature calculation: ~5ms per frame
3. Model inference: ~10-30ms per window (every 30 frames)
4. Visualization: ~2-5ms per frame

### Optimization Tips
- Reduce video resolution in camera setup (400x300 instead of 1280x720)
- Skip every 2nd frame for feature extraction
- Use GPU if available

## Example Session

```bash
$ cd smartlms-backend && python test_models_live.py

======================================================================
SmartLMS - Live Engagement Model Tester v1.0
======================================================================
[2024-04-03 14:32:00] INFO: Using device: cuda
[2024-04-03 14:32:01] INFO: Loading models from: C:\...\trained_models
[2024-04-03 14:32:02] INFO: ✓ Loaded XGBoost v3 boredom
[2024-04-03 14:32:02] INFO: ✓ Loaded XGBoost v3 engagement
[2024-04-03 14:32:02] INFO: ✓ Loaded XGBoost v3 confusion
[2024-04-03 14:32:02] INFO: ✓ Loaded XGBoost v3 frustration
[2024-04-03 14:32:03] INFO: ✓ Loaded LSTM v3 boredom
[2024-04-03 14:32:03] INFO: ✓ Loaded LSTM v3 engagement
[2024-04-03 14:32:03] INFO: ✓ Loaded LSTM v3 confusion
[2024-04-03 14:32:03] INFO: ✓ Loaded LSTM v3 frustration
[2024-04-03 14:32:04] INFO: Model Summary: XGBoost=4, LSTM=4, CNN=0
[2024-04-03 14:32:05] INFO: Camera opened. Press 'h' for help, 'q' to quit.

# <Window opens with live video feed>
# <Face detected, features flowing>
# <Model predictions updating every 30 frames>

# User presses 's' to save debug info
[2024-04-03 14:32:45] INFO: Saved debug info to ...\debug_20240403_143245.json

# User presses 'q' to quit
[2024-04-03 14:33:10] INFO: Quitting...
[2024-04-03 14:33:10] INFO: Cleanup complete
```

## Advanced Usage

### Running in Headless Mode (Server/Docker)

```python
# Modify test_models_live.py to save predictions to file instead of display
# (Not documented here - submit issue if needed)
```

### Custom Model Loading

To test a different model version:

```python
# Edit test_models_live.py, change MODEL_DIR:
MODEL_DIR = Path(__file__).parent / "app" / "ml" / "trained_models_v4"

# Or load specific model:
model = joblib.load("path/to/custom_xgb_model.joblib")
scaler = joblib.load("path/to/custom_scaler.joblib")
```

### Batch Video Testing

```bash
# For testing on recorded videos instead of camera:
# (Coming soon - modify test_models_live.py to accept video file path)
```

## Contributing

Found a bug? Have a suggestion?

1. Check the console output for error messages
2. Save debug info with **s** key
3. Open an issue with:
   - Python version
   - OS (Windows/Mac/Linux)
   - Error message
   - Debug JSON file

## Notes

- **Privacy**: No personal data is collected or stored beyond debug JSON files
- **Performance**: Predictions are CPU-bound with optional GPU acceleration
- **Compatibility**: Requires Python 3.8+
- **License**: Part of SmartLMS educational framework

## References

- [MediaPipe Face Detection](https://google.github.io/mediapipe/solutions/face_detection)
- [MediaPipe Face Mesh](https://google.github.io/mediapipe/solutions/face_mesh)
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [PyTorch Documentation](https://pytorch.org/)
