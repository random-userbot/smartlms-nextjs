#!/usr/bin/env python3
"""
Custom Layer Definitions for Loading Exported Models
Provides all custom layers used in the trained models
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Custom Layers
# ============================================================================

class PositionalEncoding(layers.Layer):
    """Add positional information to sequence (used in Transformer)"""
    def __init__(self, max_seq_len=30, d_model=768, **kwargs):
        super().__init__(**kwargs)
        self.max_seq_len = max_seq_len
        self.d_model = d_model
        
        # Create positional encoding matrix
        position = np.arange(max_seq_len)[:, np.newaxis]
        div_term = np.exp(np.arange(0, d_model, 2) * -(np.log(10000.0) / d_model))
        
        pe = np.zeros((max_seq_len, d_model))
        pe[:, 0::2] = np.sin(position * div_term)
        pe[:, 1::2] = np.cos(position * div_term[:pe.shape[1] // 2])
        
        self.pos_encoding = tf.constant(pe, dtype=tf.float32)
    
    def call(self, x):
        seq_len = tf.shape(x)[1]
        pos_enc = tf.cast(self.pos_encoding[:seq_len, :self.d_model], x.dtype)
        return x + pos_enc
    
    def get_config(self):
        config = super().get_config()
        config.update({
            'max_seq_len': self.max_seq_len,
            'd_model': self.d_model
        })
        return config


class AttentionLayer(layers.Layer):
    """Attention mechanism for sequence features (used in BiLSTM models)"""
    def __init__(self, units=64, **kwargs):
        super().__init__(**kwargs)
        self.units = units
        
    def build(self, input_shape):
        self.W = layers.Dense(self.units, activation='tanh')
        self.V = layers.Dense(1)
        super().build(input_shape)
    
    def call(self, inputs):
        # inputs: [batch, seq_len, features]
        score = self.V(self.W(inputs))  # [batch, seq_len, 1]
        attention_weights = tf.nn.softmax(score, axis=1)
        context = attention_weights * inputs
        context = tf.reduce_sum(context, axis=1)  # [batch, features]
        return context
    
    def get_config(self):
        config = super().get_config()
        config.update({'units': self.units})
        return config


class MultiHeadAttentionLayer(layers.Layer):
    """Multi-head attention for feature fusion (used in Fusion model)"""
    def __init__(self, num_heads=4, key_dim=64, **kwargs):
        super().__init__(**kwargs)
        self.num_heads = num_heads
        self.key_dim = key_dim
        
    def build(self, input_shape):
        self.mha = layers.MultiHeadAttention(
            num_heads=self.num_heads,
            key_dim=self.key_dim,
            dropout=0.1
        )
        self.layernorm = layers.LayerNormalization()
        super().build(input_shape)
    
    def call(self, inputs, training=False):
        attn_output = self.mha(inputs, inputs, training=training)
        out = self.layernorm(inputs + attn_output)
        return out
    
    def get_config(self):
        config = super().get_config()
        config.update({
            'num_heads': self.num_heads,
            'key_dim': self.key_dim
        })
        return config


class TransformerBlock(layers.Layer):
    """Single transformer encoder block (used in Transformer ViT model)"""
    def __init__(self, d_model, num_heads, ff_dim, dropout=0.1, **kwargs):
        super().__init__(**kwargs)
        self.d_model = d_model
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.dropout_rate = dropout
        
    def build(self, input_shape):
        self.att = layers.MultiHeadAttention(
            num_heads=self.num_heads,
            key_dim=self.d_model // self.num_heads,
            dropout=self.dropout_rate
        )
        self.ffn = keras.Sequential([
            layers.Dense(self.ff_dim, activation='relu'),
            layers.Dropout(self.dropout_rate),
            layers.Dense(self.d_model)
        ])
        
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = layers.Dropout(self.dropout_rate)
        self.dropout2 = layers.Dropout(self.dropout_rate)
        super().build(input_shape)
    
    def call(self, inputs, training=False):
        # Multi-head attention
        attn_output = self.att(inputs, inputs, training=training)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        
        # Feed-forward network
        ffn_output = self.ffn(out1, training=training)
        ffn_output = self.dropout2(ffn_output, training=training)
        out2 = self.layernorm2(out1 + ffn_output)
        
        return out2
    
    def get_config(self):
        config = super().get_config()
        config.update({
            'd_model': self.d_model,
            'num_heads': self.num_heads,
            'ff_dim': self.ff_dim,
            'dropout': self.dropout_rate
        })
        return config

class FMAEEncoder(layers.Layer):
    """EfficientNet-B0 based encoder for FMAE (compatibility wrapper)"""
    def __init__(self, latent_dim=256, **kwargs):
        super().__init__(**kwargs)
        self.latent_dim = latent_dim
        
    def call(self, inputs):
        return inputs
        
    def get_config(self):
        config = super().get_config()
        config.update({'latent_dim': self.latent_dim})
        return config

CUSTOM_OBJECTS = {
    'PositionalEncoding': PositionalEncoding,
    'AttentionLayer': AttentionLayer,
    'MultiHeadAttentionLayer': MultiHeadAttentionLayer,
    'TransformerBlock': TransformerBlock,
    'FMAEEncoder': FMAEEncoder,
}

# ============================================================================
# Model Loader Class (Unified with smartlms-backend)
# ============================================================================

def load_model_with_custom_layers(path, compile=False):
    """Load Keras model with custom layers registered."""
    try:
        # Register custom objects
        with keras.utils.custom_object_scope(CUSTOM_OBJECTS):
            try:
                keras.config.enable_unsafe_deserialization()
            except:
                pass
            model = keras.models.load_model(path, compile=compile, safe_mode=False)
        logger.info(f"Successfully loaded model from {path}")
        return model
    except Exception as e:
        logger.error(f"Failed to load model {path}: {e}")
        return None

class ExportModelLoader:
    def list_models(self, export_dir):
        pass

    def load_model(self, path):
        return load_model_with_custom_layers(path)

    def predict(self, model, features):
        """
        Inference with dimension handling.
        features can be a dict containing 'raw', 'vit', 'fmae' or a numpy array.
        """
        if model is None: return None

        # 1. Determine Target Shape
        try:
            # Handle list-wrapped input shapes
            in_shape = model.input_shape
            if isinstance(in_shape, list): in_shape = in_shape[0]
            
            target_feats = in_shape[2] if len(in_shape) >= 3 else 22
            target_seq = in_shape[1] if in_shape[1] else 30
        except Exception as e:
            target_feats = 22
            target_seq = 30

        # 2. Extract Correct Dimension
        x = None
        if isinstance(features, dict):
            if target_feats == 768:
                x = features.get('vit')
            elif target_feats == 256:
                x = features.get('fmae')
            elif target_feats == 1565:
                # Construct Fusion Feature
                vit = features.get('vit')
                fmae = features.get('fmae')
                raw = features.get('raw')
                if vit is not None and fmae is not None and raw is not None:
                    # Map raw 31 to 22 for legacy compatibility in Fusion
                    idx_map = list(range(17)) + [23, 24, 28, 29, 30]
                    raw_mapped = raw[:, idx_map] if raw.shape[1] >= 31 else raw[:, :22]
                    # Concatenate ViT + FMAE + MappedRaw
                    combined = np.concatenate([vit, fmae, raw_mapped], axis=-1)
                    pad_dim = 1565 - combined.shape[-1]
                    if pad_dim > 0:
                        pad = np.zeros((combined.shape[0], pad_dim), dtype=np.float32)
                        x = np.concatenate([combined, pad], axis=-1)
                    else:
                        x = combined[:, :1565]
            else:
                x = features.get('raw')
                if x is not None and x.shape[1] > target_feats:
                    x = x[:, :target_feats]
        else:
            x = features

        if x is None:
            return None

        # 3. Shape Handling
        if len(x.shape) == 2:
            # (seq, dim) -> (1, 30, dim)
            if x.shape[0] < target_seq:
                pad = np.zeros((target_seq - x.shape[0], x.shape[1]), dtype=np.float32)
                x = np.vstack([pad, x])
            x = x[-target_seq:, :]
            x = np.expand_dims(x, axis=0)
        elif len(x.shape) == 3 and x.shape[0] == 1:
            # Already has batch dim, just check seq_len
            if x.shape[1] != target_seq:
                # Truncate/Pad
                curr = x[0]
                if curr.shape[0] < target_seq:
                    pad = np.zeros((target_seq - curr.shape[0], curr.shape[1]), dtype=np.float32)
                    curr = np.vstack([pad, curr])
                else:
                    curr = curr[-target_seq:, :]
                x = np.expand_dims(curr, axis=0)

        # 4. Predict
        try:
            raw_output = model.predict(x, verbose=0)
            results = {}
            dims = ["boredom", "engagement", "confusion", "frustration"]
            
            # Case A: List of outputs (Transformers, Fusion)
            if isinstance(raw_output, list) and len(raw_output) >= 4:
                for i, out_tensor in enumerate(raw_output[:4]):
                    probs = out_tensor[0]
                    score = np.sum(probs * np.arange(4)) / 3.0 * 100.0
                    results[dims[i]] = float(score)
            
            # Case B: Single output (Baseline/BiLSTM if single-task)
            elif not isinstance(raw_output, list):
                if len(raw_output.shape) == 2 and raw_output.shape[1] == 4:
                    probs = raw_output[0]
                    results["engagement"] = float(np.sum(probs * np.arange(4)) / 3.0 * 100.0)
                elif len(raw_output.shape) == 3 and raw_output.shape[2] == 4:
                    # Sequence output? (1, 30, 4) -> take last
                    probs = raw_output[0, -1, :]
                    results["engagement"] = float(np.sum(probs * np.arange(4)) / 3.0 * 100.0)

            if not results:
                return None
                
            vals = [v for k,v in results.items() if k in dims]
            overall = float(np.mean(vals)) if vals else results.get("engagement", 0.0)
            
            return {
                "dimensions": {k: {"score": v} for k, v in results.items()},
                "overall_proxy": overall
            }
        except Exception as e:
            # Absolute visibility for debugging
            print(f"DEBUG: Inference error in model_loader: {e}")
            return None

loader = ExportModelLoader()
load_model = loader.load_model
predict = loader.predict
