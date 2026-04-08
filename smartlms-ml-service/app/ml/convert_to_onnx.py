import os
import sys
from pathlib import Path
import numpy as np
import joblib

# Add parent dir to path so we can import app.*
sys.path.append(str(Path(__file__).resolve().parents[3]))

try:
    import tensorflow as tf
    import tf2onnx
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("[CONVERT] TensorFlow/tf2onnx not found. Keras conversion skipped.")

try:
    import torch
    import torch.onnx
    from app.ml.pytorch_definitions import (
        BiLSTMModel, BiLSTMAttention, CNNBiLSTMAttention,
        BiLSTMGRUHybrid, TemporalTransformer
    )
    TORCH_AVAILABLE = True
except ImportError as e:
    TORCH_AVAILABLE = False
    print(f"[CONVERT] PyTorch not found or definitions missing: {e}. PyTorch conversion skipped.")

from app.ml.export_inference_registry import get_export_model_registry
from export.model_loader import load_model_with_custom_layers

def convert_keras_to_onnx(model_path: Path, output_path: Path):
    if not TF_AVAILABLE: return
    print(f"[CONVERT] Converting Keras model: {model_path.name}")
    try:
        model = load_model_with_custom_layers(str(model_path))
        if model is None: return
        
        # Use a fixed input shape for tracing if possible (30, feature_dim)
        spec = (tf.TensorSpec((None, 30, model.input_shape[2]), tf.float32, name="input"),)
        
        model_proto, _ = tf2onnx.convert.from_keras(model, input_signature=spec, output_path=str(output_path))
        print(f"  -> Saved to {output_path}")
    except Exception as e:
        print(f"  !! Failed to convert {model_path.name}: {e}")

def convert_torch_to_onnx(model_path: Path, output_path: Path, model_type: str):
    if not TORCH_AVAILABLE: return
    print(f"[CONVERT] Converting PyTorch model: {model_path.name} ({model_type})")
    try:
        # Identify params from filename if possible
        # Defaulting to common production params
        if "Baseline_LSTM" in str(model_path):
            model = BiLSTMModel(input_dim=49, hidden_dim=64, n_layers=2)
            dummy_input = torch.randn(1, 30, 49)
        elif "BiLSTM_Enhanced" in str(model_path):
            model = BiLSTMAttention(input_dim=31)
            dummy_input = torch.randn(1, 30, 31)
        else:
            print(f"  !! Unknown torch model type for {model_path.name}")
            return

        model.load_state_dict(torch.load(model_path, map_location='cpu'))
        model.eval()
        
        torch.onnx.export(
            model,
            dummy_input,
            str(output_path),
            export_params=True,
            opset_version=12,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
        )
        print(f"  -> Saved to {output_path}")
    except Exception as e:
        print(f"  !! Failed to convert {model_path.name}: {e}")

def main():
    registry = get_export_model_registry()
    export_dir = registry.export_dir
    print(f"[CONVERT] Processing models in {export_dir}")
    
    for folder in export_dir.iterdir():
        if not folder.is_dir(): continue
        
        # 1. Keras (.h5)
        h5_path = folder / "best_model.h5"
        if h5_path.exists():
            onnx_path = folder / "model.onnx"
            convert_keras_to_onnx(h5_path, onnx_path)
            
        # 2. PyTorch (.pt)
        for pt_name in ["best_model.pt", "lstm_v2_engagement_bin.pt", "lstm_v3_engagement_bin.pt"]:
            pt_path = folder / pt_name
            if pt_path.exists():
                onnx_path = folder / pt_name.replace(".pt", ".onnx")
                model_type = "LSTM" if "LSTM" in str(folder) else "Unknown"
                convert_torch_to_onnx(pt_path, onnx_path, model_type)

if __name__ == "__main__":
    main()
