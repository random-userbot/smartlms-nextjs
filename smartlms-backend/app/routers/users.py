"""Smart LMS - Users Router: Profile, activity history, data export"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.models import User, ActivityLog, EngagementLog, Feedback, QuizAttempt, Gamification
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/activity-history")
async def get_activity_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ActivityLog).where(ActivityLog.user_id == current_user.id)
        .order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {"id": l.id, "action": l.action, "details": l.details, "created_at": l.created_at.isoformat()}
        for l in logs
    ]


@router.get("/engagement-history")
async def get_engagement_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EngagementLog).where(EngagementLog.student_id == current_user.id)
        .order_by(EngagementLog.started_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id, "lecture_id": l.lecture_id, "overall_score": l.overall_score,
            "engagement_score": l.engagement_score, "boredom_score": l.boredom_score,
            "icap": l.icap_classification.value if l.icap_classification else None,
            "shap": l.shap_explanations, "started_at": l.started_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/feedback-history")
async def get_feedback_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Feedback).where(Feedback.student_id == current_user.id)
        .order_by(Feedback.created_at.desc())
    )
    feedbacks = result.scalars().all()
    return [
        {
            "id": f.id, "lecture_id": f.lecture_id, "overall_rating": f.overall_rating,
            "text": f.text, "sentiment": f.sentiment, "created_at": f.created_at.isoformat(),
        }
        for f in feedbacks
    ]


@router.get("/export-data")
async def export_my_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all user data (GDPR compliance)"""
    eng_result = await db.execute(
        select(EngagementLog).where(EngagementLog.student_id == current_user.id)
    )
    quiz_result = await db.execute(
        select(QuizAttempt).where(QuizAttempt.student_id == current_user.id)
    )
    fb_result = await db.execute(
        select(Feedback).where(Feedback.student_id == current_user.id)
    )

    return {
        "user": {
            "id": current_user.id, "username": current_user.username,
            "email": current_user.email, "full_name": current_user.full_name,
            "role": current_user.role.value, "created_at": current_user.created_at.isoformat(),
        },
        "engagement_logs": [
            {"score": l.overall_score, "lecture_id": l.lecture_id, "date": l.started_at.isoformat()}
            for l in eng_result.scalars().all()
        ],
        "quiz_attempts": [
            {"quiz_id": a.quiz_id, "score": a.score, "max_score": a.max_score}
            for a in quiz_result.scalars().all()
        ],
        "feedbacks": [
            {"lecture_id": f.lecture_id, "rating": f.overall_rating, "text": f.text}
            for f in fb_result.scalars().all()
        ],
    }
