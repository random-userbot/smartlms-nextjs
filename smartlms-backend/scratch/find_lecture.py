import asyncio
import os
from sqlalchemy import select
from app.database import async_session
from app.models.models import Lecture

async def find_lecture():
    async with async_session() as session:
        result = await session.execute(
            select(Lecture).where(Lecture.title.ilike("%Introduction to Data Science%"))
        )
        lecture = result.scalar_one_or_none()
        if lecture:
            print(f"ID: {lecture.id}")
            print(f"Course ID: {lecture.course_id}")
            print(f"Summary: {lecture.summary_transcript[:200]}...")
        else:
            print("Lecture not found")

if __name__ == "__main__":
    asyncio.run(find_lecture())
