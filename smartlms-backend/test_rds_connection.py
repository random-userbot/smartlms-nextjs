
import os
import socket
import psycopg2
from dotenv import load_dotenv

def test_connection():
    load_dotenv()
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        print("❌ DATABASE_URL_SYNC not found in .env")
        return

    # Parse URL
    # Format: postgresql://user:password@endpoint:port/db
    try:
        parts = url.replace("postgresql://", "").split("@")
        creds = parts[0].split(":")
        address = parts[1].split("/")
        endpoint_port = address[0].split(":")
        
        user = creds[0]
        password = creds[1]
        host = endpoint_port[0]
        port = int(endpoint_port[1])
        dbname = address[1]

        print(f"📡 Attempting to connect to: {host}:{port}")

        # 1. Socket Check
        try:
            with socket.create_connection((host, port), timeout=5):
                print("✅ Port 5432 is OPEN and reachable!")
        except Exception as e:
            print(f"❌ Could not reach port 5432. Error: {e}")
            print("💡 TIP: Check if your RDS has 'Public Access: Yes' and your Security Group allows your IP.")
            return

        # 2. Database Connection Check
        try:
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                connect_timeout=5
            )
            print("🎉 SUCCESS! Successfully connected to the database.")
            conn.close()
        except Exception as e:
            print(f"❌ Connection failed: {e}")

    except Exception as e:
        print(f"❌ Error parsing .env: {e}")

if __name__ == "__main__":
    test_connection()
