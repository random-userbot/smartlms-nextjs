"""
Smart LMS - Messaging Router
Teacher-Student messaging system with analytics context
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.models.models import (
    User, UserRole, Message, MessageCategory, Notification,
    NotificationType, Course, Enrollment, EnrollmentStatus,
    EngagementLog, QuizAttempt, Quiz, ICAPLog
)
from app.middleware.auth import get_current_user, require_teacher_or_admin

router = APIRouter(prefix="/api/messages", tags=["Messages"])


# ─── Schemas ─────────────────────────────────────────────

class MessageCreate(BaseModel):
    receiver_id: str
    subject: Optional[str] = None
    content: str = Field(..., min_length=1, max_length=5000)
    course_id: Optional[str] = None
    category: Optional[str] = "general"
    parent_id: Optional[str] = None
    analytics_context: Optional[dict] = None


class BulkMessageCreate(BaseModel):
    student_ids: List[str]
    subject: Optional[str] = None
    content: str = Field(..., min_length=1, max_length=5000)
    course_id: Optional[str] = None
    category: Optional[str] = "alert"


class MessageResponse(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    sender_role: str
    receiver_id: str
    receiver_name: str
    subject: Optional[str]
    content: str
    category: str
    course_id: Optional[str]
    course_title: Optional[str] = None
    is_read: bool
    parent_id: Optional[str]
    analytics_context: Optional[dict]
    created_at: str
    replies: list = []


class ConversationPreview(BaseModel):
    other_user_id: str
    other_user_name: str
    other_user_role: str
    last_message: str
    last_message_at: str
    unread_count: int
    course_id: Optional[str] = None
    course_title: Optional[str] = None


class StudentAnalyticsForMessage(BaseModel):
    student_id: str
    student_name: str
    email: str
    avg_engagement: Optional[float] = None
    avg_boredom: Optional[float] = None
    avg_confusion: Optional[float] = None
    latest_icap: Optional[str] = None
    quiz_avg: Optional[float] = None
    total_sessions: int = 0
    risk_level: str = "normal"  # low, normal, at_risk, critical


# ─── Send Message ────────────────────────────────────────

@router.post("", status_code=201)
async def send_message(
    msg: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to another user (teacher→student or student→teacher)"""
    # Verify receiver exists
    receiver_result = await db.execute(select(User).where(User.id == msg.receiver_id))
    receiver = receiver_result.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    # Cannot message yourself
    if msg.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    # Parse category
    try:
        category = MessageCategory(msg.category)
    except ValueError:
        category = MessageCategory.GENERAL

    message = Message(
        sender_id=current_user.id,
        receiver_id=msg.receiver_id,
        subject=msg.subject,
        content=msg.content,
        course_id=msg.course_id,
        category=category,
        parent_id=msg.parent_id,
        analytics_context=msg.analytics_context,
    )
    db.add(message)

    # Create notification for receiver
    notif_title = f"New message from {current_user.full_name}"
    if category == MessageCategory.ADVICE:
        notif_title = f"Advice from {current_user.full_name}"
    elif category == MessageCategory.ENCOURAGEMENT:
        notif_title = f"Encouragement from {current_user.full_name}"
    elif category == MessageCategory.ENGAGEMENT_ALERT:
        notif_title = f"Engagement alert from {current_user.full_name}"

    notification = Notification(
        user_id=msg.receiver_id,
        sender_id=current_user.id,
        type=NotificationType.PRIVATE_MESSAGE,
        title=notif_title,
        message=msg.content[:200] + ("..." if len(msg.content) > 200 else ""),
        extra_data={
            "message_id": message.id,
            "course_id": msg.course_id,
            "category": msg.category,
        },
    )
    db.add(notification)

    await db.commit()
    await db.refresh(message)

    return {
        "id": message.id,
        "status": "sent",
        "receiver_name": receiver.full_name,
        "created_at": message.created_at.isoformat(),
    }


# ─── Get Conversations ──────────────────────────────────

