# SmartLMS AWS Cost Management Guide

Use this guide to "Hibernate" your project when you are not actively testing to save on monthly costs.

---

## ⏸️ Hibernation (Stop Charges)
Run these commands in AWS CloudShell or your terminal to pause compute and database fees.

### 1. Stop Backend Containers
This stops the Fargate compute billing immediately.
```bash
aws ecs update-service --cluster smartlms-pro-cluster --service smartlms-suite-service-xhikhoa4 --desired-count 0 --region ap-south-2
```

### 2. Stop Database
This stops the RDS instance charges. (Note: AWS will automatically restart it after 7 days for maintenance; you'll need to run this command again if it does).
```bash
aws rds stop-db-instance --db-instance-identifier smartlms-db --region ap-south-2
```

> [!WARNING]
> **Persistent Costs**: The Application Load Balancer (ALB) and RDS Storage cannot be "paused." You will still be charged roughly **$20/month** for the Load Balancer even while your app is stopped. To save this $20, you must delete the ALB entirely.

---

## ▶️ Resumption (Restart Project)
Follow these steps to bring the system back online.

### 1. Wake up the Database
**IMPORTANT**: Wait ~5 minutes after running this command until the RDS status in the console says "Available" before starting the containers.
```bash
aws rds start-db-instance --db-instance-identifier smartlms-db --region ap-south-2
```

### 2. Restart Backend Containers
```bash
aws ecs update-service --cluster smartlms-pro-cluster --service smartlms-suite-service-xhikhoa4 --desired-count 1 --region ap-south-2
```

---

## 🚀 Health Check
Run this script to verify everything is back up:
```powershell
./smartlms-backend/check_production_health.ps1
```

## 🧨 Emergency Kill Switch (Delete All)
Run these only if you want to **delete the entire project** and all its data.
```bash
# ECS
aws ecs delete-service --cluster smartlms-pro-cluster --service smartlms-suite-service-xhikhoa4 --force --region ap-south-2
# ALB
aws elbv2 delete-load-balancer --load-balancer-arn [YOUR_ALB_ARN] --region ap-south-2
# RDS
aws rds delete-db-instance --db-instance-identifier smartlms-db --skip-final-snapshot --region ap-south-2
```
