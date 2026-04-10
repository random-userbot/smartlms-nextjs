
import asyncio
import logging
from sqlalchemy import text
from app.database import engine
from app.models.models import Base, User, UserRole
from app.services.auth_service import hash_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_reset")

async def hard_reset_production_db():
    """
    NUCLEAR OPTION: Drops all tables and recreates them.
    Also seeds the default admin user.
    """
    print("\n" + "!" * 60)
    print("  WARNING: YOU ARE ABOUT TO WIPE THE PRODUCTION DATABASE.")
    print("  ALL DATA WILL BE PERMANENTLY DELETED.")
    print("!" * 60 + "\n")
    
    confirm = input("Are you absolutely sure? Type 'NUKE' to proceed: ")
    if confirm != "NUKE":
        print("Operation cancelled.")
        return

    async with engine.begin() as conn:
        print("[1/3] Dropping all tables (Cleaning RDS Schema)...")
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
        print("[OK] Database wiped.")

        print("[2/3] Recreating tables from latest models...")
        await conn.run_sync(Base.metadata.create_all)
        print("[OK] Schema recreated.")

    print("[3/3] Seeding default admin user...")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
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
    print("[OK] Admin user created: admin@smartlms.com / admin123")
    
    print("\n" + "=" * 60)
    print("  HARD RESET COMPLETE. Production is now clean & synchronized.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(hard_reset_production_db())
