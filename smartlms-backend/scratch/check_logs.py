import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('smartlms-backend'))
from app.database import async_session
from sqlalchemy import select
from app.models.models import EngagementLog

async def main():
    async with async_session() as db:
        result = await db.execute(select(EngagementLog.id, EngagementLog.watch_duration).limit(10))
        for row in result:
            print(row)

if __name__ == '__main__':
    asyncio.run(main())
