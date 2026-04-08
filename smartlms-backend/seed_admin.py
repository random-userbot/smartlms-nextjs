import asyncio
from app.database import async_session
from app.models.models import User, UserRole
from app.middleware.auth import get_password_hash
from sqlalchemy import select

async def seed_admin():
    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(select(User).where(User.email == "admin@smartlms.com"))
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("Creating default admin user...")
            admin = User(
                username="admin",
                email="admin@smartlms.com",
                full_name="System Administrator",
                hashed_password=get_password_hash("admin123"), # Default password
                role=UserRole.ADMIN,
                is_active=True
            )
            session.add(admin)
            await session.commit()
            print("Admin user created: admin@smartlms.com / admin123")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    asyncio.run(seed_admin())
