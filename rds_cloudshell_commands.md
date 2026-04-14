# AWS CloudShell RDS Verification Commands

Below is a comprehensive list of `psql` commands formatted to run directly in your AWS CloudShell. These commands will query your production RDS database and help us verify the state of your tables—especially tracking down why the analytics boards are empty, verifying transcript fetching, and diagnosing enrollment issues.

### Prerequisites (If you haven't already run this in your current session)
```bash
curl -o global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

**Base Connection String (for reference):**
```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem"
```

---

### 1. Give Yourself Admin Access
Run this to instantly upgrade your account to the Admin role (replace the email if you signed in with a different one):

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "UPDATE users SET role = 'ADMIN' WHERE email = 'revanthpuram004@gmail.com' RETURNING id, email, role, full_name;"
```

### 2. User & Role Audit
Check if users exist and understand the breakdown of roles:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT role, COUNT(*) FROM users GROUP BY role;"
```

### 3. Student Matrix & Enrollments (Debugging Empty Matrix)
The frontend filters students by a specific `status`. Let's see what the current enrollment statuses are set to (e.g., 'active' vs 'ACTIVE').

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT status, COUNT(*) FROM enrollments GROUP BY status;"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT id, course_id, student_id, status FROM enrollments LIMIT 10;"
```

### 4. Engagement Logs (Debugging 0% Analytics)
Teaching scores and class focus graphs rely heavily on `engagement_logs`. The backend demands `watch_duration >= 15` or `watch_duration * 1.25 >= total_duration`. Let's verify what data actually exists in these columns.

```bash
# Check the most recent 10 engagement logs
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT watch_duration, total_duration, status, engagement_score, started_at FROM engagement_logs ORDER BY started_at DESC LIMIT 10;"

# Count how many logs have 0 watch_duration (this would cause the analytics to drop them entirely)
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT COUNT(*) FROM engagement_logs WHERE watch_duration = 0 OR watch_duration IS NULL;"

# Check general engagement score averages
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT AVG(engagement_score) as avg_score, AVG(attention_lapse_duration) as avg_lapse FROM engagement_logs;"
```

### 5. Transcripts & Lectures (Debugging YouTube Fetch)
Check if your lectures are retaining any text in the `transcript` column, or if they are failing and staying completely empty.

```bash
# Check length of transcripts for recent lectures
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT id, title, LENGTH(transcript) as transcript_char_length FROM lectures ORDER BY created_at DESC LIMIT 10;"
```

### 6. ICAP Logs (Learning States)
This drives the Pedagogical Node Management / Learning Intelligence. Let's see if students have logged actual cognitive states (interactive, constructive, active, passive).

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT classification, COUNT(*) FROM icap_logs GROUP BY classification;"
```

### 7. Quiz Attempts Audit
Check if any quizzes have actually been taken, which contributes 10% toward the teacher score.

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT COUNT(*), AVG(score) FROM quiz_attempts;"
```

---

Run any of these in CloudShell to get immediate clarity into why the backend filters are isolating your frontend data. Paste the outputs of the **Student Matrix & Enrollments** and **Engagement Logs** sections back here so I can pinpoint exactly what lines of backend code we need to adjust further!### 8. Fix ICAP Logs Enum Case Mismatch
To ensure your Student Matrix and class focus graphs correctly load pedagogical data, normalize uppercase enums to lowercase:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "UPDATE icap_logs SET classification = 'ACTIVE' WHERE classification = 'active';"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "UPDATE icap_logs SET classification = 'INTERACTIVE' WHERE classification = 'interactive';"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "UPDATE icap_logs SET classification = 'CONSTRUCTIVE' WHERE classification = 'constructive';"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "UPDATE icap_logs SET classification = 'PASSIVE' WHERE classification = 'passive';"
```

### 9. AI Tutor Sessions
Check if your AI tutor interactions are logging correctly. A common issue is missing user relationships or orphaned sessions:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT id, student_id, title, created_at FROM ai_tutor_sessions ORDER BY created_at DESC LIMIT 5;"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT session_id, role, SUBSTRING(content, 1, 50) AS snippet FROM ai_tutor_messages ORDER BY created_at DESC LIMIT 5;"
```

