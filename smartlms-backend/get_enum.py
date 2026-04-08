import asyncio
from sqlalchemy import text
from app.database import async_session

async def main():
    async with async_session() as session:
        res = await session.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'notificationtype'"))
        print(res.scalars().all())

if __name__ == "__main__":
    asyncio.run(main())
