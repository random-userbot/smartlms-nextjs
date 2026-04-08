# Baseline_LSTM_74.2%_BIASED

## Model Information
- **Accuracy**: 74.2%
- **Description**: WARNING: High accuracy is misleading - only predicts Engagement class
- **Source Path**: models
- **Export Date**: 2025-11-22 13:50:18

## Files Exported
- best_model.h5 (1.52 MB)
- classification_report.json (0 MB)
- engagement_lstm_final.h5 (1.52 MB)
- evaluation_metrics.json (0 MB)
- training_history.csv (0 MB)

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
WARNING: High accuracy is misleading - only predicts Engagement class
