import asyncio
from app.database import engine
from app.models.models import Lecture
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def main():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Lecture))
        lectures = result.scalars().all()
        for l in lectures:
            print(f"ID: {l.id}, Title: {l.title}, youtube_url: {l.youtube_url}, video_url: {l.video_url}")

asyncio.run(main())
