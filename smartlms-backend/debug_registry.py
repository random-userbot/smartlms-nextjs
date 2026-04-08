import os
import sys
from pathlib import Path

# Add app to path
sys.path.append(os.getcwd())

from app.ml.export_inference_registry import get_export_model_registry

registry = get_export_model_registry()
models = registry.list_models()

print(f"Registry Root: {registry.root}")
print(f"Export Dir: {registry.export_dir}")
print(f"Export Dir Exists: {registry.export_dir.exists()}")
print(f"Total Models: {len(models)}")

for m in models:
    print(f" - [{m['family']}] {m['name']} (Status: {m['status']})")

keras_models = [m for m in models if m['family'] == 'export_keras' and m['status'] != 'error']
print(f"Filtered Keras Models: {len(keras_models)}")
