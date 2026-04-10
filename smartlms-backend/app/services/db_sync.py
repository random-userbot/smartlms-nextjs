"""
Smart LMS - Database Synchronization Service
Ensures RDS schema parity by automatically injecting missing columns and tables.
"""

import logging
from sqlalchemy import text, inspect
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncEngine
from app.models.models import Base
from app.database import engine
from app.models.models import User, UserRole
from app.services.auth_service import hash_password
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("uvicorn.error")

async def run_db_sync():
    """Wipe and/or synchronize the database schema."""
    async with engine.begin() as conn:
        # 1. Base creation
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Audit columns for tables that already exist
    async with engine.connect() as conn:
        # We need a sync connection for inspection
        def sync_audit(sync_conn):
            inspector = inspect(sync_conn)
            tables = inspector.get_table_names()
            logger.info(f"[DB_GUARD] Discovered {len(tables)} tables in default schema: {tables}")
            
            if not tables:
                logger.warning("[DB_GUARD] No tables found in default schema. Attempting 'public' schema explicitly.")
                tables = inspector.get_table_names(schema="public")
                logger.info(f"[DB_GUARD] Discovered {len(tables)} tables in 'public' schema.")

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
                    # Get list of existing column names and force to lowercase for comparison
                    columns_data = inspector.get_columns(table_name)
                    # If specific schema was used, we might need it here too
                    if not columns_data and table_name in inspector.get_table_names(schema="public"):
                        columns_data = inspector.get_columns(table_name, schema="public")
                        
                    existing_cols = [c["name"].lower() for c in columns_data]
                    logger.info(f"[DB_GUARD] Auditing {table_name}: Found {len(existing_cols)} columns.")
                    
                    for col_name, col_type, is_jsonb in columns:
                        # Normalize target name to lowercase
                        target_col_name = col_name.lower()
                        
                        if target_col_name not in existing_cols:
                            # 2.2 Raw SQL Fallback Check (Ultimate Truth for RDS)
                            try:
                                raw_check = sync_conn.execute(text(f"""
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = '{table_name}' 
                                    AND column_name = '{col_name}'
                                """))
                                if raw_check.scalar():
                                    logger.info(f"[DB_GUARD] Column {table_name}.{col_name} detected via raw SQL. Skipping injection.")
                                    continue
                            except:
                                pass

                            logger.info(f"[DB_GUARD] Discovered missing column (Confirmed): {table_name}.{col_name}")
                            
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

    # 3. Automatic Admin Bootstrapping
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        from sqlalchemy import select
        admin_check = await session.execute(select(User).where(User.email == "admin@smartlms.com"))
        if not admin_check.scalar_one_or_none():
            logger.info("[DB_GUARD] No admin detected. Bootstrapping default admin user...")
            admin_user = User(
                username="admin",
                email="admin@smartlms.com",
                full_name="System Administrator",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                is_active=True
            )
            session.add(admin_user)
            await session.commit()
            logger.info("[DB_GUARD] Admin seeded successfully: admin@smartlms.com / admin123")

if __name__ == "__main__":
    # Allow standalone running for manual triggers
    import asyncio
    asyncio.run(run_db_sync())
