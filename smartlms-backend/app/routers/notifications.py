"""
Smart LMS - Notifications Router
In-app notifications and teacher announcements
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.models import User, UserRole, Notification, NotificationType, Enrollment
from app.middleware.auth import get_current_user, require_teacher_or_admin
from app.services.debug_logger import debug_logger

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationCreate(BaseModel):
    user_id: Optional[str] = None  # None = broadcast to course students
    course_id: Optional[str] = None
    title: str
    message: str
    type: str = "announcement"


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    sender_id: Optional[str]
    type: str
    title: str
    message: Optional[str]
    extra_data: Optional[dict]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[NotificationResponse])
async def get_my_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's notifications"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        query = query.where(Notification.is_read == False)
    result = await db.execute(query.order_by(Notification.created_at.desc()).limit(limit))
    return [NotificationResponse.model_validate(n) for n in result.scalars().all()]


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of unread notifications"""
    result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    return {"count": result.scalar() or 0}


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark notification as read"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await db.commit()
    return {"message": "Marked as read"}


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read"""
    await db.execute(
        update(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        ).values(is_read=True)
    )
    await db.commit()
    return {"message": "All marked as read"}


@router.post("/announce", status_code=201)
async def send_announcement(
    request: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Send announcement to a student or all students in a course"""
    if request.user_id:
        # Private message to specific student
        notification = Notification(
            user_id=request.user_id,
            sender_id=current_user.id,
            type=NotificationType.PRIVATE_MESSAGE,
            title=request.title,
            message=request.message,
            extra_data={"course_id": request.course_id} if request.course_id else None,
        )
        db.add(notification)
    elif request.course_id:
        # Broadcast to all enrolled students
        result = await db.execute(
            select(Enrollment.student_id).where(Enrollment.course_id == request.course_id)
        )
        student_ids = [row[0] for row in result.all()]

        for sid in student_ids:
            notification = Notification(
                user_id=sid,
                sender_id=current_user.id,
                type=NotificationType.ANNOUNCEMENT,
                title=request.title,
                message=request.message,
                extra_data={"course_id": request.course_id},
            )
            db.add(notification)
    else:
        raise HTTPException(status_code=400, detail="Specify user_id or course_id")

    await db.commit()

    debug_logger.log("activity", f"Announcement sent: {request.title}",
                     user_id=current_user.id)

    return {"message": "Announcement sent"}
