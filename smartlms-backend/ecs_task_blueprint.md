# ECS Task Definition Cheat Sheet (The "Suite")

Use this guide to copy-paste the configuration into your **AWS ECS Task Definition**.

## 1. Task Settings (General)
- **Family**: `smartlms-suite`
- **CPU**: `2 vCPU`
- **Memory**: `4 GB`
- **Task Role**: Ensure it has `AmazonS3ReadOnlyAccess` and `AmazonSQSFullAccess`.

---

## 2. Container: `backend`
The main web server that talks to the DB and the users.

- **Image**: `472548058914.dkr.ecr.ap-south-2.amazonaws.com/smartlms-backend:latest`
- **Port Mapping**:
  - **Container Port**: `8000`
  - **Protocol**: `TCP`
  - **App Protocol**: `HTTP`
- **Environment Variables**:
  - `DATABASE_URL`: `postgresql+asyncpg://smartlms_admin:[PASSWORD]@smartlms-db.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com:5432/smartlms`
  - `DATABASE_URL_SYNC`: `postgresql://smartlms_admin:[PASSWORD]@smartlms-db.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com:5432/smartlms`
  - `ML_SERVICE_URL`: `http://localhost:8001`
  - `SQS_QUEUE_URL`: `https://sqs.ap-south-2.amazonaws.com/512965611417/engagement-queue`
  - `AWS_REGION`: `ap-south-2`
  - `APP_ENV`: `production`

---

## 3. Container: `ml-api`
The "Brain" that does real-time scoring.

- **Image**: `472548058914.dkr.ecr.ap-south-2.amazonaws.com/smartlms-ml-service:latest`
- **Port Mapping**:
  - **Container Port**: `8001`
  - **Protocol**: `TCP`
  - **App Protocol**: `HTTP`
- **Environment Variables**:
  - `AWS_S3_MODEL_BUCKET`: `smartlms-models`
  - `MODEL_S3_PREFIX`: `models/`
  - `AWS_REGION`: `ap-south-2`

---

## 4. Container: `ml-worker`
The background assistant that processes engagement logs.

- **Image**: `472548058914.dkr.ecr.ap-south-2.amazonaws.com/smartlms-ml-service:latest`
- **Port Mappings**: **NONE** (Remove all)
- **Command Overrides**:
  - `python`, `-m`, `app.worker`
- **Environment Variables**:
  - `AWS_S3_MODEL_BUCKET`: `smartlms-models`
  - `MODEL_S3_PREFIX`: `models/`
  - `SQS_QUEUE_URL`: `https://sqs.ap-south-2.amazonaws.com/512965611417/engagement-queue`
  - `AWS_REGION`: `ap-south-2`

---

### **Final Checklist:**
1. ✅ **Ports**: Only 8000 and 8001 should be open.
2. ✅ **Passwords**: Replace `[PASSWORD]` with your real RDS password.
3. ✅ **Command**: Make sure the worker has the `app.worker` override.
