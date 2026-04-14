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

