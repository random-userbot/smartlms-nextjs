import boto3
import os
import sys

# AWS Settings
REGION = os.getenv('AWS_REGION', 'us-east-1')
INSTANCE_ID = os.getenv('EC2_INSTANCE_ID')

def lambda_handler(event, context):
    """
    AWS Lambda Handler to start or stop an EC2 instance.
    Expected event: {"action": "start"} or {"action": "stop"}
    """
    if not INSTANCE_ID:
        return {"error": "EC2_INSTANCE_ID environment variable not set"}

    ec2 = boto3.client('ec2', region_name=REGION)
    action = event.get('action', '').lower()

    try:
        if action == 'start':
            print(f"Starting instance: {INSTANCE_ID}")
            ec2.start_instances(InstanceIds=[INSTANCE_ID])
            return {"status": "starting", "instance_id": INSTANCE_ID}
        
        elif action == 'stop':
            print(f"Stopping instance: {INSTANCE_ID}")
            ec2.stop_instances(InstanceIds=[INSTANCE_ID])
            return {"status": "stopping", "instance_id": INSTANCE_ID}
        
        else:
            return {"error": f"Invalid action: {action}. Use 'start' or 'stop'."}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Local testing / CLI usage
    if len(sys.argv) < 2:
        print("Usage: python aws_power_manager.py [start|stop]")
        sys.exit(1)
    
    test_event = {"action": sys.argv[1]}
    print(lambda_handler(test_event, None))
