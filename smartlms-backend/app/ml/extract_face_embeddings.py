"""
Smart LMS - ViT Face Embedding Extractor
=========================================
Extracts per-frame face crop embeddings from DAiSEE raw videos
using a pretrained Vision Transformer (ViT-B/16).

Usage:
    # On Kaggle T4 (~4-8 hrs for full dataset):
    python extract_face_embeddings.py --video_dir /kaggle/input/daisee-videos --output_dir /kaggle/working/vit_embeddings

    # Locally (subset for testing):
    python extract_face_embeddings.py --max_clips 100

Dependencies:
    pip install torch torchvision transformers opencv-python tqdm
"""

import os
import sys
import cv2
import glob
import argparse
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

# ── Detect environment ──
ON_KAGGLE = os.path.exists("/kaggle/working")

if ON_KAGGLE:
    DEFAULT_VIDEO_DIR = "/kaggle/input/daisee-videos/DAiSEE/DataSet"
    DEFAULT_OUTPUT_DIR = "/kaggle/working/vit_embeddings"
else:
    DEFAULT_VIDEO_DIR = r"C:\Users\revan\Downloads\DAiSEE\DAiSEE\DataSet"
    DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "vit_embeddings")


def find_video_files(base_dir: str) -> List[str]:
    """
    Find all .avi video files in DAiSEE directory structure.
    Structure: DataSet/{Train,Validation,Test}/{UserID}/{ClipID}.avi
    """
    patterns = [
        os.path.join(base_dir, "**", "*.avi"),
        os.path.join(base_dir, "**", "*.mp4"),
    ]
    videos = []
    for pattern in patterns:
        videos.extend(glob.glob(pattern, recursive=True))
    print(f"Found {len(videos)} video files in {base_dir}")
    return sorted(videos)


def get_clip_id(video_path: str) -> str:
    """Extract clip ID from video path (filename without ext)."""
    return Path(video_path).stem