### 10. Activity Logs (Platform Session Tracking)
Check general user "sessions" via the activity logs to see logins, logouts, switches:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT action, COUNT(*) FROM activity_logs GROUP BY action;"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT user_id, action, created_at FROM activity_logs ORDER BY created_at DESC LIMIT 10;"
```

### 11. Teaching Scores & Gamification
Verify if batch analytics updates have computed teaching scores correctly, and check points balance:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT module_id, overall_score, date FROM teaching_scores ORDER BY date DESC LIMIT 5;"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT user_id, points, level, tier_name FROM gamification LIMIT 10;"
```

### 12. Courses & Modules Verification
Finally, verify what courses are actually available to ensure the dashboard has data to pull:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT id, title, is_published FROM courses;"
```

### 13. Query Raw ML Features (Action Units, Embeddings, Gaze, etc.)
Your raw machine learning features (like AUs, eye_aspect_ratio, head_pose, blink_rate, and the full timeline of values) are stored inside the `engagement_logs` as JSON payload columns: `features` and `feature_timeline`. For dataset preparation, you can extract these specific JSON properties directly.

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT session_id, features->>'au_values' AS action_units, features->>'gaze_score' AS gaze, features->>'head_pose' AS head_rotation FROM engagement_logs WHERE features IS NOT NULL LIMIT 5;"

psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT session_id, LENGTH(feature_timeline::text) AS timeline_size_bytes FROM engagement_logs WHERE feature_timeline IS NOT NULL LIMIT 5;"
```
### 14. Bypass CloudShell Download Restrictions via S3 Presigned URL
If your VPC or AWS setup restricts clicking the "Download file" button directly in CloudShell, you can securely route the file through an S3 bucket and generate a direct download link.

```bash
# 1. Create a quick temporary bucket (must be uniquely named, feel free to add random numbers)
aws s3 mb s3://smartlms-dataset-temp-export-998877

# 2. Copy your exported dataset to the new bucket
aws s3 cp training_dataset_export.csv s3://smartlms-dataset-temp-export-998877/

# 3. Generate a secure, 1-hour public download link
aws s3 presign s3://smartlms-dataset-temp-export-998877/training_dataset_export.csv --expires-in 3600
```
**Next Steps:** Copy the `https://...` link that prints out, paste it into your local browser, and the massive CSV dataset will immediately download to your computer!
### 15. Check Live ML Streaming (Continuous Session Monitoring)
To verify your web browser's Neural Eye (AutoEngagementCapture) is successfully pushing 3-second batches to the backend constantly during a lecture, run this to track the `watch_duration` increasing in real-time for your latest session.

```bash
# Run this twice with a 10-second gap while watching a video in another tab. If watch_duration increases, the ML pipeline is streaming successfully!
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT session_id, student_id, watch_duration, status FROM engagement_logs ORDER BY started_at DESC LIMIT 3;"
```

