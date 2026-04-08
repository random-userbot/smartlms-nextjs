# AWS Production Verification Checklist ✅

Follow these steps one-by-one to ensure your SmartLMS deployment is perfectly connected and running.

---

## 1. The "Heartbeat" Check (ALB & Backend)
First, verify that the entry point to your application is open.

- [ ] **ALB Status**: Go to **EC2 -> Load Balancers**. Status should be `Active`.
- [ ] **Target Group Health**: Go to **EC2 -> Target Groups -> smartlms-backend-tg**. 
  - [ ] Under the **Targets** tab, health must be `Healthy` (Green). 
- [ ] **API Health Check**: Visit your Load Balancer URL in a browser:
  - URL: `http://[YOUR-ALB-DNS-NAME]/api/health`
  - Expected Response: `{"status": "healthy", ...}`

---

## 2. Infrastructure Connectivity (Internal)
Verify the backend can talk to its "teammates."

- [ ] **Database (RDS)**: Check **CloudWatch Logs** for `smartlms-suite`.
  - Look for: `Database connection successful` or no database-related errors during startup.
- [ ] **Models (S3)**: Check the **ml-api** container logs.
  - Look for: `Successfully downloaded BiLSTM model from S3` or `ONNX models loaded`.
- [ ] **Bus (SQS)**: Ensure no errors in the **ml-worker** logs.
  - Look for: `Listening for messages on SQS query...`

---

## 3. Real-Time Logic (The "Big Test")
Verify that the AI engagement tracking actually works.

- [ ] **Authentication**: Log in to your frontend.
  - *If this works, RDS and JWT are definitely working.*
- [ ] **Engagement Capture**: Start a lecture and ensure the camera/waveform is active.
- [ ] **The "Magic" Link (SQS -> Worker)**:
  1. Capture a few frames of engagement.
  2. Go to the **SQS Console** -> **engagement-queue**.
  3. Verify that **Messages Available** increases (Backend sent a task) and then returns to 0 (Worker processed it).
- [ ] **Inference Persistence**: Check the "Analytics" tab in your frontend to see if the engagement graph has new data points.

---

## 4. Cost Control (Safety Check)
Ensure you don't get a surprise bill.

- [ ] **Task Count**: Verify you only have **1** task running in ECS.
- [ ] **Scaling**: Ensure "Auto Scaling" is disabled for now.
- [ ] **Retention**: Set CloudWatch log retention to 1 week (so logs don't grow forever).

---

### **Need to "Turn it Off" for the night?**
- To stop all costs but keep your setup:
  1. Update ECS Service -> **Desired Tasks: 0**.
  2. Delete the **Application Load Balancer** (Keep the Target Group and ECS Service).
  3. Leave **RDS** running (it's under Free Tier anyway).
