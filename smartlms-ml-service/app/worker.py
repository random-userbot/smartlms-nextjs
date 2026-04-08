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

# Initialize SQS client
sqs = boto3.client('sqs', region_name=settings.AWS_REGION)

async def process_message(feature_payload):
    """
    Process a single engagement payload.
    Payload expected format: {
        "log_id": str,
        "features": [...],
        "model_id": str,
        "timestamp": str
    }
    """
    async with async_session() as db:
        log_id = feature_payload.get("log_id")
        if not log_id:
            logger.error("Message missing log_id")
            return

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

        try:
            # 2. Run Inference
            registry = get_export_model_registry()
            model_id = feature_payload.get("model_id", settings.MODEL_ID_DEFAULT)
            features = feature_payload.get("features", [])
            
            # Actual ML Inference
            result = registry.infer(model_id=model_id, features=features)
            output = result.get("output", {})
            
            # 3. Apply Results (Idempotent Update)
            engagement_log.status = EngagementStatus.COMPLETED
            engagement_log.overall_score = output.get("overall_score")
            engagement_log.engagement_score = output.get("engagement")
            engagement_log.boredom_score = output.get("boredom")
            engagement_log.confusion_score = output.get("confusion")
            engagement_log.frustration_score = output.get("frustration")
            engagement_log.scores_timeline = output.get("timeline")
            engagement_log.shap_explanations = output.get("shap")
            
            # ICAP
            icap = result.get("icap", {})
            engagement_log.icap_classification = icap.get("classification")
            engagement_log.icap_evidence = icap.get("evidence")

            await db.commit()
            logger.info(f"Successfully processed log {log_id}")

        except Exception as e:
            logger.error(f"Error processing log {log_id}: {e}")
            logger.error(traceback.format_exc())
            engagement_log.status = EngagementStatus.FAILED
            engagement_log.error_message = str(e)
            await db.commit()

async def worker_loop():
    """Main worker loop with long polling and batching"""
    logger.info("ML Worker starting up...")
    
    # Pre-warm models (Expert request 8)
    registry = get_export_model_registry()
    logger.info("Pre-loading ML models into RAM...")
    registry.preload_all_models()
    logger.info("Models loaded. Ready for jobs.")

    queue_url = settings.SQS_QUEUE_URL
    if not queue_url:
        logger.error("SQS_QUEUE_URL not set. Worker exiting.")
        return

    while True:
        try:
            # 1. Long Polling + Batching (Expert requests 1 & 3)
            response = sqs.receive_message(
                QueueUrl=queue_url,
                AttributeNames=['All'],
                MaxNumberOfMessages=settings.SQS_MAX_MESSAGES,
                WaitTimeSeconds=settings.SQS_WAIT_TIME_SECONDS
            )

            messages = response.get('Messages', [])
            if not messages:
                # No messages, loop again (wait time ensures we don't spam)
                continue

            logger.info(f"Received batch of {len(messages)} messages")

            # 2. Process Batch
            tasks = []
            entries_to_delete = []
            for msg in messages:
                receipt_handle = msg['ReceiptHandle']
                msg_id = msg['MessageId']
                try:
                    body = json.loads(msg['Body'])
                    tasks.append(process_message(body))
                    entries_to_delete.append({
                        'Id': msg_id,
                        'ReceiptHandle': receipt_handle
                    })
                except Exception as e:
                    logger.error(f"Error parsing message body: {e}")
                    # Delete malformed messages one by one to avoid blocking the batch
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

            # 3. Parallel Execution of ML Inference tasks
            if tasks:
                await asyncio.gather(*tasks)

            # 4. Batch Delete from SQS (Expert Optimization: Reduce API calls)
            if entries_to_delete:
                try:
                    sqs.delete_message_batch(
                        QueueUrl=queue_url,
                        Entries=entries_to_delete
                    )
                    logger.info(f"Successfully deleted batch of {len(entries_to_delete)} messages from SQS")
                except Exception as e:
                    logger.error(f"WORKER: SQS Batch Delete Failed: {e}")
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(5)  # Wait before retry on fatal error

if __name__ == "__main__":
    asyncio.run(worker_loop())
