# SmartLMS Backend - Build and Push to ECR Production
$ACCOUNT_ID = "472548058914"
$REGION = "ap-south-2"
$ECR_REPO = "smartlms-backend"
$CLUSTER = "smartlms-pro-cluster"
$SERVICE = "smartlms-suite-service-xhikhoa4"

$ECR_URL = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

Write-Host "--- Starting Backend Production Build ---" -ForegroundColor Cyan

# 1. Login to ECR
Write-Host "Logging into AWS ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

if ($LASTEXITCODE -ne 0) { Write-Error "ECR Login Failed"; exit }

# 2. Build Docker Image (Hardenized for Fargate)
Write-Host "Building Docker Image (smartlms-backend:latest)..."
Set-Location smartlms-backend
docker build -t $ECR_REPO .

if ($LASTEXITCODE -ne 0) { Write-Error "Docker Build Failed"; exit }

# 3. Tag Image
Write-Host "Tagging Image..."
docker tag "$($ECR_REPO):latest" "$ECR_URL/$($ECR_REPO):latest"

# 4. Push to ECR
Write-Host "Pushing to ECR (this may take a few minutes)..."
docker push "$ECR_URL/$($ECR_REPO):latest"

if ($LASTEXITCODE -ne 0) { Write-Error "Docker Push Failed"; exit }

# 5. Trigger ECS Deployment
Write-Host "Updating ECS Service to deploy new image..."
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment

Write-Host "--- Backend Deployment Triggered Successfully ---" -ForegroundColor Green
Set-Location ..
