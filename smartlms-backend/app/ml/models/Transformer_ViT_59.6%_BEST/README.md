# Transformer_ViT_59.6%_BEST

## Model Information
- **Accuracy**: 59.6%
- **Description**: Best overall - ViT + Temporal Transformer (6 blocks, 8 heads)
- **Source Path**: pipeline3\models\transformer_20251118_071716
- **Export Date**: 2025-11-22 13:50:18

## Files Exported
- best_model.h5 (384.93 MB)
- test_results.json (0 MB)
- training_history.csv (0.01 MB)

## Usage
To load this model in Python:
```python
import tensorflow as tf

# Load the model
model = tf.keras.models.load_model('path/to/model.h5')

# Or for Keras format
model = tf.keras.models.load_model('path/to/model.keras')

# Make predictions
predictions = model.predict(your_data)
```

## Notes
Best overall - ViT + Temporal Transformer (6 blocks, 8 heads)
