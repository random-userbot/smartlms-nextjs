import asyncio
from app.database import async_session
from app.models.models import User, UserRole
from sqlalchemy import select

async def main():
    async with async_session() as db:
        res = await db.execute(select(User).limit(1))
        user = res.scalar_one()
        print("Role:", repr(user.role))
        print("Type:", type(user.role))
        print("Is admin/teacher:", user.role in (UserRole.TEACHER, UserRole.ADMIN))

asyncio.run(main())
