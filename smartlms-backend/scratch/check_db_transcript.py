
import asyncio
import os
import sys

# Add app to path
sys.path.append(os.path.join(os.getcwd(), '.'))

from sqlalchemy import select
from app.database import async_session
from app.models.models import Lecture

async def check_transcript():
    lecture_id = "725396fa-dbfe-4d34-aeb7-11bd911c2668"
    async with async_session() as session:
        res = await session.execute(select(Lecture).where(Lecture.id == lecture_id))
        lecture = res.scalar_one_or_none()
        if lecture:
            print(f"LECTURE: {lecture.title}")
            print(f"TRANSCRIPT EXISTS: {bool(lecture.transcript)}")
            if lecture.transcript:
                print(f"LENGTH: {len(lecture.transcript)}")
                print(f"PREVIEW: {lecture.transcript[:100]}...")
            else:
                print("TRANSCRIPT IS NULL IN DB")
        else:
            print("LECTURE NOT FOUND")

if __name__ == "__main__":
    asyncio.run(check_transcript())
