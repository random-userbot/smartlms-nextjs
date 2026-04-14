import asyncio
from app.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.models import EngagementLog, TeachingScore, ICAPLog, Enrollment

async def main():
    async with AsyncSession(engine) as session:
        print("=== TELEMETRY SUMMARY ===")
        
        # Engagement Logs
        res = await session.execute(select(func.count(EngagementLog.id), func.avg(EngagementLog.engagement_score)))
        eng_count, eng_avg = res.first()
        print(f"Engagement Logs: {eng_count} records | Average Score: {eng_avg or 0:.2f}%")
        
        # Teaching Scores
        res = await session.execute(select(func.count(TeachingScore.id), func.avg(TeachingScore.overall_score)))
        ts_count, ts_avg = res.first()
        print(f"Teaching Scores: {ts_count} records | Average Score: {ts_avg or 0:.2f}%")
        
        # ICAP Logs
        res = await session.execute(select(func.count(ICAPLog.id)))
        icap_count = res.scalar()
        print(f"ICAP Logs: {icap_count} records")
        
        print("\n=== LATEST ENGAGEMENT ===")
        res = await session.execute(select(EngagementLog.session_id, EngagementLog.engagement_score, EngagementLog.status).order_by(EngagementLog.started_at.desc()).limit(3))
        for row in res.all():
            print(f"Session: {row.session_id} | Score: {row.engagement_score}% | Status: {row.status}")

if __name__ == "__main__":
    asyncio.run(main())
