#!/usr/bin/env python3
"""
SmartLMS - Live Model Tester Troubleshooter
=============================================
Diagnose and fix common issues before running the live tester.

Usage:
  python troubleshoot.py

"""

import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class Troubleshooter:
    def __init__(self):
        self.backend_dir = Path(__file__).parent
        self.checks_passed = []
        self.checks_failed = []
        self.checks_warning = []
    
    def header(self, text):
        print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
        print(f"{BOLD}{BLUE}{text:^60}{RESET}")
        print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")
    
    def success(self, msg):
        print(f"{GREEN}✓ {msg}{RESET}")
        self.checks_passed.append(msg)
    
    def error(self, msg):
        print(f"{RED}✗ {msg}{RESET}")
        self.checks_failed.append(msg)
    
    def warning(self, msg):
        print(f"{YELLOW}⚠ {msg}{RESET}")
        self.checks_warning.append(msg)
    
    def info(self, msg):
        print(f"{BLUE}ℹ {msg}{RESET}")
    
    def run(self):
        """Run all diagnostic checks."""
        self.header("SmartLMS Live Model Tester - Diagnostics")
        
        # 1. Python environment
        self.check_python()
        
        # 2. File structure
        self.check_structure()
        
        # 3. Dependencies
        self.check_dependencies()
        
        # 4. GPU support
        self.check_gpu()
        
        # 5. Camera
        self.check_camera()
        
        # 6. Models
        self.check_models()
        
        # 7. Permissions
        self.check_permissions()
        
        # 8. Summary
        self.print_summary()
    
    def check_python(self):
        """Check Python version and executable."""
        self.header("Python Environment")
        
        v = sys.version_info
        if v.major == 3 and v.minor >= 8:
            self.success(f"Python {v.major}.{v.minor}.{v.micro}")
        else:
            self.error(f"Python {v.major}.{v.minor}.{v.micro} (need 3.8+)")
        
        self.info(f"Executable: {sys.executable}")
        self.info(f"Platform: {sys.platform}")
    
    def check_structure(self):
        """Check required directory structure."""
        self.header("Directory Structure")
        
        required_files = {
            "Test Script": "test_models_live.py",
            "Setup Script": "quickstart_setup.py",
            "Requirements": "requirements_test.txt",
            "Documentation": "TEST_MODELS_README.md",
        }
        
        required_dirs = {
            "App ML": "app/ml",
            "Models": "app/ml/trained_models",
            "App Config": "app/config.py",
        }
        
        for name, path in required_files.items():
            if (self.backend_dir / path).exists():
                self.success(f"{name}: {path}")
            else:
                self.error(f"{name} NOT FOUND: {path}")
        
        for name, path in required_dirs.items():
            if (self.backend_dir / path).exists():
                self.success(f"{name}: {path}")
            else:
                self.error(f"{name} NOT FOUND: {path}")
    
    def check_dependencies(self):
        """Check Python package dependencies."""
        self.header("Python Dependencies")
        
        packages = {
            "numpy": "Numerical computing",
            "cv2 (opencv)": "Video capture & processing",
            "mediapipe": "Face detection & landmarks",
            "torch": "PyTorch models",
            "torchvision": "PyTorch vision utils",
            "sklearn": "scikit-learn utilities",
            "joblib": "Model serialization",
            "xgboost": "XGBoost models (optional)",
        }
        
        for package, description in packages.items():
            try:
                # Special handling for cv2
                if package == "cv2 (opencv)":
                    import cv2
                    ver = cv2.__version__
                    pkg_name = "opencv"
                elif package == "sklearn":
                    import sklearn
                    ver = sklearn.__version__
                    pkg_name = "scikit-learn"
                else:
                    mod = __import__(package.split()[0].replace("-", "_"))
                    ver = getattr(mod, '__version__', 'unknown')
                    pkg_name = package
                
                self.success(f"{package}: v{ver}")
            except ImportError:
                self.warning(f"{package}: NOT INSTALLED")
                self.info(f"  Install: pip install {package.split()[0]}")
    
    def check_gpu(self):
        """Check GPU availability."""
        self.header("GPU Support (Optional)")
        
        try:
            import torch
            if torch.cuda.is_available():
                self.success(f"CUDA available: {torch.cuda.get_device_name(0)}")
                self.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            else:
                self.warning("CUDA not available (will use CPU)")
                self.info("CPU inference is slower (~15fps) but still works")
        except ImportError:
            self.warning("PyTorch not installed (needed for GPU check)")
    
    def check_camera(self):
        """Check camera accessibility."""
        self.header("Camera Access")
        
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    self.success(f"Camera accessible: {w}x{h}")
                else:
                    self.error("Camera detected but can't read frames")
            else:
                self.error("Camera not accessible")
                self.info("  - Close Zoom, Teams, OBS, etc.")
                self.info("  - Try Device Manager > Imaging Devices")
                self.info("  - Try different camera index: cv2.VideoCapture(1)")
            
            cap.release()
        except ImportError:
            self.warning("OpenCV not installed (can't test camera)")
        except Exception as e:
            self.error(f"Camera check failed: {e}")
    
    def check_models(self):
        """Check trained models exist."""
        self.header("Trained Models")
        
        models_dir = self.backend_dir / "app" / "ml" / "trained_models"
        
        if not models_dir.exists():
            self.error(f"Models directory not found: {models_dir}")
            self.info("  Run: python app/ml/train_model_v3.py")
            return
        
        model_types = {
            "XGBoost": ["xgb_v3_boredom_bin.joblib", "xgb_v3_engagement_bin.joblib",
                       "xgb_v3_confusion_bin.joblib", "xgb_v3_frustration_bin.joblib"],
            "XGB Scalers": ["scaler_v3_boredom_bin.joblib", "scaler_v3_engagement_bin.joblib",
                           "scaler_v3_confusion_bin.joblib", "scaler_v3_frustration_bin.joblib"],
            "LSTM": ["lstm_v3_boredom_bin.pt", "lstm_v3_engagement_bin.pt",
                    "lstm_v3_confusion_bin.pt", "lstm_v3_frustration_bin.pt"],
            "CNN-BiLSTM": ["cnn_bilstm_v2_boredom_bin.pt", "cnn_bilstm_v2_engagement_bin.pt",
                          "cnn_bilstm_v2_confusion_bin.pt", "cnn_bilstm_v2_frustration_bin.pt"],
        }
        
        for model_type, files in model_types.items():
            found = sum(1 for f in files if (models_dir / f).exists())
            
            if found == len(files):
                self.success(f"{model_type}: {found}/{len(files)}")
            elif found > 0:
                self.warning(f"{model_type}: {found}/{len(files)} (missing {len(files)-found})")
            else:
                self.error(f"{model_type}: 0/{len(files)} (not trained)")
        
        # Show total
        all_files = []
        for files in model_types.values():
            all_files.extend(files)
        found_all = sum(1 for f in all_files if (models_dir / f).exists())
        
        self.info(f"Total: {found_all}/{len(all_files)} models available")
    
    def check_permissions(self):
        """Check file permissions."""
        self.header("File Permissions")
        
        files_to_check = [
            ("Test Script", "test_models_live.py"),
            ("Quickstart", "quickstart_setup.py"),
            ("Debug Directory", "debug_logs"),
        ]
        
        for name, path in files_to_check:
            full_path = self.backend_dir / path
            if full_path.exists():
                try:
                    if full_path.is_file():
                        full_path.read_bytes()
                    elif full_path.is_dir():
                        list(full_path.iterdir())
                    self.success(f"{name}: readable/writable")
                except PermissionError:
                    self.error(f"{name}: permission denied")
            else:
                self.warning(f"{name}: not found")
    
    def print_summary(self):
        """Print diagnostic summary."""
        self.header("Diagnostic Summary")
        
        print(f"{GREEN}Passed: {len(self.checks_passed)}{RESET}")
        for check in self.checks_passed:
            print(f"  {GREEN}✓{RESET} {check}")
        
        if self.checks_warning:
            print(f"\n{YELLOW}Warnings: {len(self.checks_warning)}{RESET}")
            for check in self.checks_warning:
                print(f"  {YELLOW}⚠{RESET} {check}")
        
        if self.checks_failed:
            print(f"\n{RED}Failed: {len(self.checks_failed)}{RESET}")
            for check in self.checks_failed:
                print(f"  {RED}✗{RESET} {check}")
        
        # Recommendation
        print(f"\n{BOLD}Recommendation:{RESET}")
        if not self.checks_failed and not self.checks_warning:
            print(f"{GREEN}All systems go! Run: python test_models_live.py{RESET}")
        elif not self.checks_failed:
            print(f"{YELLOW}Some warnings, but should work. Run with caution.{RESET}")
        else:
            print(f"{RED}Fix critical failures before running test_models_live.py{RESET}")
        
        # Save report
        self._save_report()
    
    def _save_report(self):
        """Save diagnostic report to file."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "platform": sys.platform,
            "passed": len(self.checks_passed),
            "failed": len(self.checks_failed),
            "warnings": len(self.checks_warning),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_warning": self.checks_warning,
        }
        
        report_file = self.backend_dir / "debug_logs" / "diagnostic_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n{BLUE}ℹ Report saved: {report_file}{RESET}")
        except Exception as e:
            print(f"{YELLOW}⚠ Could not save report: {e}{RESET}")

if __name__ == "__main__":
    try:
        troubleshooter = Troubleshooter()
        troubleshooter.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