### 16. Verify Transcripts & YouTube Fetching
If your transcripts are still failing, let's see exactly which YouTube URLs are breaking so we can determine if AWS IPs are being hard-blocked or if it's a private video/cookie issue:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "SELECT id, title, source_url, LENGTH(transcript) as transcript_char_size FROM lectures ORDER BY created_at DESC LIMIT 5;"
```

---

### 17. Safely Wipe All Analytics / Course Data (Keep Schema)
If you want to quickly clear all the generated data (sessions, quizzes, logs) without destroying the tables themselves or losing your Admin user account, `TRUNCATE` the tables. 

```bash
# Wipe all analytics, courses, and logs but KEEP users intact:
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "TRUNCATE TABLE courses, enrollments, lectures, materials, feedbacks, teaching_scores, messages, notifications, engagement_logs, attendance, quizzes, quiz_attempts, icap_logs, activity_logs, ai_tutor_sessions, ai_tutor_messages, gamification CASCADE;"
```

### 18. Wipe ABSOLUTELY EVERYTHING (Including Users)
If you want to wipe the **users** table as well (forcing everyone to re-register), just add `users` to the truncation list:

```bash
psql "host=smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com port=5432 dbname=smartlms user=postgres password=Surplexcity sslmode=verify-full sslrootcert=./global-bundle.pem" -c "TRUNCATE TABLE users CASCADE;"
```

# Netscape HTTP Cookie File
# This file was generated by Cookie Editor https://chromewebstore.google.com/detail/cookie-editor/ookdjilphngeeeghgngjabigmpepanpl
www.youtube.com	FALSE	/	FALSE	1791747597	ext_name	ojplmecpdpgccookcobabopnaifgidhf
.youtube.com	TRUE	/	TRUE	1791750090	PREF	f4=4000000&f6=40000000&tz=Asia.Calcutta&f5=30000&f7=150
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791184463	__Secure-BUCKET	COIG
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791360918	LOGIN_INFO	AFmmF2swRAIgB6SQKajKnCf0muh0mTKykSTfhLJSckIkbKGmnNCxBFMCIGvQb-izr80w9cSL82dEUtHN3Wwb7L5CAU5OWQkIgqQ6:QUQ3MjNmd1JXZDd4dWc0LVlBS0EwSURmaGppT2dSUFdMQmJkUDUzT2I2bUNtS3ZmbHJKc0t1N2JrTUNyeDFJYVhXUnl5cWgyQ3N1aGJIOVBRY2ZkTWJlUTYwWE5LODhScWxzVF9lU3B2UGc5S2VTV29WQmpTMlItS2hpQ3B0RDZhMWJnVzNfTklVa1VINFlzWWN0YXZkVlFOSVd5Z3R3SFN3
.youtube.com	TRUE	/	FALSE	1791744361	SID	g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZWJLMnNUYTZZjKdEjT39PwgACgYKAZwSARYSFQHGX2MiSzKmHHuXjrfhtvrqZGC0LBoVAUF8yKpDFkcWcuegVa3RTmj_DSqJ0076
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791744361	__Secure-1PSID	g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZG47KhPS8j0qVbr-t4vnsKAACgYKARISARYSFQHGX2MizrN_t8Erv9KmYf_x5amLQxoVAUF8yKoEvyys3R_wF9UmmQdswZIf0076
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791744361	__Secure-3PSID	g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZIjCK__QNo_MtvXQjAwLp7AACgYKAcUSARYSFQHGX2MizCUINjEN3DsDJYk6LG7FtxoVAUF8yKr408__rHPyd8sWf5zpjfuM0076
#HttpOnly_.youtube.com	TRUE	/	FALSE	1791744361	HSID	A06OA6vgi7g17bELM
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791744361	SSID	AqPjJcVMlJPUlU88Q
.youtube.com	TRUE	/	FALSE	1791744361	APISID	DTLfaREwiCSqqMJR/AezX_2hFQOsyjphRr
.youtube.com	TRUE	/	TRUE	1791744361	SAPISID	u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn
.youtube.com	TRUE	/	TRUE	1791744361	__Secure-1PAPISID	u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn
.youtube.com	TRUE	/	TRUE	1791744361	__Secure-3PAPISID	u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791745706	NID	530=JiPzaxnPPzf8iFNPWPkHohb9KOA1JibNbHH9I7YtyC6rrf6_v0RU9tOZwmEWFTWgAS-4VGyYWPTFdS6VcgqRuTOqTJx8eImnAXIuHk8pZY8AGj-X-XHPkWLwFxiPjU0yBqo7Nif-79A3kV0ITY8lQtSVrF3Mn109j8m63I7yR8PzQBdhAOlyspYgQf6SR2eWhm1z
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791751117	__Secure-1PSIDTS	sidts-CjQBWhotCQGcWZZXXn2Xfo62a8CEPjJtmd_f4GZbFvnMG3m-r6IJOFxWkl9FKYCQGGSsDixqEAA
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791751117	__Secure-3PSIDTS	sidts-CjQBWhotCQGcWZZXXn2Xfo62a8CEPjJtmd_f4GZbFvnMG3m-r6IJOFxWkl9FKYCQGGSsDixqEAA
.youtube.com	TRUE	/	FALSE	1791751117	SIDCC	AKEyXzWWlB1QrhGmNwR_sN2P3NvwgsyztwvFV5AuhrVoIrwfrA82kb-EO3PGUhf6CPyz-vIlMT0
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791751117	__Secure-1PSIDCC	AKEyXzU_ksdhq2EVjPVUl5jjOgPBXbkJMNe55vFaot5DB90MtZNqjZmD_lfJGpETYBY3PhSfSQ
#HttpOnly_.youtube.com	TRUE	/	TRUE	1791751117	__Secure-3PSIDCC	AKEyXzVuZ7PdUE26NcX-2RXvxDJFLj2PvRkZfrZPzNvYDyQ_Zy4hnZVLxEzPEOeFrT_F7XNVXQ

[
  {
    "domain": "www.youtube.com",
    "expirationDate": 1791747597.947822,
    "hostOnly": true,
    "httpOnly": false,
    "name": "ext_name",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "ojplmecpdpgccookcobabopnaifgidhf"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791750090.131975,
    "hostOnly": false,
    "httpOnly": false,
    "name": "PREF",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "f4=4000000&f6=40000000&tz=Asia.Calcutta&f5=30000&f7=150"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791184463.435477,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-BUCKET",
    "path": "/",
    "sameSite": "lax",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "COIG"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791360918.654035,
    "hostOnly": false,
    "httpOnly": true,
    "name": "LOGIN_INFO",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AFmmF2swRAIgB6SQKajKnCf0muh0mTKykSTfhLJSckIkbKGmnNCxBFMCIGvQb-izr80w9cSL82dEUtHN3Wwb7L5CAU5OWQkIgqQ6:QUQ3MjNmd1JXZDd4dWc0LVlBS0EwSURmaGppT2dSUFdMQmJkUDUzT2I2bUNtS3ZmbHJKc0t1N2JrTUNyeDFJYVhXUnl5cWgyQ3N1aGJIOVBRY2ZkTWJlUTYwWE5LODhScWxzVF9lU3B2UGc5S2VTV29WQmpTMlItS2hpQ3B0RDZhMWJnVzNfTklVa1VINFlzWWN0YXZkVlFOSVd5Z3R3SFN3"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.338931,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZWJLMnNUYTZZjKdEjT39PwgACgYKAZwSARYSFQHGX2MiSzKmHHuXjrfhtvrqZGC0LBoVAUF8yKpDFkcWcuegVa3RTmj_DSqJ0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.33917,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZG47KhPS8j0qVbr-t4vnsKAACgYKARISARYSFQHGX2MizrN_t8Erv9KmYf_x5amLQxoVAUF8yKoEvyys3R_wF9UmmQdswZIf0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.33923,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a0008wj_5oqbhSk7eDd0rS66tfjrMLK_NCYdxMU3tJdPz-m_Ai2ZIjCK__QNo_MtvXQjAwLp7AACgYKAcUSARYSFQHGX2MizCUINjEN3DsDJYk6LG7FtxoVAUF8yKr408__rHPyd8sWf5zpjfuM0076"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339403,
    "hostOnly": false,
    "httpOnly": true,
    "name": "HSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "A06OA6vgi7g17bELM"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339526,
    "hostOnly": false,
    "httpOnly": true,
    "name": "SSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AqPjJcVMlJPUlU88Q"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339603,
    "hostOnly": false,
    "httpOnly": false,
    "name": "APISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "DTLfaREwiCSqqMJR/AezX_2hFQOsyjphRr"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339673,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339742,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-1PAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791744361.339814,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-3PAPISID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "u1B1NTscm26rTxbR/A1be5pVKOxaqIn5Sn"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791745706.173915,
    "hostOnly": false,
    "httpOnly": true,
    "name": "NID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "530=JiPzaxnPPzf8iFNPWPkHohb9KOA1JibNbHH9I7YtyC6rrf6_v0RU9tOZwmEWFTWgAS-4VGyYWPTFdS6VcgqRuTOqTJx8eImnAXIuHk8pZY8AGj-X-XHPkWLwFxiPjU0yBqo7Nif-79A3kV0ITY8lQtSVrF3Mn109j8m63I7yR8PzQBdhAOlyspYgQf6SR2eWhm1z"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791751117.475737,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDTS",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjQBWhotCQGcWZZXXn2Xfo62a8CEPjJtmd_f4GZbFvnMG3m-r6IJOFxWkl9FKYCQGGSsDixqEAA"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791751117.475881,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDTS",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjQBWhotCQGcWZZXXn2Xfo62a8CEPjJtmd_f4GZbFvnMG3m-r6IJOFxWkl9FKYCQGGSsDixqEAA"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791751117.475933,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzWWlB1QrhGmNwR_sN2P3NvwgsyztwvFV5AuhrVoIrwfrA82kb-EO3PGUhf6CPyz-vIlMT0"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791751117.475984,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzU_ksdhq2EVjPVUl5jjOgPBXbkJMNe55vFaot5DB90MtZNqjZmD_lfJGpETYBY3PhSfSQ"
  },
  {
    "domain": ".youtube.com",
    "expirationDate": 1791751117.476029,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDCC",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzVuZ7PdUE26NcX-2RXvxDJFLj2PvRkZfrZPzNvYDyQ_Zy4hnZVLxEzPEOeFrT_F7XNVXQ"
  }
]