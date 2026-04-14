import asyncio
from app.database import async_session
from app.models.models import Course, Lecture
from sqlalchemy import select

async def main():
    async with async_session() as db:
        c_res = await db.execute(select(Course).where(Course.id == 'a1d2a391-b3d2-438d-bdb9-cb3ab6afe622'))
        course = c_res.scalar_one_or_none()
        print("Course:", course.title if course else None)
        
        if course:
            l_res = await db.execute(select(Lecture).where(Lecture.course_id == course.id))
            lectures = l_res.scalars().all()
            print("Lectures count:", len(lectures))
            for l in lectures:
                print("Lecture:", l.title)

asyncio.run(main())
