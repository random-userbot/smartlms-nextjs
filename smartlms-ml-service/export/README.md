# Exported Models Directory

Place your Keras/TensorFlow model folders here.
Each folder should contain a `best_model.h5` file.

Example:
smartlms-backend/export/
  Transformer_ViT_59.6%_BEST/
    best_model.h5
    test_results.json (optional)
  BiLSTM_Enhanced_FMAE_58.6%/
    best_model.h5
  Fusion_Enhanced_57.4%/
    best_model.h5

These models will be automatically discovered by the backend and listed for inference.
Ensure `tensorflow-cpu` is installed.
