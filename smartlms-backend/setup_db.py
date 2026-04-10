"""
SmartLMS - Database Initialization Script
Generates all 17 tables on the fresh RDS instance.
"""
import asyncio
import sys
import os

# Ensure the app directory is in the path
sys.path.append(os.getcwd())

from app.database import create_tables

async def main():
    print("--- SmartLMS Database Initialization ---")
    print("Targeting: {}".format(os.getenv("DATABASE_URL", "NOT_FOUND")))
    
    try:
        await create_tables()
        print("\n[SUCCESS] All tables have been successfully generated.")
    except Exception as e:
        print("\n[ERROR] Initialization failed!")
        print(str(e))

if __name__ == "__main__":
    asyncio.run(main())
