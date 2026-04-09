# SmartLMS Production Health Check
$REGION = "ap-south-2"
$CLUSTER = "smartlms-pro-cluster"
$SERVICE = "smartlms-suite-service-xhikhoa4"
$DB = "smartlms-db"

Write-Host "`n--- Checking SmartLMS Infrastructure Status ---" -ForegroundColor Cyan

# 1. Check RDS
Write-Host "`n[1/3] Checking RDS Database..." -NoNewline
$dbStatus = (aws rds describe-db-instances --db-instance-identifier $DB --region $REGION --query "DBInstances[0].DBInstanceStatus" --output text)
if ($dbStatus -eq "available") { Write-Host " OK ($dbStatus)" -ForegroundColor Green } else { Write-Host " ALERT ($dbStatus)" -ForegroundColor Red }

# 2. Check Load Balancer & Health Checks
Write-Host "[2/3] Checking Load Balancer & Targets..."
$tgArn = "arn:aws:elasticloadbalancing:ap-south-2:472548058914:targetgroup/smartlms-backend-tg/c39da6e48a310f07"
$targetHealth = (aws elbv2 describe-target-health --target-group-arn $tgArn --region $REGION --query "TargetHealthDescriptions[0].TargetHealth.State" --output text)
if ($targetHealth -eq "healthy") { Write-Host "  - Backend Status: HEALTHY" -ForegroundColor Green } else { Write-Host "  - Backend Status: $targetHealth (Initializing or Failing)" -ForegroundColor Yellow }

# 3. Check ECS Tasks
Write-Host "[3/3] Checking ECS Service Deployment..."
$deployment = (aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION --query "services[0].deployments[0].{Status:status,Rollout:rolloutState,Reason:rolloutStateReason}" --output json)
$runningTasks = (aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION --query "services[0].runningCount" --output text)

Write-Host "  - Running Tasks: $runningTasks"
Write-Host "  - Deployment Status:"
$deployment

Write-Host "`n--- Check Complete ---" -ForegroundColor Cyan
