import boto3
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    SmartLMS CREDIT SAFEGUARD (Hard Cap)
    Triggered when budget exceeds $80/month.
    Actions:
    1. Scale all ECS Services (Backend + ML) to 0.
    2. Stop RDS Instance (db.t4g.micro).
    """
    ecs = boto3.client('ecs')
    rds = boto3.client('rds')
    
    cluster_name = os.environ.get('ECS_CLUSTER_NAME', 'SmartLMS-Cluster')
    services = os.environ.get('ECS_SERVICES', '').split(',')
    rds_instance_id = os.environ.get('RDS_INSTANCE_ID', 'SmartLMS-DB')

    logger.info(f"CRITICAL: Budget Limit Reached. Shutting down {len(services)} services and RDS.")

    # 1. Scale ECS Services to 0
    for service_name in services:
        if service_name.strip():
            try:
                ecs.update_service(
                    cluster=cluster_name,
                    service=service_name.strip(),
                    desiredCount=0
                )
                logger.info(f"Successfully scaled {service_name} to 0.")
            except Exception as e:
                logger.error(f"Failed to scale {service_name}: {e}")

    # 2. Stop RDS Instance (Idempotent)
    try:
        # Check if instance is already stopped or stopping
        response = rds.describe_db_instances(DBInstanceIdentifier=rds_instance_id)
        status = response['DBInstances'][0]['DBInstanceStatus']
        
        if status == 'available':
            rds.stop_db_instance(DBInstanceIdentifier=rds_instance_id)
            logger.info(f"Successfully stopped RDS: {rds_instance_id}")
        else:
            logger.info(f"RDS {rds_instance_id} is in state '{status}'. No action needed.")
    except Exception as e:
        logger.error(f"Failed to stop RDS: {e}")

    return {
        'statusCode': 200,
        'body': 'SmartLMS Safeguard: All services terminated to protect credits.'
    }
