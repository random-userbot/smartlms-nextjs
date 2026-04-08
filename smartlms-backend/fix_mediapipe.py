#!/usr/bin/env python3
"""
MediaPipe Installation Fixer
=============================
Fixes common MediaPipe import issues.

Usage:
    python fix_mediapipe.py

"""

import subprocess
import sys
import os

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def print_info(text):
    print(f"ℹ {text}")

def main():
    print_header("MediaPipe Installation Fixer")
    
    # Step 1: Uninstall old version
    print_info("Step 1: Removing old MediaPipe installation...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "uninstall", "-y", "-q", "mediapipe"
        ])
        print_success("Old MediaPipe removed")
    except:
        print_info("No previous MediaPipe installation found")
    
    # Step 2: Clear pip cache
    print_info("Step 2: Clearing pip cache...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "cache", "purge", "-q"
        ])
        print_success("Cache cleared")
    except:
        print_info("Could not clear cache (non-critical)")
    
    # Step 3: Install latest MediaPipe
    print_info("Step 3: Installing latest MediaPipe...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "--upgrade", "mediapipe"
        ])
        print_success("MediaPipe installed successfully")
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install MediaPipe: {e}")
        return False
    
    # Step 4: Verify installation
    print_info("Step 4: Verifying installation...")
    try:
        import mediapipe as mp
        from mediapipe.solutions import face_detection, face_mesh, drawing_utils
        print_success(f"MediaPipe {mp.__version__} verified")
        print_success("face_detection module available")
        print_success("face_mesh module available")
        print_success("drawing_utils module available")
        return True
    except ImportError as e:
        print_error(f"Verification failed: {e}")
        return False

if __name__ == "__main__":
    print_header("MediaPipe Installation Fixer")
    
    success = main()
    
    print_header("Result")
    if success:
        print_success("MediaPipe is now ready!")
        print_info("Run: python test_models_live.py")
    else:
        print_error("MediaPipe installation still has issues")
        print_info("Try manual installation:")
        print(f"  python -m pip install --upgrade --force-reinstall mediapipe")
    
    sys.exit(0 if success else 1)