@router.get("/conversations")
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of conversations with preview of last message"""
    # Get all messages involving this user
    result = await db.execute(
        select(Message).where(
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        ).order_by(desc(Message.created_at))
    )
    messages = result.scalars().all()

    # Group by the other user
    conversations = {}
    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if other_id not in conversations:
            conversations[other_id] = {
                "messages": [],
                "unread": 0,
                "last_msg": msg,
                "course_id": msg.course_id,
            }
        conversations[other_id]["messages"].append(msg)
        if msg.receiver_id == current_user.id and not msg.is_read:
            conversations[other_id]["unread"] += 1

    # Fetch user details
    other_user_ids = list(conversations.keys())
    if not other_user_ids:
        return []

    users_result = await db.execute(
        select(User).where(User.id.in_(other_user_ids))
    )
    users_map = {u.id: u for u in users_result.scalars().all()}

    # Fetch course titles
    course_ids = [c["course_id"] for c in conversations.values() if c["course_id"]]
    courses_map = {}
    if course_ids:
        courses_result = await db.execute(
            select(Course).where(Course.id.in_(course_ids))
        )
        courses_map = {c.id: c.title for c in courses_result.scalars().all()}

    result_list = []
    for other_id, conv_data in conversations.items():
        user = users_map.get(other_id)
        if not user:
            continue
        last = conv_data["last_msg"]
        result_list.append({
            "other_user_id": other_id,
            "other_user_name": user.full_name,
            "other_user_role": user.role.value,
            "last_message": last.content[:100] + ("..." if len(last.content) > 100 else ""),
            "last_message_at": last.created_at.isoformat(),
            "unread_count": conv_data["unread"],
            "course_id": conv_data["course_id"],
            "course_title": courses_map.get(conv_data["course_id"]),
        })

    # Sort by last message time
    result_list.sort(key=lambda x: x["last_message_at"], reverse=True)
    return result_list


# ─── Get Messages with User ─────────────────────────────

@router.get("/with/{user_id}")
async def get_messages_with_user(
    user_id: str,
    course_id: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all messages between current user and specified user"""
    conditions = [
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == user_id),
            and_(Message.sender_id == user_id, Message.receiver_id == current_user.id),
        )
    ]
    if course_id:
        conditions.append(Message.course_id == course_id)

    result = await db.execute(
        select(Message).where(*conditions)
        .order_by(desc(Message.created_at))
        .limit(limit).offset(offset)
    )
    messages = result.scalars().all()

    # Mark received messages as read
    for msg in messages:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    await db.commit()

    # Get user names
    other_result = await db.execute(select(User).where(User.id == user_id))
    other_user = other_result.scalar_one_or_none()

    return {
        "other_user": {
            "id": other_user.id if other_user else user_id,
            "name": other_user.full_name if other_user else "Unknown",
            "role": other_user.role.value if other_user else "unknown",
        },
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": current_user.full_name if m.sender_id == current_user.id else (other_user.full_name if other_user else "Unknown"),
                "receiver_id": m.receiver_id,
                "content": m.content,
                "subject": m.subject,
                "category": m.category.value if m.category else "general",
                "course_id": m.course_id,
                "is_read": m.is_read,
                "parent_id": m.parent_id,
                "analytics_context": m.analytics_context,
                "created_at": m.created_at.isoformat(),
            }
            for m in reversed(messages)  # Chronological order
        ],
    }


# ─── Unread Count ────────────────────────────────────────

