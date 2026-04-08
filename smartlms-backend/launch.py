#!/usr/bin/env python3
"""
SmartLMS Test Models - Launcher
===================================
Step-by-step setup and testing launcher.

Usage:
    # First time setup
    python launch.py setup
    
    # Validate before testing
    python launch.py validate
    
    # Fix MediaPipe issues
    python launch.py fix
    
    # Run the live tester
    python launch.py test
    
    # Full diagnostics
    python launch.py diagnose
"""

import subprocess
import sys
from pathlib import Path

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def error(text):
    print(f"{RED}✗ {text}{RESET}")

def info(text):
    print(f"{BLUE}ℹ {text}{RESET}")

def section(text):
    print(f"\n{BOLD}{text}{RESET}")

def run_script(script, description):
    """Run a Python script."""
    section(description)
    backend_dir = Path(__file__).parent
    
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=backend_dir,
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        error(f"Failed: {e}")
        return False

def main():
    backend_dir = Path(__file__).parent
    
    if len(sys.argv) < 2:
        args = "help"
    else:
        args = sys.argv[1].lower()
    
    if args == "setup":
        header("Step 1: Setup SmartLMS Model Tester")
        success("Running initial setup...")
        success("Installing dependencies...")
        run_script("quickstart_setup.py", "Running Setup Script")
        
        section("Next Steps:")
        print(f"  1. {YELLOW}python launch.py validate{RESET}  # Verify setup")
        print(f"  2. {YELLOW}python launch.py test{RESET}      # Run tests")
    
    elif args == "validate":
        header("Step 2: Validate Setup")
        success("Checking all components...")
        run_script("validate_setup.py", "Running Validation")
        
        section("Next Steps:")
        print(f"  • {GREEN}python launch.py test{RESET}     # Run live tester")
        print(f"  • {YELLOW}python launch.py fix{RESET}      # Fix issues")
        print(f"  • {YELLOW}python launch.py diagnose{RESET} # Full diagnostics")
    
    elif args == "fix":
        header("Step 3: Fix MediaPipe Issues")
        success("Attempting to fix MediaPipe...")
        run_script("fix_mediapipe.py", "Running MediaPipe Fixer")
        
        section("Next Steps:")
        print(f"  1. {YELLOW}python launch.py validate{RESET}  # Verify fix")
        print(f"  2. {YELLOW}python launch.py test{RESET}      # Run tests")
    
    elif args == "diagnose" or args == "troubleshoot":
        header("Step 4: Full Diagnostics")
        success("Running comprehensive diagnostics...")
        run_script("troubleshoot.py", "Running Diagnostics")
    
    elif args == "test" or args == "run":
        header("Running SmartLMS Live Engagement Model Tester")
        
        info("Starting camera feed and model inference...")
        info("Press 'h' for help while running")
        info("Press 'q' or ESC to quit\n")
        
        script_path = backend_dir / "test_models_live.py"
        if not script_path.exists():
            error("test_models_live.py not found")
            return 1
        
        try:
            subprocess.run(
                [sys.executable, str(script_path)],
                cwd=backend_dir,
                check=False
            )
        except Exception as e:
            error(f"Failed to run: {e}")
            return 1
    
    elif args == "--help" or args == "-h" or args == "help":
        header("SmartLMS Model Tester - Launcher Guide")
        
        print("""
QUICK START:

  Option A - Full Setup (First Time)
    python launch.py setup       # Install everything
    python launch.py validate    # Check everything works
    python launch.py test        # Run live tests

  Option B - Individual Commands
    python launch.py validate    # Check your setup
    python launch.py test        # Run live tests
    python launch.py fix         # Fix MediaPipe issues
    python launch.py diagnose    # Full diagnostics

COMMANDS:

  setup      Install dependencies, create directories, initialize
  validate   Check all components (imports, models, camera)
  fix        Fix MediaPipe import errors specifically
  diagnose   Run full troubleshooting diagnostics
  test       Run the live engagement model tester
  help       Show this help message

WHAT EACH STEP DOES:

  setup     - Installs Python packages, creates directories,
              verifies Python version, tests camera access

  validate  - Checks MediaPipe, PyTorch, OpenCV, models,
              and camera - faster than full diagnostics

  fix       - Uninstalls and reinstalls MediaPipe,
              fixes "has no attribute 'solutions'" errors

  diagnose  - Complete system check with detailed reporting

  test      - Starts live camera feed with model predictions,
              real-time feature extraction, on-screen overlays

TYPICAL WORKFLOWS:

  1. First-time setup:
     python launch.py setup
     python launch.py validate
     python launch.py test

  2. Quick validation:
     python launch.py validate
     python launch.py test

  3. Fix MediaPipe issues:
     python launch.py fix
     python launch.py validate
     python launch.py test

  4. Full diagnostics:
     python launch.py diagnose

TROUBLESHOOTING:

  "AttributeError: 'mediapipe' has no attribute 'solutions'"
    → python launch.py fix

  "ModuleNotFoundError: No module named 'mediapipe'"
    → python launch.py setup

  "Camera not found"
    → Close Zoom/Teams, check Device Manager, run validate again

  "No models loaded"
    → Train models: python app/ml/train_model_v3.py

KEYBOARD SHORTCUTS (while running test):

  q / ESC   Quit
  p         Pause/Resume
  s         Save debug info
  r         Reset history
  1-3       Toggle models
  h         Show help

DOCUMENTATION:

  TEST_MODELS_README.md    Full technical documentation
  QUICKSTART.txt          30-second quick start
  requirements_test.txt   Python dependencies
        """)
    
    else:
        error(f"Unknown command: {args}")
        print(f"\nUse: python launch.py --help")
        return 1

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
    except Exception as e:
        error(f"Error: {e}")
