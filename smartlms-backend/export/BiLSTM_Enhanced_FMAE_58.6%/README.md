# BiLSTM_Enhanced_FMAE_58.6%

## Model Information
- **Accuracy**: 58.6%
- **Description**: Second best - Bi-LSTM with FER2013 transfer learning
- **Source Path**: pipeline3\models\model1_enhanced
- **Export Date**: 2025-11-22 13:50:18

## Files Exported
- best_model.h5 (6.68 MB)
- test_results.json (0 MB)

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
Second best - Bi-LSTM with FER2013 transfer learning
