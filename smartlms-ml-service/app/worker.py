import os
import sys
import json
import asyncio
import boto3
import logging
import traceback
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session

# Add current directory to path so 'app.ml' imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import async_session
from app.models import EngagementLog, EngagementStatus
from app.ml.export_inference_registry import get_export_model_registry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smartlms-ml-worker")

def _get_sqs_client():
    """Build SQS client with fallback to IAM role if keys are missing."""
    sqs_args = {'region_name': settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        sqs_args.update({
            'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
            'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY
        })
    return boto3.client('sqs', **sqs_args)

sqs = _get_sqs_client()

async def process_message(feature_payload):
    """
    Process a single engagement payload.
    """
    async with async_session() as db:
        log_id = feature_payload.get("log_id")
        if not log_id:
            logger.error("Message missing log_id")
            return

        try:
            # 1. Idempotency Check: Fetch current log state
            stmt = select(EngagementLog).where(EngagementLog.id == log_id)
            result = await db.execute(stmt)
            engagement_log = result.scalar_one_or_none()

            if not engagement_log:
                logger.error(f"Engagement log {log_id} not found in DB")
                return

            if engagement_log.status == EngagementStatus.COMPLETED:
                logger.info(f"Log {log_id} already processed. Skipping.")
                return

            # 2. Run Inference
            registry = get_export_model_registry()
            model_id = feature_payload.get("model_id", settings.MODEL_ID_DEFAULT)
            features = feature_payload.get("features", [])
            if model_id == "builtin::ensemble_pro":
                # Compute base scores first
                base_res = registry.infer("builtin::xgboost", features=features)
                base_outputs = base_res.get("output", {})
                
                # Fetch export models
                models = registry.list_models()
                export_models = [m["model_id"] for m in models if m["model_id"].startswith("export::") and m.get("recommended")]
                
                if not export_models:
                    output = base_outputs
                else:
                    all_results = []
                    for mid in export_models[:4]:
                        try:
                            res = registry.infer(mid, features)
                            o = res.get("output", {})
                            if isinstance(o, dict) and "dimensions" in o:
                                dims = o["dimensions"]
                                def _w(dname):
                                    d = dims.get(dname, {})
                                    probs = d.get("probabilities", [])
                                    if len(probs) == 4:
                                        return float(sum(p * (idx / 3.0 * 100.0) for idx, p in enumerate(probs)))
                                    return float(d.get("class_index", 0) * 33.3)
                                all_results.append({
                                    "engagement": _w("engagement"),
                                    "boredom": _w("boredom"),
                                    "confusion": _w("confusion"),
                                    "frustration": _w("frustration")
                                })
                        except Exception:
                            continue
                    
                    if not all_results:
                        output = base_outputs
                    else:
                        import numpy as np
                        output = {
                            "engagement": float(np.mean([r["engagement"] for r in all_results] + [base_outputs.get("engagement", 50.0)])),
                            "boredom": float(np.mean([r["boredom"] for r in all_results] + [base_outputs.get("boredom", 50.0)])),
                            "confusion": float(np.mean([r["confusion"] for r in all_results] + [base_outputs.get("confusion", 50.0)])),
                            "frustration": float(np.mean([r["frustration"] for r in all_results] + [base_outputs.get("frustration", 50.0)]))
                        }
                        output["overall"] = float((output["engagement"] + (100 - output["boredom"])) / 2.0)
            else:
                # Actual ML Inference
                result = registry.infer(model_id=model_id, features=features)
                output = result.get("output", {})
            
            # 3. Apply Results (Idempotent Update)
            engagement_log.status = EngagementStatus.COMPLETED
            # Handle different key names between registry output and DB model
            engagement_log.overall_score = output.get("overall") 
            engagement_log.engagement_score = output.get("engagement")
            engagement_log.boredom_score = output.get("boredom")
            engagement_log.confusion_score = output.get("confusion")
            engagement_log.frustration_score = output.get("frustration")
            
            # Store raw dimensions as JSON
            engagement_log.scores_timeline = json.dumps(output.get("dimensions", {}))
            
            # ICAP (Simplified for now)
            engagement_log.icap_classification = "active" if (output.get("overall", 0) > 60) else "passive"

            await db.commit()
            logger.info(f"[WORKER] Successfully processed log {log_id}. Score: {output.get('overall')}%")

        except Exception as e:
            logger.error(f"[WORKER] Error processing log {log_id}: {e}")
            logger.error(traceback.format_exc())
            try:
                engagement_log.status = EngagementStatus.FAILED
                engagement_log.error_message = str(e)
                await db.commit()
            except:
                pass

async def worker_loop():
    """Main worker loop with long polling and batching"""
    # Pre-warm models (Expert request 8)
    registry = get_export_model_registry()
    logger.info("[BOOT] Pre-loading ML models into RAM...")
    registry.preload_all_models()
    logger.info("[BOOT] SQS Worker Starting...")

    queue_url = settings.SQS_QUEUE_URL
    if not queue_url:
        logger.error("[BOOT] SQS_QUEUE_URL not set. Worker entering idle state.")
        while True:
            await asyncio.sleep(3600) # Sleep forever but keep task alive

    while True:
        try:
            # 1. Long Polling
            response = sqs.receive_message(
                QueueUrl=queue_url,
                AttributeNames=['All'],
                MaxNumberOfMessages=settings.SQS_MAX_MESSAGES,
                WaitTimeSeconds=settings.SQS_WAIT_TIME_SECONDS
            )

            messages = response.get('Messages', [])
            if not messages:
                continue

            logger.info(f"[WORKER] Received batch of {len(messages)} jobs")

            # 2. Process Batch
            entries_to_delete = []
            for msg in messages:
                receipt_handle = msg['ReceiptHandle']
                msg_id = msg['MessageId']
                try:
                    body = json.loads(msg['Body'])
                    # Process sequentially within batch to avoid DB session concurrency issues 
                    # unless using a pool, but simpler is safer for now.
                    await process_message(body)
                    
                    entries_to_delete.append({
                        'Id': msg_id,
                        'ReceiptHandle': receipt_handle
                    })
                except Exception as e:
                    logger.error(f"[WORKER] Error parsing message body: {e}")
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

            # 3. Batch Delete from SQS
            if entries_to_delete:
                try:
                    sqs.delete_message_batch(
                        QueueUrl=queue_url,
                        Entries=entries_to_delete
                    )
                except Exception as e:
                    logger.error(f"[WORKER] SQS Batch Delete Failed: {e}")
        except Exception as e:
            logger.error(f"[WORKER] Loop error: {e}")
            await asyncio.sleep(10)  # Wait before retry on fatal error

if __name__ == "__main__":
    asyncio.run(worker_loop())
