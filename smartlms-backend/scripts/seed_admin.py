import asyncio
import uuid
from datetime import datetime
import bcrypt
from sqlalchemy import select
from app.database import async_session, engine, Base
from app.models.models import User, UserRole

async def seed_admin():
    print("\n" + "="*50)
    print("  SmartLMS Admin Seeding Initialized")
    print("="*50)
    
    # 1. Credentials
    ADMIN_EMAIL = "admin@smartlms.online"
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "SmartLMS2026!" # User should change this after first login
    
    # 2. Hash Password
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), salt).decode('utf-8')
    
    async with async_session() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).where((User.email == ADMIN_EMAIL) | (User.username == ADMIN_USERNAME))
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"[INFO] Admin user already exists: {existing_user.username} ({existing_user.email})")
            if existing_user.role != UserRole.ADMIN:
                print(f"[FIX] Upgrading user {existing_user.username} to ADMIN role...")
                existing_user.role = UserRole.ADMIN
                await session.commit()
                print("[OK] User promoted to Admin.")
            return

        # Create Admin
        new_admin = User(
            id=str(uuid.uuid4()),
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            full_name="System Administrator",
            password_hash=password_hash,
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        session.add(new_admin)
        await session.commit()
        
        print(f"[SUCCESS] Admin User Created!")
        print(f"  Email:    {ADMIN_EMAIL}")
        print(f"  Username: {ADMIN_USERNAME}")
        print(f"  Password: {ADMIN_PASSWORD}")
        print("\n[IMPORTANT] Re-deploy or restart the backend to ensure the DB sync picks up the changes.")

if __name__ == "__main__":
    asyncio.run(seed_admin())
