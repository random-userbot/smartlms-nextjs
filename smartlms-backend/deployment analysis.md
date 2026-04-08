# DAiSEE Engagement Model Analysis

This document provides a detailed analysis of the available models in the `c:\Users\revan\Downloads\DAiSEE\export` folder, including weights, features, and deployment instructions.

## 📊 Model Summary Comparison

| Rank | Model Name | Accuracy | Speed | Input Features | Notes |
|------|------------|----------|-------|----------------|-------|
| 🥇 | **Transformer_ViT_59.6%_BEST** | 59.6% | 50-80ms | ViT (768-dim) | Recommended: Best balance, unbiased. |
| 🥈 | **BiLSTM_Enhanced_FMAE_58.6%** | 58.6% | 10-20ms | FMAE (256-dim) | Fast: Ideal for real-time. |
| 🥉 | **Fusion_Enhanced_57.4%** | 57.4% | 80-100ms | Combined (1565-dim) | Multi-modal fusion of OpenFace + EffNet + FMAE. |
| 4 | Baseline_LSTM_74.2%_BIASED | 74.2% | 10ms | OpenFace (22-dim) | ⚠️ **DO NOT USE**: Biased towards "Engagement". |

---

## 🥇 Recommended Model: Transformer_ViT_59.6%_BEST

This model is the most reliable and provides balanced detection across all four engagement dimensions.

### 🏗️ Architecture
- **Backbone**: ViT-base-patch16-224 (pre-trained at `google/vit-base-patch16-224`)
- **Temporal Component**: 6-layer Temporal Transformer Encoder
- **Heads**: 8 Attention Heads
- **Feed-Forward Dimension**: 2048

### 📂 Model Files
- **Weights**: `export/Transformer_ViT_59.6%_BEST/best_model.h5`
- **Config**: Defined in `model_loader.py` (requires custom layers)
- **Size**: ~385 MB

### 🧩 Feature Requirements
- **Input Shape**: `(batch_size, 30, 768)`
- **Sequence Length**: 30 frames (approx. 1 second at 30 FPS)
- **Feature Vector**: 768-dimensional ViT features extracted from the class token of `google/vit-base-patch16-224`.

---

## 🥈 Faster Alternative: BiLSTM_Enhanced_FMAE_58.6%

Best for lower-end hardware or high-frequency real-time analysis.

### 🏗️ Architecture
- **Core**: Bi-directional LSTM with Attention mechanism.
- **Speed**: 3-5x faster than the Transformer model.

### 📂 Model Files
- **Weights**: `export/BiLSTM_Enhanced_FMAE_58.6%/best_model.h5`
- **Size**: ~6.7 MB

### 🧩 Feature Requirements
- **Input Shape**: `(batch_size, 30, 256)`
- **Feature Vector**: 256-dimensional FMAE (FER2013-pre-trained) features.

---

## 🚀 Deployment Instructions

### 1. Model Loader
You **MUST** use the provided `model_loader.py` to load these models, as they contain custom layers (`TransformerBlock`, `AttentionLayer`, `PositionalEncoding`).

```python
import sys
from pathlib import Path

# Add export directory to path
sys.path.insert(0, './export')
from model_loader import load_model_with_custom_layers

# Load the model
model_path = 'export/Transformer_ViT_59.6%_BEST/best_model.h5'
model = load_model_with_custom_layers(model_path, compile=False)
```

### 2. Output Parsing
The models output 4 distinct probability distributions (one for each dimension). Use the following labels:

- **Dimensions**: Boredom, Engagement, Confusion, Frustration
- **Levels**: Very Low (0), Low (1), High (2), Very High (3)

```python
predictions = model.predict(features)
labels = ['Very Low', 'Low', 'High', 'Very High']
dimensions = ['Boredom', 'Engagement', 'Confusion', 'Frustration']

for i, dim in enumerate(dimensions):
    class_id = np.argmax(predictions[i][0])
    print(f"{dim}: {labels[class_id]} ({predictions[i][0][class_id]:.1%})")
```

### 3. Optimization
To achieve a **2-3x speedup**, convert the model to ONNX using `tf2onnx`:
```python
import tf2onnx
import onnx

spec = (tf.TensorSpec((None, 30, 768), tf.float32, name="input"),)
model_proto, _ = tf2onnx.convert.from_keras(model, input_signature=spec)
onnx.save(model_proto, 'optimized_model.onnx')
```

---

> [!IMPORTANT]
> Always ensure your input buffer is exactly **30 frames** long. Shorter sequences will require padding, which may reduce accuracy.

> [!TIP]
> For real-time applications, use a **sliding window** with a step size of 5-10 frames to produce smoother engagement updates while maintaining responsiveness.
