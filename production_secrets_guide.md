# SmartLMS Production Deployment: Secrets Guide

This document lists the required environment variables (secrets) for each of the three main components of the SmartLMS platform. 

> [!IMPORTANT]
> **YouTube Resilience**: The values for `YOUTUBE_COOKIES`, `PO_TOKEN`, and `VISITOR_DATA` must be refreshed if the backend begins receiving "Bot Detection" errors again.

---

## 1. Backend Container (`smartlms-backend-task`)
Required for FastAPI, YouTube processing, and AI features.

| Variable | Description | Example / Note |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL Async Connection | `postgresql+asyncpg://user:pass@host:5432/db` |
| `DATABASE_URL_SYNC` | PostgreSQL Sync Connection | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | Secret for Auth Tokens | Use a long, random alphanumeric string |
| `GROQ_API_KEY` | Inference for AI tutor | Starting with `gsk_...` |
| `AWS_ACCESS_KEY_ID` | SQS and S3 Permissions | Provided via IAM in AWS console |
| `AWS_SECRET_ACCESS_KEY` | SQS and S3 Permissions | Provided via IAM in AWS console |
| `SQS_QUEUE_URL` | Engagement Queue | URL from the SQS Dashboard |
| `AWS_REGION` | AWS Data Center | `ap-south-2` |
| `YOUTUBE_COOKIES` | Netscape Cookie Block | **Paste the full multi-line text block** |
| `YOUTUBE_PO_TOKEN` | Proof of Origin Token | Generated via `youtube-po-token-generator` |
| `YOUTUBE_VISITOR_DATA` | YouTube Session ID | Paired with the PO Token |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID | From Google Cloud Console |

---

## 2. ML Worker Container (`ml-api-task`)
Required for polling SQS and performing real-time inference.

| Variable | Description | Example / Note |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL Async Connection | **Required** to save engagement scores |
| `SQS_QUEUE_URL` | Engagement Queue | **Required** to pull jobs from backend |
| `AWS_ACCESS_KEY_ID` | SQS Read Permissions | Provided via IAM |
| `AWS_SECRET_ACCESS_KEY` | SQS Read Permissions | Provided via IAM |
| `AWS_REGION` | AWS Data Center | `ap-south-2` |

---

## 3. Frontend Environment (Vercel / Build Time)
Required during the `npm run build` phase.

| Variable | Description | Example / Note |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | Production Backend URL | `https://smartlms.online` (No `/api` at end) |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID | Must match the Backend's Google ID |
| `NEXT_PUBLIC_APP_NAME` | Website Title | `SmartLMS` |

---

## Deployment Sync Checklist
1. [ ] **Update Secrets**: Manually update the Environment tab in AWS ECS for both Backend and ML tasks.
2. [ ] **Fresh Build**: Ensure `YOUTUBE_PO_TOKEN` is the one you just generated (they can expire after a few days).
3. [ ] **Service Restart**: In the AWS ECS Console, click **"Update Service"** and check **"Force new deployment"** for both tasks.
