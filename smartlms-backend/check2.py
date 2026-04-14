import asyncio
import sys
sys.path.insert(0, '.')
from sqlalchemy import select
from app.database import async_session
from app.models.models import EngagementLog

async def main():
    async with async_session() as db:
        res = await db.execute(select(EngagementLog.watch_duration).limit(10))
        print([r[0] for r in res])

asyncio.run(main())
