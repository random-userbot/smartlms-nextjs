import boto3
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from app.config import settings
from functools import lru_cache
import time

logger = logging.getLogger("uvicorn.error")

class MLClient:
    """
    Expert-level ML Client for SmartLMS.
    - Uses AWS SQS for Async Inference (Cost Optimized).
    - Implements In-Memory Caching (Performance Optimized).
    - Decoupled from ML Worker status.
    - Synchronous fallback via HTTP for real-time "Fast Scores".
    """
    def __init__(self):
        # SQS Client for pushing jobs
        self.sqs = None
        self.queue_url = settings.SQS_QUEUE_URL
        self.ml_service_url = settings.ML_SERVICE_URL
        
        # Simple Cache: {key: (timestamp, data)}
        self._cache = {}
        self._cache_ttl = 300 # 5 minutes

    def _get_sqs(self):
        if self.sqs is None:
            sqs_args = {'region_name': settings.AWS_REGION}
            if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                sqs_args.update({
                    'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY
                })
            self.sqs = boto3.client('sqs', **sqs_args)
        return self.sqs

    async def push_inference_job(self, log_id: str, features: List[Dict[str, Any]], model_id: str = "default") -> bool:
        """Push a feature batch to SQS for the ML Worker to process."""
        try:
            payload = {
                "log_id": log_id,
                "features": features,
                "model_id": model_id,
                "timestamp": str(time.time())
            }

            # Simulated push if no SQS URL is provided
            if not self.queue_url:
                print(f"║ [ASYNC_TELEMETRY] SIMULATED | ID: {log_id[:8]}... | Mode: Local Dev ║", flush=True)
                return True

            self._get_sqs().send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(payload)
            )
            
            print(f"║ [ASYNC_TELEMETRY] SUCCESS   | ID: {log_id[:8]}... | Queue: ...{self.queue_url[-12:]} ║", flush=True)
            return True
        except Exception as e:
            print(f"║ [ASYNC_TELEMETRY] FAILURE   | ID: {log_id[:8]}... | Error: {str(e)[:15]} ║", flush=True)
            logger.error(f"ML_CLIENT: Failed to push SQS job for {log_id}: {e}")
            return False

    async def infer(self, model_id: str, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform real-time inference via the ML service HTTP endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ml_service_url}/infer",
                    json={"model_id": model_id, "features": features}
                )
                if response.status_code == 200:
                    return response.json()
                logger.error(f"ML_CLIENT: /infer returned status {response.status_code}: {response.text}")
                return {"error": f"ML Service returned {response.status_code}"}
        except Exception as e:
            logger.warning(f"ML_CLIENT: HTTP Inference fallback failed: {type(e).__name__} - {e}")
            return {"error": str(e)}

    async def ensemble(self, base_scores: Dict[str, float], features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform deep model ensembling via the ML service HTTP endpoint."""
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"{self.ml_service_url}/ensemble",
                    json={"base_scores": base_scores, "features": features}
                )
                if response.status_code == 200:
                    return response.json()
                logger.error(f"ML_CLIENT: /ensemble returned status {response.status_code}: {response.text}")
                return base_scores # Fallback to base scores if ensemble fails
        except Exception as e:
            logger.warning(f"ML_CLIENT: HTTP Ensemble fallback failed: {type(e).__name__} - {e}")
            return base_scores

    def get_cached_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a result from the in-memory cache if not expired."""
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            else:
                del self._cache[key]
        return None

    def set_cached_result(self, key: str, data: Dict[str, Any]):
        """Cache a result for future requests."""
        self._cache[key] = (time.time(), data)

    async def get_models(self) -> List[Dict[str, Any]]:
        """Fetch available models from the ML service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ml_service_url}/models")
                if response.status_code == 200:
                    return response.json()
                return []
        except Exception:
            return [{"model_id": "export::Transformer_ViT_59.6%_BEST", "name": "Deep Ensemble (SOTA)"}]

ml_client = MLClient()
