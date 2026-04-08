import sqlite3
import os

db_path = 'smartlms.db'
if not os.path.exists(db_path):
    print("Database not found at", db_path)
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column(table, col, type_):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if col not in columns:
        print(f"Adding column '{col}' to {table} table...")
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {type_}")
            conn.commit()
            print(f"Successfully added '{col}'.")
        except Exception as e:
            print(f"Failed to add '{col}': {e}")

# Hardening Lectures
add_column("lectures", "transcript", "TEXT")
add_column("lectures", "summary", "TEXT")

# Hardening Engagement Logs
add_column("engagement_logs", "no_face_detected_count", "INTEGER DEFAULT 0")
add_column("engagement_logs", "attention_lapse_duration", "FLOAT DEFAULT 0.0")

conn.close()
print("Schema update complete.")
