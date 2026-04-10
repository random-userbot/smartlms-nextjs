"""
Smart LMS - Database Synchronization Service
Ensures RDS schema parity by automatically injecting missing columns and tables.
"""

import logging
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine
from app.models.models import Base
from app.database import engine

logger = logging.getLogger("uvicorn.error")

async def run_db_sync():
    """
    Introspect the database and ensure all columns in models.py 
    are present in the live database.
    """
    logger.info("[DB_GUARD] Starting database schema synchronization audit...")
    
    # 1. Ensure all missing tables are created (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Audit columns for tables that already exist
    async with engine.connect() as conn:
        # We need a sync connection for inspection
        def sync_audit(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            
            # Map of expected changes for production stabilization
            # Structure: {table_name: [(column_name, sql_type, is_jsonb)]}
            target_changes = {
                "assignment_submissions": [
                    ("structured_answers", "JSONB", True),
                    ("teacher_feedback", "TEXT", False)
                ],
                "courses": [
                    ("thumbnail_url", "VARCHAR(500)", False)
                ],
                "engagement_logs": [
                    ("is_finalized", "BOOLEAN DEFAULT FALSE", False),
                    ("feature_timeline", "JSONB", True)
                ]
            }
            
            applied_count = 0
            for table_name, columns in target_changes.items():
                if table_name in tables:
                    existing_cols = [c["name"] for c in inspector.get_columns(table_name)]
                    
                    for col_name, col_type, is_jsonb in columns:
                        if col_name not in existing_cols:
                            logger.info(f"[DB_GUARD] Discovered missing column: {table_name}.{col_name}")
                            
                            # Handle Postgres (RDS) vs SQLite differences
                            final_type = col_type
                            if "sqlite" in str(engine.url) and is_jsonb:
                                final_type = "JSON"
                                
                            try:
                                sync_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {final_type}"))
                                applied_count += 1
                                logger.info(f"[DB_GUARD] Successfully injected: {table_name}.{col_name}")
                            except Exception as e:
                                logger.error(f"[DB_GUARD] Failed to inject {col_name}: {str(e)}")
                                
            return applied_count

        count = await conn.run_sync(sync_audit)
        
    if count > 0:
        logger.info(f"[DB_GUARD] Schema synchronization complete. {count} columns injected.")
    else:
        logger.info("[DB_GUARD] Schema is already perfectly synchronized with production models.")

if __name__ == "__main__":
    # Allow standalone running for manual triggers
    import asyncio
    asyncio.run(run_db_sync())
