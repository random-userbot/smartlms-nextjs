"""Smart LMS - Gamification Router"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.models import User, Gamification
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/gamification", tags=["Gamification"])

BADGES = {
    "first_lecture": {"name": "First Steps", "description": "Watched your first lecture", "icon": "play-circle"},
    "quiz_master": {"name": "Quiz Master", "description": "Scored 90%+ on a quiz", "icon": "award"},
    "perfect_score": {"name": "Perfectionist", "description": "Got 100% on a quiz", "icon": "star"},
    "streak_3": {"name": "On Fire", "description": "3-day login streak", "icon": "flame"},
    "streak_7": {"name": "Dedicated", "description": "7-day login streak", "icon": "zap"},
    "engaged": {"name": "Fully Engaged", "description": "80%+ engagement score", "icon": "target"},
    "note_taker": {"name": "Note Taker", "description": "Detected taking notes during lecture", "icon": "pencil"},
    "feedback_giver": {"name": "Voice Heard", "description": "Submitted 5 feedbacks", "icon": "message-circle"},
    "early_bird": {"name": "Early Bird", "description": "Completed lecture within 24h of upload", "icon": "sunrise"},
    "top_10": {"name": "Leaderboard Star", "description": "Reached top 10 on leaderboard", "icon": "trophy"},
}


@router.get("/profile")
async def get_gamification_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Gamification).where(Gamification.user_id == current_user.id)
    )
    gam = result.scalar_one_or_none()

    if not gam:
        gam = Gamification(user_id=current_user.id)
        db.add(gam)
        await db.commit()
        await db.refresh(gam)

    return {
        "user_id": current_user.id,
        "points": gam.points,
        "level": gam.level,
        "badges": gam.badges or [],
        "streaks": gam.streaks or {},
        "available_badges": BADGES,
    }


@router.post("/award-points")
async def award_points(
    activity: str,
    amount: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Gamification).where(Gamification.user_id == current_user.id)
    )
    gam = result.scalar_one_or_none()
    if not gam:
        gam = Gamification(user_id=current_user.id)
        db.add(gam)

    gam.points = (gam.points or 0) + amount
    gam.level = 1 + (gam.points // 100)  # Level up every 100 points
    await db.commit()

    return {"points": gam.points, "level": gam.level}


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Gamification, User).join(User, Gamification.user_id == User.id)
        .order_by(Gamification.points.desc()).limit(limit)
    )
    rows = result.all()

    return [
        {
            "rank": i + 1,
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "points": gam.points,
            "level": gam.level,
            "badges_count": len(gam.badges or []),
        }
        for i, (gam, user) in enumerate(rows)
    ]