@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total unread message count"""
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.receiver_id == current_user.id,
            Message.is_read == False,
        )
    )
    return {"unread_count": result.scalar() or 0}


@router.get("/search", response_model=List[MessageResponse])
async def search_messages(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search messages by content for the current user"""

    result = await db.execute(
        select(Message).where(
            and_(
                or_(
                    Message.sender_id == current_user.id,
                    Message.receiver_id == current_user.id
                ),
                Message.content.ilike(f"%{q}%")
            )
        ).order_by(desc(Message.created_at)).limit(50)
    )
    
    messages = result.scalars().all()
    if not messages:
        return []

    user_ids = {m.sender_id for m in messages} | {m.receiver_id for m in messages}
    course_ids = {m.course_id for m in messages if m.course_id}

    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    courses_map = {}
    if course_ids:
        courses_result = await db.execute(select(Course.id, Course.title).where(Course.id.in_(course_ids)))
        courses_map = {cid: title for cid, title in courses_result.all()}
    
    responses = []
    for m in messages:
        sender = users_map.get(m.sender_id)
        receiver = users_map.get(m.receiver_id)
        if not sender or not receiver:
            continue
        course_title = courses_map.get(m.course_id)
            
        responses.append(MessageResponse(
            id=m.id,
            sender_id=m.sender_id,
            sender_name=sender.full_name,
            sender_role=sender.role.value,
            receiver_id=m.receiver_id,
            receiver_name=receiver.full_name,
            subject=m.subject,
            content=m.content,
            category=m.category.value,
            course_id=m.course_id,
            course_title=course_title,
            is_read=m.is_read,
            parent_id=m.parent_id,
            analytics_context=m.analytics_context,
            created_at=m.created_at.isoformat(),
        ))
    
    return responses


# ─── Mark Message Read ───────────────────────────────────