class FaceDetectorCropper:
    """
    Face detection and cropping pipeline.
    Uses OpenCV DNN face detector (SSD) with fallback to Haar cascade.
    """
    def __init__(self):
        self.haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        # Try DNN face detector for better accuracy
        self.dnn_detector = None
        try:
            proto = cv2.data.haarcascades.replace(
                'haarcascade_frontalface_default.xml', ''
            )
            model_path = os.path.join(proto, 'deploy.prototxt')
            weights_path = os.path.join(proto, 'res10_300x300_ssd_iter_140000.caffemodel')
            if os.path.exists(model_path) and os.path.exists(weights_path):
                self.dnn_detector = cv2.dnn.readNetFromCaffe(model_path, weights_path)
        except Exception:
            pass

    def detect_and_crop(self, frame: np.ndarray, target_size: int = 224) -> Optional[np.ndarray]:
        """
        Detect face in frame and return cropped, resized face image.
        Returns None if no face detected.
        """
        h, w = frame.shape[:2]
        face_box = None

        # Try DNN detector first (more robust)
        if self.dnn_detector is not None:
            blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104, 177, 123))
            self.dnn_detector.setInput(blob)
            detections = self.dnn_detector.forward()
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    x1 = max(0, int(detections[0, 0, i, 3] * w))
                    y1 = max(0, int(detections[0, 0, i, 4] * h))
                    x2 = min(w, int(detections[0, 0, i, 5] * w))
                    y2 = min(h, int(detections[0, 0, i, 6] * h))
                    if x2 - x1 > 30 and y2 - y1 > 30:
                        face_box = (x1, y1, x2 - x1, y2 - y1)
                        break

        # Fallback to Haar
        if face_box is None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.haar.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
            if len(faces) > 0:
                face_box = tuple(faces[0])

        # Fallback: use center crop for frontal webcam videos
        if face_box is None:
            # DAiSEE is frontal webcam — center crop is reasonable fallback
            size = min(h, w)
            y1 = max(0, (h - size) // 2)
            x1 = max(0, (w - size) // 2)
            face_box = (x1, y1, size, size)

        x, y, fw, fh = face_box
        # Add 10% margin
        margin = int(max(fw, fh) * 0.1)
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(w, x + fw + margin)
        y2 = min(h, y + fh + margin)

        face_crop = frame[y1:y2, x1:x2]
        if face_crop.shape[0] < 10 or face_crop.shape[1] < 10:
            return None

        face_crop = cv2.resize(face_crop, (target_size, target_size))
        return face_crop


class ViTEmbeddingExtractor:
    """
    Extract embeddings from face crops using pretrained ViT-B/16.
    Uses the [CLS] token output (768-dim) as the face embedding.
    """
    def __init__(self, model_name: str = "google/vit-base-patch16-224", device: str = None):
        import torch
        from transformers import ViTModel, ViTFeatureExtractor

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading ViT model: {model_name} on {self.device}")

        self.feature_extractor = ViTFeatureExtractor.from_pretrained(model_name)
        self.model = ViTModel.from_pretrained(model_name).to(self.device)
        # Wrap for multi-GPU if available
        if torch.cuda.device_count() > 1:
            print(f"  [Multi-GPU] Using {torch.cuda.device_count()} GPUs with DataParallel")
            self.model = torch.nn.DataParallel(self.model)
        self.model.eval()

        # Freeze
        for param in self.model.parameters():
            param.requires_grad = False

        print(f"ViT loaded. Embedding dim: 768")

    def extract_batch(self, face_crops: List[np.ndarray]) -> np.ndarray:
        """
        Extract embeddings from a batch of face crops.
        face_crops: list of (224, 224, 3) numpy arrays (BGR)
        Returns: (N, 768) numpy array
        """
        import torch

        # Convert BGR to RGB
        rgb_crops = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in face_crops]

        # Preprocess
        inputs = self.feature_extractor(images=rgb_crops, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            # [CLS] token is first position in last_hidden_state
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()

        return embeddings  # (batch, 768)


def extract_video_embeddings(
    video_path: str,
    face_detector: FaceDetectorCropper,
    vit_extractor: ViTEmbeddingExtractor,
    sample_fps: float = 2.0,
    batch_size: int = 16,
) -> Optional[np.ndarray]:
    """
    Extract per-frame ViT embeddings from a video.
    
    Args:
        video_path: Path to video file
        face_detector: Face detector/cropper
        vit_extractor: ViT embedding model
        sample_fps: Frames to sample per second (2 fps = 1 embedding every 0.5s)
        batch_size: Batch size for ViT inference
    
    Returns:
        (N_frames, 768) numpy array or None if failed
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or total_frames <= 0:
        cap.release()
        return None

    # Calculate which frames to sample
    frame_interval = max(1, int(fps / sample_fps))
    sample_indices = list(range(0, total_frames, frame_interval))

    face_crops = []
    for target_idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret:
            break
        crop = face_detector.detect_and_crop(frame, target_size=224)
        if crop is not None:
            face_crops.append(crop)

    cap.release()

    if len(face_crops) < 2:
        return None

    # Extract embeddings in batches
    all_embeddings = []
    for i in range(0, len(face_crops), batch_size):
        batch = face_crops[i:i + batch_size]
        embeddings = vit_extractor.extract_batch(batch)
        all_embeddings.append(embeddings)

    return np.vstack(all_embeddings)  # (N_frames, 768)


def main():
    parser = argparse.ArgumentParser(description="Extract ViT face embeddings from DAiSEE videos")
    parser.add_argument("--video_dir", default=DEFAULT_VIDEO_DIR, help="Path to DAiSEE DataSet directory")
    parser.add_argument("--output_dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for embeddings")
    parser.add_argument("--model", default="google/vit-base-patch16-224", help="HuggingFace ViT model name")
    parser.add_argument("--sample_fps", type=float, default=2.0, help="Frames per second to sample")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for ViT inference")
    parser.add_argument("--max_clips", type=int, default=0, help="Max clips to process (0=all)")
    parser.add_argument("--resume", action="store_true", help="Skip already processed clips")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Find videos
    videos = find_video_files(args.video_dir)
    if args.max_clips > 0:
        videos = videos[:args.max_clips]

    # Skip already processed
    if args.resume:
        done = set(Path(f).stem for f in glob.glob(os.path.join(args.output_dir, "*.npy")))
        videos = [v for v in videos if get_clip_id(v) not in done]
        print(f"Resuming: {len(done)} already done, {len(videos)} remaining")

    print(f"\nProcessing {len(videos)} videos")
    print(f"Output: {args.output_dir}")
    print(f"Model: {args.model}")
    print(f"Sample FPS: {args.sample_fps}")

    # Initialize
    face_detector = FaceDetectorCropper()
    vit_extractor = ViTEmbeddingExtractor(model_name=args.model)

    from tqdm import tqdm
    success, failed = 0, 0
    for video_path in tqdm(videos, desc="Extracting"):
        clip_id = get_clip_id(video_path)
        out_path = os.path.join(args.output_dir, f"{clip_id}.npy")

        try:
            embeddings = extract_video_embeddings(
                video_path, face_detector, vit_extractor,
                sample_fps=args.sample_fps, batch_size=args.batch_size,
            )
            if embeddings is not None:
                np.save(out_path, embeddings.astype(np.float16))  # float16 saves space
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n  Error {clip_id}: {e}")
            failed += 1

        if (success + failed) % 100 == 0:
            print(f"\n  Progress: {success} success, {failed} failed")

    print(f"\n{'='*50}")
    print(f"DONE: {success} embeddings extracted, {failed} failed")
    print(f"Output: {args.output_dir}")

    # Summary stats
    embed_files = glob.glob(os.path.join(args.output_dir, "*.npy"))
    if embed_files:
        sample = np.load(embed_files[0])
        total_size = sum(os.path.getsize(f) for f in embed_files)
        print(f"Total files: {len(embed_files)}")
        print(f"Sample shape: {sample.shape}")
        print(f"Total size: {total_size / (1024**2):.1f} MB")


if __name__ == "__main__":
    main()
