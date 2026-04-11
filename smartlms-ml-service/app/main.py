from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
import sys

import asyncio
from contextlib import asynccontextmanager

# Add current directory to path so 'app.ml' imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.engagement_model import get_engagement_model
from app.ml.export_inference_registry import get_export_model_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for ML Service"""
    registry = get_export_model_registry()
    
    # Eager preload if not in sleep window
    registry.preload_all_models()

    from app.worker import worker_loop

    async def neural_sleep_monitor():
        """Monitor for 10m idle or 2-7 AM window to purge RAM"""
        try:
            # Initial wait to allow startup to settle
            await asyncio.sleep(60) 
            while True:
                # 1. Idle Purge (10 mins)
                registry.cleanup_if_idle(10)
                
                # 2. Nightly Window Check (2-7 AM IST)
                if registry.is_in_sleep_window():
                    if registry._loaded_models:
                        print("[MEMORY] Nightly window active. Purging neural RAM.", flush=True)
                        registry._loaded_models.clear()
                        import gc
                        gc.collect()
                
                await asyncio.sleep(300) # Check every 5 mins
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Neural Monitor Error: {e}")

    app.monitor_task = asyncio.create_task(neural_sleep_monitor())
    app.worker_task = asyncio.create_task(worker_loop())
    yield
    # Shutdown
    if hasattr(app, "monitor_task"):
        app.monitor_task.cancel()

app = FastAPI(title="SmartLMS ML Service", version="1.0.0", lifespan=lifespan)
logger = logging.getLogger("uvicorn.error")

# --- Schemas ---

class EngagementFeature(BaseModel):
    # Facial features
    gaze_score: float = 0.0
    head_pose_yaw: float = 0.0
    head_pose_pitch: float = 0.0
    head_pose_roll: float = 0.0
    head_pose_stability: float = 0.0
    eye_aspect_ratio_left: float = 0.0
    eye_aspect_ratio_right: float = 0.0
    blink_rate: float = 0.0
    mouth_openness: float = 0.0

    # Action Unit proxies
    au01_inner_brow_raise: float = 0.0
    au02_outer_brow_raise: float = 0.0
    au04_brow_lowerer: float = 0.0
    au06_cheek_raiser: float = 0.0
    au12_lip_corner_puller: float = 0.0
    au15_lip_corner_depressor: float = 0.0
    au25_lips_part: float = 0.0
    au26_jaw_drop: float = 0.0

    # Behavioral
    keyboard_active: bool = False
    mouse_active: bool = False
    tab_visible: bool = True
    playback_speed: float = 1.0
    note_taking: bool = False
    
    # Optional visual embedding (already computed or to be used by model)
    visual_embedding: Optional[List[float]] = None

class InferenceRequest(BaseModel):
    model_id: str
    features: List[EngagementFeature]

class EnsembleRequest(BaseModel):
    base_scores: Dict[str, Any]
    features: List[EngagementFeature]

# --- Endpoints ---

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "smartlms-ml-service"}

@app.get("/models")
async def list_models():
    registry = get_export_model_registry()
    return registry.list_models()

@app.post("/infer")
async def infer(request: InferenceRequest):
    try:
        registry = get_export_model_registry()
        features_dicts = [f.model_dump() for f in request.features]
        result = registry.infer(model_id=request.model_id, features=features_dicts)
        
        # Add forecast for built-in model
        if request.model_id == "builtin::xgboost":
            model = get_engagement_model()
            current_score = result.get("output", {}).get("overall", 50.0)
            result["output"]["forecast"] = model.forecast_next(features_dicts, current_score)
            
        return result
    except Exception as e:
        logger.error(f"Inference error for {request.model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ensemble")
async def ensemble(request: EnsembleRequest):
    """
    Combines fast base scores with deep ensemble results.
    Mirroring the logic in backend/app/routers/engagement.py:apply_export_xgb_ensemble
    """
    try:
        registry = get_export_model_registry()
        features_dicts = [f.model_dump() for f in request.features]
        
        # 1. Fetch available models
        models = registry.list_models()
        # Include all recommended models (ViT, BiLSTM, Fusion, etc.)
        export_models = [m["model_id"] for m in models if m["model_id"].startswith("export::") and m.get("recommended")]
        
        if not export_models:
            return request.base_scores

        all_results = []
        print(f"\n[NEURAL_ENROLL] Syncing deep ensemble for {len(export_models)} target models...", flush=True)
        
        # Increase slice to include ViT (usually the 3rd or 4th in the list)
        for mid in export_models[:4]: 
            try:
                print(f" -> Accessing: {mid}...", end="", flush=True)
                res = registry.infer(mid, features_dicts)
                output = res.get("output", {})
                if isinstance(output, dict) and "dimensions" in output:
                    dims = output["dimensions"]
                    # Convert to weight based scores
                    def _w(dname):
                        d = dims.get(dname, {})
                        probs = d.get("probabilities", [])
                        if len(probs) == 4:
                            import numpy as np
                            return float(sum(p * (idx / 3.0 * 100.0) for idx, p in enumerate(probs)))
                        return float(d.get("class_index", 0) * 33.3)
                    
                    print(" [SUCCESS: Neural Node Captured]", flush=True)
                    all_results.append({
                        "model_id": mid,
                        "engagement": _w("engagement"),
                        "boredom": _w("boredom"),
                        "confusion": _w("confusion"),
                        "frustration": _w("frustration")
                    })
            except Exception as e:
                print(f" [FAILED: {e}]", flush=True)
                continue

        if not all_results:
            return request.base_scores

        import numpy as np
        
        # Calculate final ensembled scores (Average across all successful neural nodes + base XGB)
        final_scores = {
            "engagement": float(np.mean([r["engagement"] for r in all_results] + [request.base_scores["engagement"]])),
            "boredom": float(np.mean([r["boredom"] for r in all_results] + [request.base_scores["boredom"]])),
            "confusion": float(np.mean([r["confusion"] for r in all_results] + [request.base_scores["confusion"]])),
            "frustration": float(np.mean([r["frustration"] for r in all_results] + [request.base_scores["frustration"]])),
            "ensemble_model_count": len(all_results),
            "model_type": "deep_ensemble_v2"
        }
        
        # Weighted average for overall score (Engagement weight is higher)
        # engagement - boredom + 100 / 2
        final_scores["overall"] = float((final_scores["engagement"] + (100 - final_scores["boredom"])) / 2.0)
        
        # Add forecast
        model = get_engagement_model()
        final_scores["forecast"] = model.forecast_next(features_dicts, final_scores["overall"])
        
        print(f"║ FINAL ENSEMBLE SCORE: {final_scores['overall']:.1f}% ({len(all_results)} Models Syncing) ║\n", flush=True)
        return final_scores
        
    except Exception as e:
        logger.error(f"Ensemble error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
