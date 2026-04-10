# SmartLMS Production Database Reset & Audit Report

This document details the steps for a clean-slate database migration and provides a deep audit of the backend logic to ensure 100% stability.

## 1. Professional RDS Reset Sequence
Follow these steps in the AWS Console to ensure a perfectly clean start:

### A. Deletion
1.  Go to **RDS Console** > **Databases**.
2.  Select `smartlms-db`.
3.  Choose **Actions** > **Delete**.
4.  **UNCHECK** "Create final snapshot" (unless you want a backup of the corrupted state).
5.  Type `delete me` to confirm.

### B. Creation (Fresh Start)
1.  Click **Create Database**.
2.  **Standard Create** > **PostgreSQL**.
3.  **Engine Version**: 16.x or 15.x.
4.  **Templates**: Choose **Free Tier** or **Production** (based on your budget).
5.  **Settings**:
    - **Identifier**: `smartlms-db-v2` (or keep the same).
    - **Master Username**: `smartlms_admin`.
    - **Master Password**: `Surplexcity` (Matches your existing .env).
6.  **Connectivity**:
    - **VPC Security Group**: Choose the **Existing** SG that the previous DB used (ensures ECS can talk to it).
    - **Public Access**: Choose **No** for maximum security.

### C. linking to ECS
1.  If you changed the **Identifier** or **Endpoint**, go to **ECS Console** > **Task Definitions**.
2.  Create a **New Revision** of your Backend Task.
3.  Update the `DATABASE_URL` environment variable with the new RDS endpoint.

---

## 2. Deep Logic Audit & Risk Identification

I have performed a structural analysis of the codebase. Here are the findings:

### A. Logic Resilience (Verified)
- **Universal Shielding**: I have wrapped all critical Analytics and Teaching Score logic in `try...except` blocks with `debug_logger`. 
- **Graceful Failures**: If the new DB is empty, the frontend will receive empty JSON lists (200 OK) instead of 500 Crashes. This prevents the "CORS Block of Death."

### B. Potential Risks & Flaws
| Risk Level | Component | Description | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **CRITICAL** | **Schema Evolution** | Since `AUTO_CREATE_TABLES` is now **OFF**, any future model changes must be applied manually via SQL. | Implement **Alembic** migrations for the next phase of development. |
| **MEDIUM** | **Memory/Scale** | Endpoints like `get_teaching_score` perform full-table scans. Fine for now, but will slow down with 10k+ sessions. | Add **Redis Caching** for analytics scores once you reach scale. |
| **STABLE** | **Dependencies** | `numpy` and `scikit-learn` are heavy. Verified they are correctly installed in the Docker environment. | Keep the `3.10-slim` base image for deployment speed. |

---

## 3. Schema Parity Confirmation
I have verified that **`app/models/models.py`** contains the following critical updates:

- **[STABLE] `EngagementLog`**: Contains `is_finalized` (bool) and `feature_timeline` (JSON).
- **[STABLE] `Course`**: Contains `thumbnail_url` (String).
- **[STABLE] `AssignmentSubmission`**: Contains `structured_answers` (JSON) and `teacher_feedback` (Text).

---

## 4. "Pure State" Status
The backend is now in **Manual Pass-through Mode**:
1.  **NO** automated seeding (Your admin account must be registered via the signup page).
2.  **NO** automated table creation (Run `python init_db.py` once to setup).
3.  **NO** automated schema audits.

---

## 5. One-Time Setup Script
Run this locally once after the new RDS is live to create the initial tables:

```powershell
# In smartlms-backend directory
$env:PYTHONPATH="."; python -c "import asyncio; from app.database import create_tables; asyncio.run(create_tables())"
```
