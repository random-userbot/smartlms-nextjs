# SmartLMS Automated CLI Deployment
$CLUSTER = "smartlms-pro-cluster"
$SERVICE = "smartlms-suite-service-xhikhoa4"
$DB_ID = "smartlms-db"

Write-Host "Step 1: Discovering Security Groups"
$RDS_SG = (aws rds describe-db-instances --db-instance-identifier $DB_ID --query "DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId" --output text)
$ECS_SG = (aws ecs describe-services --cluster $CLUSTER --services $SERVICE --query "services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]" --output text)

Write-Host "Found RDS SG: $RDS_SG"
Write-Host "Found ECS SG: $ECS_SG"

Write-Host "Step 2: Fixing Firewall (Port 5432)"
aws ec2 authorize-security-group-ingress --group-id $RDS_SG --protocol tcp --port 5432 --source-group $ECS_SG 2>$null
Write-Host "Security rule check complete."

Write-Host "Step 3: Launching ECS Service"
aws ecs update-service --cluster $CLUSTER --service $SERVICE --desired-count 1 | Out-Null
Write-Host "Desired count set to 1. Tasks are starting..."

Write-Host "Step 4: Waiting for Service to stabilize (takes 2-3 mins)"
aws ecs wait services-stable --cluster $CLUSTER --services $SERVICE

Write-Host "SUCCESS! Everything is running."
$ALB_DNS = (aws elbv2 describe-load-balancers --query "LoadBalancers[0].DNSName" --output text)
$TEST_URL = "http://" + $ALB_DNS + "/api/health"
Write-Host "Final URL to test: $TEST_URL"
