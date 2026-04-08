#!/usr/bin/env python3
"""
Quick Start Setup for SmartLMS Live Model Tester
================================================
This script sets up everything needed to run the live engagement model tester.

Usage:
  python quickstart_setup.py

"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")

def print_warning(text):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    """Print info message."""
    print(f"{BLUE}ℹ {text}{RESET}")

def check_python_version():
    """Check if Python version is 3.8+."""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print_error(f"Python 3.8+ required, but you have {version.major}.{version.minor}.{version.micro}")
        return False

def check_camera():
    """Check if camera is accessible."""
    print_header("Checking Camera Access")
    
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print_success("Camera detected and accessible")
            cap.release()
            return True
        else:
            print_error("Camera not accessible or not found")
            print_warning("Make sure your webcam is plugged in and not in use by another app")
            return False
    except ImportError:
        print_warning("OpenCV not installed yet (will be installed)")
        return None

def check_models():
    """Check if trained models exist."""
    print_header("Checking Trained Models")
    
    backend_dir = Path(__file__).parent
    models_dir = backend_dir / "app" / "ml" / "trained_models"
    
    if not models_dir.exists():
        print_error(f"Models directory not found: {models_dir}")
        return False
    
    required_models = {
        "XGBoost": ["xgb_v3_boredom_bin.joblib", "xgb_v3_engagement_bin.joblib",
                   "xgb_v3_confusion_bin.joblib", "xgb_v3_frustration_bin.joblib"],
        "Scalers": ["scaler_v3_boredom_bin.joblib", "scaler_v3_engagement_bin.joblib",
                   "scaler_v3_confusion_bin.joblib", "scaler_v3_frustration_bin.joblib"],
        "LSTM": ["lstm_v3_boredom_bin.pt", "lstm_v3_engagement_bin.pt",
                "lstm_v3_confusion_bin.pt", "lstm_v3_frustration_bin.pt"],
    }
    
    all_found = True
    for model_type, files in required_models.items():
        found = 0
        for file in files:
            if (models_dir / file).exists():
                found += 1
        
        if found == len(files):
            print_success(f"{model_type}: {found}/{len(files)} models found")
        elif found > 0:
            print_warning(f"{model_type}: {found}/{len(files)} models found (some missing)")
            all_found = False
        else:
            print_error(f"{model_type}: 0/{len(files)} models found (training required)")
            all_found = False
    
    if not all_found:
        print_info("To train models, run: python app/ml/train_model_v3.py")
    
    return all_found

def install_requirements():
    """Install Python requirements."""
    print_header("Installing Python Requirements")
    
    backend_dir = Path(__file__).parent
    requirements_file = backend_dir / "requirements_test.txt"
    
    if not requirements_file.exists():
        print_error(f"requirements_test.txt not found at {requirements_file}")
        return False
    
    print(f"Installing from {requirements_file}...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)
        ])
        print_success("All requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install requirements: {e}")
        print_info("Try manually: pip install -r requirements_test.txt")
        return False

def create_directories():
    """Create necessary directories."""
    print_header("Creating Directories")
    
    backend_dir = Path(__file__).parent
    dirs_to_create = [
        backend_dir / "debug_logs" / "live_test",
    ]
    
    for dir_path in dirs_to_create:
        dir_path.mkdir(parents=True, exist_ok=True)
        print_success(f"Directory ready: {dir_path}")

def run_diagnostics():
    """Run diagnostic tests."""
    print_header("Running Diagnostics")
    
    try:
        print_info("Checking MediaPipe...")
        import mediapipe
        print_success(f"MediaPipe {mediapipe.__version__} installed")
    except ImportError:
        print_error("MediaPipe not installed (installing via requirements)")
    
    try:
        print_info("Checking PyTorch...")
        import torch
        device = "GPU (CUDA)" if torch.cuda.is_available() else "CPU"
        print_success(f"PyTorch {torch.__version__} installed ({device})")
    except ImportError:
        print_error("PyTorch not installed (installing via requirements)")
    
    try:
        print_info("Checking OpenCV...")
        import cv2
        print_success(f"OpenCV {cv2.__version__} installed")
    except ImportError:
        print_error("OpenCV not installed (installing via requirements)")
    
    try:
        print_info("Checking scikit-learn...")
        import sklearn
        print_success(f"scikit-learn {sklearn.__version__} installed")
    except ImportError:
        print_error("scikit-learn not installed (installing via requirements)")
    
    try:
        print_info("Checking joblib...")
        import joblib
        print_success(f"joblib {joblib.__version__} installed")
    except ImportError:
        print_error("joblib not installed (installing via requirements)")

def print_next_steps():
    """Print next steps for user."""
    print_header("Next Steps")
    
    print("1. Review the setup results above")
    print()
    print("2. If all checks passed:")
    print(f"   {BOLD}python test_models_live.py{RESET}")
    print()
    print("3. Once running, press 'h' for help on keyboard controls")
    print()
    print("4. Try these actions:")
    print("   • Move your face around")
    print("   • Blink your eyes (test EAR)")
    print("   • Move your head (test head pose)")
    print("   • Open/close your mouth (test AU25/AU26)")
    print()
    print("5. Watch the predictions update every ~1 second")
    print()
    print("For detailed info, see: TEST_MODELS_README.md")

def create_summary_report():
    """Create a summary report."""
    print_header("Setup Summary")
    
    backend_dir = Path(__file__).parent
    report = {
        "timestamp": str(Path(__file__).stat().st_mtime),
        "script": "test_models_live.py",
        "requirements": "requirements_test.txt",
        "documentation": "TEST_MODELS_README.md",
        "models_dir": str(backend_dir / "app" / "ml" / "trained_models"),
        "debug_dir": str(backend_dir / "debug_logs" / "live_test"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    
    report_file = backend_dir / "debug_logs" / "setup_report.json"
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print_success(f"Setup report saved: {report_file}")
    except Exception as e:
        print_warning(f"Could not save setup report: {e}")

def main():
    """Main setup flow."""
    print(f"\n{BOLD}{BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  SmartLMS - Live Engagement Model Tester                   ║")
    print("║  Quick Start Setup                                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{RESET}\n")
    
    # Check Python version
    if not check_python_version():
        print_error("Please upgrade to Python 3.8+")
        sys.exit(1)
    
    # Check camera
    camera_status = check_camera()
    
    # Check models
    models_ok = check_models()
    
    # Create directories
    create_directories()
    
    # Install requirements
    if not install_requirements():
        print_warning("Continuing without installing requirements (may fail later)")
    
    # Run diagnostics
    run_diagnostics()
    
    # Print next steps
    print_next_steps()
    
    # Save summary
    create_summary_report()
    
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Setup interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Setup failed with error: {e}{RESET}")
        sys.exit(1)
