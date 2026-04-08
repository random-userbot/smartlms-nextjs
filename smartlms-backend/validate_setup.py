#!/usr/bin/env python3
"""
Quick validation script to test MediaPipe and model loading
before running the full test_models_live.py
"""

import sys
import os

# Color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_imports():
    """Test all required imports."""
    print(f"\n{BLUE}Testing imports...{RESET}")
    
    errors = []
    
    # Test OpenCV
    try:
        import cv2
        print(f"{GREEN}✓ OpenCV {cv2.__version__}{RESET}")
    except ImportError as e:
        errors.append(f"OpenCV: {e}")
        print(f"{RED}✗ OpenCV failed{RESET}")
    
    # Test NumPy
    try:
        import numpy as np
        print(f"{GREEN}✓ NumPy {np.__version__}{RESET}")
    except ImportError as e:
        errors.append(f"NumPy: {e}")
        print(f"{RED}✗ NumPy failed{RESET}")
    
    # Test MediaPipe (the critical one)
    try:
        import mediapipe as mp
        print(f"{GREEN}✓ MediaPipe {mp.__version__}{RESET}")
        
        # Try importing the specific solutions
        from mediapipe.solutions import face_detection, face_mesh, drawing_utils
        print(f"{GREEN}✓ MediaPipe solutions (face_detection, face_mesh, drawing_utils){RESET}")
    except ImportError as e:
        errors.append(f"MediaPipe: {e}")
        print(f"{RED}✗ MediaPipe failed: {e}{RESET}")
        print(f"\n{YELLOW}Fix: Run 'python fix_mediapipe.py' or 'pip install --upgrade mediapipe'{RESET}")
    
    # Test PyTorch
    try:
        import torch
        device = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
        print(f"{GREEN}✓ PyTorch {torch.__version__} ({device}){RESET}")
    except ImportError as e:
        errors.append(f"PyTorch: {e}")
        print(f"{RED}✗ PyTorch failed{RESET}")
    
    # Test joblib
    try:
        import joblib
        print(f"{GREEN}✓ joblib{RESET}")
    except ImportError as e:
        errors.append(f"joblib: {e}")
        print(f"{RED}✗ joblib failed{RESET}")
    
    # Test scikit-learn
    try:
        import sklearn
        print(f"{GREEN}✓ scikit-learn {sklearn.__version__}{RESET}")
    except ImportError as e:
        errors.append(f"scikit-learn: {e}")
        print(f"{RED}✗ scikit-learn failed{RESET}")
    
    return errors

def test_models():
    """Test if trained models exist."""
    print(f"\n{BLUE}Testing model files...{RESET}")
    
    from pathlib import Path
    
    backend_dir = Path(__file__).parent
    models_dir = backend_dir / "app" / "ml" / "trained_models"
    
    if not models_dir.exists():
        print(f"{RED}✗ Models directory not found: {models_dir}{RESET}")
        print(f"{YELLOW}Hint: You need to train models first with:${RESET}")
        print(f"  python app/ml/train_model_v3.py")
        return False
    
    # Check for XGBoost models
    xgb_models = list(models_dir.glob("xgb_v3_*.joblib"))
    if len(xgb_models) == 4:
        print(f"{GREEN}✓ XGBoost models (4/4) found{RESET}")
    elif len(xgb_models) > 0:
        print(f"{YELLOW}⚠ XGBoost models ({len(xgb_models)}/4) found{RESET}")
    else:
        print(f"{RED}✗ XGBoost models not found{RESET}")
    
    # Check for scalers
    scaler_models = list(models_dir.glob("scaler_v3_*.joblib"))
    if len(scaler_models) == 4:
        print(f"{GREEN}✓ XGBoost scalers (4/4) found{RESET}")
    elif len(scaler_models) > 0:
        print(f"{YELLOW}⚠ XGBoost scalers ({len(scaler_models)}/4) found{RESET}")
    else:
        print(f"{RED}✗ XGBoost scalers not found{RESET}")
    
    # Check for LSTM models
    lstm_models = list(models_dir.glob("lstm_v3_*.pt"))
    if len(lstm_models) == 4:
        print(f"{GREEN}✓ LSTM models (4/4) found{RESET}")
    elif len(lstm_models) > 0:
        print(f"{YELLOW}⚠ LSTM models ({len(lstm_models)}/4) found{RESET}")
    else:
        print(f"{YELLOW}⚠ LSTM models not found (will use XGBoost only){RESET}")
    
    # Check for CNN models
    cnn_models = list(models_dir.glob("cnn_bilstm_v2_*.pt"))
    if len(cnn_models) == 4:
        print(f"{GREEN}✓ CNN-BiLSTM models (4/4) found{RESET}")
    elif len(cnn_models) > 0:
        print(f"{YELLOW}⚠ CNN-BiLSTM models ({len(cnn_models)}/4) found{RESET}")
    else:
        print(f"{YELLOW}⚠ CNN-BiLSTM models not found (will use XGBoost + LSTM){RESET}")
    
    has_models = len(xgb_models) == 4 and len(scaler_models) == 4
    return has_models

def test_camera():
    """Test camera access."""
    print(f"\n{BLUE}Testing camera access...{RESET}")
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                print(f"{GREEN}✓ Camera accessible ({w}x{h}){RESET}")
                cap.release()
                return True
            else:
                print(f"{RED}✗ Camera detected but can't read frames{RESET}")
                cap.release()
                return False
        else:
            print(f"{RED}✗ Camera not accessible{RESET}")
            print(f"{YELLOW}Hint: Close Zoom, Teams, OBS, or other apps using camera{RESET}")
            return False
    except Exception as e:
        print(f"{RED}✗ Camera test failed: {e}{RESET}")
        return False

def main():
    print(f"\n{BLUE}{'='*60}")
    print(f"{'SmartLMS Model Tester - Validation':^60}")
    print(f"{'='*60}{RESET}\n")
    
    # Test imports
    import_errors = test_imports()
    
    # Test models
    models_ok = test_models()
    
    # Test camera
    camera_ok = test_camera()
    
    # Summary
    print(f"\n{BLUE}{'='*60}")
    print(f"{'Summary':^60}")
    print(f"{'='*60}{RESET}")
    
    if import_errors:
        print(f"\n{RED}Import Errors ({len(import_errors)}):{RESET}")
        for error in import_errors:
            print(f"  • {error}")
    else:
        print(f"{GREEN}✓ All imports successful{RESET}")
    
    if models_ok:
        print(f"{GREEN}✓ Trained models ready{RESET}")
    else:
        print(f"{YELLOW}⚠ Some models missing (can still test with available models){RESET}")
    
    if camera_ok:
        print(f"{GREEN}✓ Camera ready{RESET}")
    else:
        print(f"{YELLOW}⚠ Camera not available (can't run test_models_live.py){RESET}")
    
    # Recommendation
    print(f"\n{BLUE}Recommendation:{RESET}")
    
    if not import_errors and camera_ok:
        print(f"{GREEN}Ready to run: python test_models_live.py{RESET}")
        return 0
    elif import_errors:
        print(f"{RED}Fix import errors first:{RESET}")
        if any("MediaPipe" in e for e in import_errors):
            print(f"  python fix_mediapipe.py")
        else:
            print(f"  pip install -r requirements_test.txt")
        return 1
    else:
        print(f"{YELLOW}Can test with mock camera (data will be simulated){RESET}")
        return 2

if __name__ == "__main__":
    sys.exit(main())
