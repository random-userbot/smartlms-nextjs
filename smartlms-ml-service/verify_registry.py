import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[0]))

from app.ml.export_inference_registry import get_export_model_registry

def verify():
    reg = get_export_model_registry()
    print(f"Export Dir: {reg.export_dir}")
    print(f"Dir Exists: {reg.export_dir.exists()}")
    
    models = reg.discover_models()
    print(f"\nDiscovered {len(models)} models:")
    for m in models:
        print(f" - {m.name} [ID: {m.model_id}, Family: {m.family}]")

if __name__ == "__main__":
    verify()