@router.put("/{message_id}/read")
async def mark_message_read(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a specific message as read"""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.receiver_id == current_user.id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.is_read = True
    await db.commit()
    return {"status": "read"}


# ─── Teacher: Get Student Analytics for Messaging ────────

@router.get("/student-analytics/{student_id}")
async def get_student_analytics_for_messaging(
    student_id: str,
    course_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Get student analytics context for the teacher to compose a message.
    Shows engagement, ICAP, quiz performance, and risk level."""
    
    # Verify student exists
    student_result = await db.execute(select(User).where(User.id == student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Engagement logs (optionally filtered by course)
    eng_query = select(EngagementLog).where(EngagementLog.student_id == student_id)
    if course_id:
        from sqlalchemy import exists
        eng_query = eng_query.where(
            EngagementLog.lecture_id.in_(
                select(EngagementLog.lecture_id).join(
                    Course, Course.id == course_id
                )
            )
        )
    eng_result = await db.execute(eng_query.order_by(desc(EngagementLog.started_at)).limit(50))
    eng_logs = eng_result.scalars().all()

    avg_engagement = None
    avg_boredom = None
    avg_confusion = None
    if eng_logs:
        scores = [l.engagement_score for l in eng_logs if l.engagement_score is not None]
        boredom = [l.boredom_score for l in eng_logs if l.boredom_score is not None]
        confusion = [l.confusion_score for l in eng_logs if l.confusion_score is not None]
        avg_engagement = round(sum(scores) / max(len(scores), 1), 1) if scores else None
        avg_boredom = round(sum(boredom) / max(len(boredom), 1), 1) if boredom else None
        avg_confusion = round(sum(confusion) / max(len(confusion), 1), 1) if confusion else None

    # Latest ICAP
    icap_result = await db.execute(
        select(ICAPLog).where(ICAPLog.student_id == student_id)
        .order_by(desc(ICAPLog.created_at)).limit(1)
    )
    latest_icap = icap_result.scalar_one_or_none()

    # Quiz performance
    quiz_result = await db.execute(
        select(QuizAttempt).where(QuizAttempt.student_id == student_id)
    )
    attempts = quiz_result.scalars().all()
    quiz_avg = None
    if attempts:
        quiz_scores = [(a.score / a.max_score * 100) for a in attempts if a.max_score]
        quiz_avg = round(sum(quiz_scores) / max(len(quiz_scores), 1), 1) if quiz_scores else None

    # Risk assessment
    risk_level = "normal"
    if avg_engagement is not None:
        if avg_engagement < 30:
            risk_level = "critical"
        elif avg_engagement < 50:
            risk_level = "at_risk"
        elif avg_engagement > 75:
            risk_level = "low"

    # Message templates based on context
    templates = []
    if risk_level == "critical":
        templates.append({
            "category": "engagement_alert",
            "subject": "Let's Improve Your Engagement",
            "content": f"Hi {student.full_name}, I noticed your engagement has been low recently. I want to help you succeed in this course. What challenges are you facing? Let's work together to find a solution."
        })
    if avg_confusion and avg_confusion > 60:
        templates.append({
            "category": "advice",
            "subject": "Need Help with Course Material?",
            "content": f"Hi {student.full_name}, I noticed you might be finding some parts of the material challenging. Please don't hesitate to ask questions during lectures or use the AI tutor. I'm here to help!"
        })
    if avg_boredom and avg_boredom > 60:
        templates.append({
            "category": "advice",
            "subject": "Feedback on Course Content",
            "content": f"Hi {student.full_name}, I'd love to hear your thoughts on the course content. Is there anything you'd like to see covered differently or any topics you're particularly interested in?"
        })
    if quiz_avg and quiz_avg > 85:
        templates.append({
            "category": "encouragement",
            "subject": "Great Work on Quizzes!",
            "content": f"Hi {student.full_name}, I wanted to recognize your excellent quiz performance! Keep up the great work. Consider helping your peers as well - teaching others is the best way to solidify your knowledge."
        })
    if not templates:
        templates.append({
            "category": "general",
            "subject": "Check-in",
            "content": f"Hi {student.full_name}, I wanted to check in on your progress in the course. How are you finding the material? Let me know if there's anything I can help with."
        })

    return {
        "student_id": student.id,
        "student_name": student.full_name,
        "email": student.email,
        "avg_engagement": avg_engagement,
        "avg_boredom": avg_boredom,
        "avg_confusion": avg_confusion,
        "latest_icap": latest_icap.classification.value if latest_icap else None,
        "quiz_avg": quiz_avg,
        "total_sessions": len(eng_logs),
        "risk_level": risk_level,
        "message_templates": templates,
    }


# ─── Teacher: Bulk Message Students ─────────────────────

@router.post("/bulk-send")
async def bulk_send_messages(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Send a message to multiple students at once.
    Body: { student_ids: [], subject, content, course_id, category }"""
    student_ids = data.get("student_ids", [])
    if not student_ids:
        raise HTTPException(status_code=400, detail="No students specified")

    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content required")

    try:
        category = MessageCategory(data.get("category", "general"))
    except ValueError:
        category = MessageCategory.GENERAL

    sent_count = 0
    for sid in student_ids:
        msg = Message(
            sender_id=current_user.id,
            receiver_id=sid,
            subject=data.get("subject"),
            content=content,
            course_id=data.get("course_id"),
            category=category,
        )
        db.add(msg)

        notification = Notification(
            user_id=sid,
            sender_id=current_user.id,
            type=NotificationType.PRIVATE_MESSAGE,
            title=f"Message from {current_user.full_name}",
            message=content[:200] + ("..." if len(content) > 200 else ""),
            extra_data={"message_id": msg.id, "course_id": data.get("course_id")},
        )
        db.add(notification)
        sent_count += 1

    await db.commit()
    return {"status": "sent", "sent_count": sent_count}


# ─── Teacher: Get At-Risk Students ──────────────────────

@router.get("/at-risk-students/{course_id}")
async def get_at_risk_students(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Get students with low engagement who may need teacher outreach"""
    from sqlalchemy.orm import aliased

    # Get enrolled students
    enrollment_result = await db.execute(
        select(Enrollment, User).join(User, Enrollment.student_id == User.id).where(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
    )
    students = enrollment_result.all()

    from app.models.models import Lecture
    # Get course lecture IDs
    lecture_result = await db.execute(
        select(Lecture.id).where(Lecture.course_id == course_id)
    )
    lecture_ids = [l[0] for l in lecture_result.all()]

    at_risk = []
    for enrollment, student in students:
        # Get engagement data for this student in this course
        eng_result = await db.execute(
            select(EngagementLog).where(
                EngagementLog.student_id == student.id,
                EngagementLog.lecture_id.in_(lecture_ids) if lecture_ids else EngagementLog.student_id == student.id,
            ).order_by(desc(EngagementLog.started_at)).limit(20)
        )
        logs = eng_result.scalars().all()

        avg_eng = 0
        avg_boredom = 0
        if logs:
            scores = [l.engagement_score for l in logs if l.engagement_score is not None]
            boredom = [l.boredom_score for l in logs if l.boredom_score is not None]
            avg_eng = round(sum(scores) / max(len(scores), 1), 1) if scores else 0
            avg_boredom = round(sum(boredom) / max(len(boredom), 1), 1) if boredom else 0

        risk = "normal"
        if avg_eng < 30:
            risk = "critical"
        elif avg_eng < 50:
            risk = "at_risk"

        # Check if teacher already messaged recently
        recent_msg = await db.execute(
            select(Message).where(
                Message.sender_id == current_user.id,
                Message.receiver_id == student.id,
                Message.course_id == course_id,
            ).order_by(desc(Message.created_at)).limit(1)
        )
        last_msg = recent_msg.scalar_one_or_none()

        at_risk.append({
            "student_id": student.id,
            "student_name": student.full_name,
            "email": student.email,
            "avg_engagement": avg_eng,
            "avg_boredom": avg_boredom,
            "total_sessions": len(logs),
            "progress": enrollment.progress,
            "risk_level": risk,
            "last_messaged": last_msg.created_at.isoformat() if last_msg else None,
        })

    # Sort by risk (critical first)
    risk_order = {"critical": 0, "at_risk": 1, "normal": 2, "low": 3}
    at_risk.sort(key=lambda x: (risk_order.get(x["risk_level"], 3), x["avg_engagement"]))

    return at_risk


# ─── Delete Message ──────────────────────────────────────

@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific message. Only sender or receiver can delete."""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            or_(
                Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id,
            )
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found or unauthorized")
    
    await db.delete(msg)
    await db.commit()
    return {"status": "deleted"}


# ─── Delete Conversation ─────────────────────────────────

@router.delete("/conversation/{other_user_id}")
async def delete_conversation(
    other_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all messages between current user and another user"""
    from sqlalchemy import delete
    
    q = delete(Message).where(
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == other_user_id),
            and_(Message.sender_id == other_user_id, Message.receiver_id == current_user.id),
        )
    )
    await db.execute(q)
    await db.commit()
    return {"status": "conversation_purged"}


@router.post("/bulk-send", status_code=201)
async def bulk_send_message(
    payload: BulkMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Send a message to multiple students simultaneously.
    Used for Risk Matrix alerts.
    """
    sent_count = 0
    errors = []
    
    # 1. Fetch students to verify they exist and are students
    student_res = await db.execute(select(User).where(User.id.in_(payload.student_ids)))
    students = student_res.scalars().all()
    
    found_ids = [s.id for s in students]
    missing_ids = [sid for sid in payload.student_ids if sid not in found_ids]
    
    if missing_ids:
        errors.append(f"Students not found: {missing_ids}")

    # 2. Bulk create messages
    for student in students:
        new_msg = Message(
            id=str(uuid4()),
            sender_id=current_user.id,
            receiver_id=student.id,
            subject=payload.subject or f"Focus Alert: {payload.course_id or 'General'}",
            content=payload.content,
            category=MessageCategory(payload.category),
            course_id=payload.course_id,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(new_msg)
        
        # 3. Create Notification
        notif = Notification(
            id=str(uuid4()),
            user_id=student.id,
            type=NotificationType.MESSAGE,
            title="New Instructor Alert",
            content=f"You received a priority message from {current_user.full_name}",
            link=f"/messages?other_user_id={current_user.id}",
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.add(notif)
        sent_count += 1

    await db.commit()
    
    return {
        "status": "success",
        "sent_count": sent_count,
        "errors": errors if errors else None
    }
