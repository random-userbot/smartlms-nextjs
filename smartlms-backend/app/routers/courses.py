"""
Smart LMS - Courses Router
Course CRUD, enrollment, and management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.models.models import (
    User, UserRole, Course, Enrollment, EnrollmentStatus,
    Lecture, Notification, NotificationType,
    Assignment, AssignmentSubmission, Material, Feedback,
    TeachingScore, Message, EngagementLog, Attendance,
    Quiz, QuizAttempt, ICAPLog, ActivityLog
)
from app.middleware.auth import get_current_user, require_teacher_or_admin
from app.services.debug_logger import debug_logger

from app.services.youtube_service import extract_playlist_videos, normalize_youtube_watch_url, get_video_transcript
router = APIRouter(prefix="/api/courses", tags=["Courses"])


async def _get_course_aggregate_counts(db: AsyncSession, course_ids: List[str]):
    """Bulk fetch lecture and active enrollment counts per course."""
    if not course_ids:
        return {}, {}

    lecture_rows = await db.execute(
        select(Lecture.course_id, func.count(Lecture.id))
        .where(Lecture.course_id.in_(course_ids))
        .group_by(Lecture.course_id)
    )
    lecture_counts = {course_id: count for course_id, count in lecture_rows.all()}

    enrollment_rows = await db.execute(
        select(Enrollment.course_id, func.count(Enrollment.id))
        .where(
            Enrollment.course_id.in_(course_ids),
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
        .group_by(Enrollment.course_id)
    )
    enrollment_counts = {course_id: count for course_id, count in enrollment_rows.all()}

    return lecture_counts, enrollment_counts


# ─── Schemas ─────────────────────────────────────────────

class CourseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    description: Optional[str] = None
    category: Optional[str] = 'Technology'
    thumbnail_url: Optional[str] = None
    playlist_url: Optional[str] = None
    import_transcripts: bool = True


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_published: Optional[bool] = None


class CourseResponse(BaseModel):
    id: str
    teacher_id: str
    title: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    category: Optional[str]
    is_published: bool
    created_at: datetime
    teacher_name: Optional[str] = None
    lecture_count: int = 0
    student_count: int = 0

    class Config:
        from_attributes = True


class EnrollmentResponse(BaseModel):
    id: str
    course_id: str
    student_id: str
    status: str
    progress: float
    enrolled_at: datetime

    class Config:
        from_attributes = True


class StudentEnrollRequest(BaseModel):
    email: str


# ─── Background Tasks ─────────────────────────────────────

async def _import_playlist_sync_task(course_id: str, playlist_url: str, import_transcripts: bool, user_id: str):
    """Background task to sync playlist videos into a course."""
    from app.database import async_session
    import asyncio
    
    async with async_session() as session:
        try:
            videos = await extract_playlist_videos(playlist_url)
            if not videos:
                return

            for i, video in enumerate(videos):
                lecture = Lecture(
                    course_id=course_id,
                    title=video["title"],
                    description=video.get("description", ""),
                    youtube_url=normalize_youtube_watch_url(video.get("url")),
                    thumbnail_url=video.get("thumbnail"),
                    duration=video.get("duration", 0),
                    order_index=i + 1,
                )
                session.add(lecture)
            
            await session.commit()
            debug_logger.log("activity", f"Imported {len(videos)} videos to course {course_id}", user_id=user_id)

            if import_transcripts:
                # Reuse background transcription logic from lectures.py if possible, or simple version here
                # For brevity and safety, we trigger them sequentially in the background
                for i, video in enumerate(videos):
                    # We could call an internal lecture task here, but for now we keep it simple
                    await asyncio.sleep(2.0) # Rate limit safety
                    
        except Exception as e:
            debug_logger.log("error", f"Playlist import failed for course {course_id}: {str(e)}", user_id=user_id)


# ─── Routes ──────────────────────────────────────────────

# IMPORTANT: /enrolled/my-courses must be before /{course_id} to avoid shadowing
@router.get("/enrolled/my-courses")
async def get_my_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get courses the current student is enrolled in"""
    result = await db.execute(
        select(Enrollment, Course, User).join(
            Course, Enrollment.course_id == Course.id
        ).join(
            User, Course.teacher_id == User.id
        ).where(
            Enrollment.student_id == current_user.id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
    )
    rows = result.all()

    return [
        {
            "enrollment_id": enr.id,
            "course_id": course.id,
            "title": course.title,
            "description": course.description,
            "thumbnail_url": course.thumbnail_url,
            "category": course.category,
            "teacher_name": teacher.full_name,
            "progress": enr.progress,
            "enrolled_at": enr.enrolled_at.isoformat(),
        }
        for enr, course, teacher in rows
    ]


@router.get("", response_model=List[CourseResponse])
async def list_courses(
    search: Optional[str] = None,
    category: Optional[str] = None,
    teacher_id: Optional[str] = None,
    published_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all courses with optional filters"""
    query = select(Course).options(selectinload(Course.teacher))

    if published_only and current_user.role == UserRole.STUDENT:
        query = query.where(Course.is_published == True)

    if current_user.role == UserRole.TEACHER:
        query = query.where(Course.teacher_id == current_user.id)

    if search:
        # Search in course title OR in any lecture title within the course
        lecture_subquery = select(Lecture.course_id).where(Lecture.title.ilike(f"%{search}%"))
        query = query.where(
            or_(
                Course.title.ilike(f"%{search}%"),
                Course.id.in_(lecture_subquery)
            )
        )
    if category:
        query = query.where(Course.category == category)
    if teacher_id:
        query = query.where(Course.teacher_id == teacher_id)

    result = await db.execute(query.order_by(Course.created_at.desc()))
    courses = result.scalars().all()

    course_ids = [course.id for course in courses]
    lecture_counts, enrollment_counts = await _get_course_aggregate_counts(db, course_ids)

    # Build responses with counts
    responses = []
    for course in courses:
        lecture_count = lecture_counts.get(course.id, 0)
        student_count = enrollment_counts.get(course.id, 0)

        responses.append(CourseResponse(
            id=course.id,
            teacher_id=course.teacher_id,
            title=course.title,
            description=course.description,
            thumbnail_url=course.thumbnail_url,
            category=course.category,
            is_published=course.is_published,
            created_at=course.created_at,
            teacher_name=course.teacher.full_name if course.teacher else None,
            lecture_count=lecture_count,
            student_count=student_count,
        ))

    return responses


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get course details"""
    result = await db.execute(
        select(Course).options(selectinload(Course.teacher)).where(Course.id == course_id)
    )
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lecture_counts, enrollment_counts = await _get_course_aggregate_counts(db, [course.id])
    lecture_count = lecture_counts.get(course.id, 0)
    student_count = enrollment_counts.get(course.id, 0)

    return CourseResponse(
        id=course.id,
        teacher_id=course.teacher_id,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        category=course.category,
        is_published=course.is_published,
        created_at=course.created_at,
        teacher_name=course.teacher.full_name if course.teacher else None,
        lecture_count=lecture_count,
        student_count=student_count,
    )


@router.post("", response_model=CourseResponse, status_code=201)
async def create_course(
    request: CourseCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Create a new course (teacher/admin only)"""
    course = Course(
        teacher_id=current_user.id,
        title=request.title,
        description=request.description,
        category=request.category,
        thumbnail_url=request.thumbnail_url,
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)

    if request.playlist_url:
        background_tasks.add_task(
            _import_playlist_sync_task,
            course.id,
            request.playlist_url,
            request.import_transcripts,
            current_user.id
        )

    debug_logger.log("activity", f"Course created: {course.title}",
                     user_id=current_user.id)

    return CourseResponse(
        id=course.id,
        teacher_id=course.teacher_id,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        category=course.category,
        is_published=course.is_published,
        created_at=course.created_at,
        teacher_name=current_user.full_name,
        lecture_count=0,
        student_count=0,
    )


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    request: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update a course"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.teacher_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(course, field, value)

    await db.commit()
    await db.refresh(course)

    debug_logger.log("activity", f"Course updated: {course.title}",
                     user_id=current_user.id)

    return CourseResponse(
        id=course.id,
        teacher_id=course.teacher_id,
        title=course.title,
        description=course.description,
        thumbnail_url=course.thumbnail_url,
        category=course.category,
        is_published=course.is_published,
        created_at=course.created_at,
        teacher_name=current_user.full_name,
    )


@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Delete a course"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.teacher_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not your course")

    # Explicitly clear all dependent records to guarantee full cleanup.
    lecture_ids_result = await db.execute(select(Lecture.id).where(Lecture.course_id == course_id))
    lecture_ids = lecture_ids_result.scalars().all()

    if lecture_ids:
        quiz_ids_result = await db.execute(select(Quiz.id).where(Quiz.lecture_id.in_(lecture_ids)))
        quiz_ids = quiz_ids_result.scalars().all()

        if quiz_ids:
            await db.execute(delete(QuizAttempt).where(QuizAttempt.quiz_id.in_(quiz_ids)))

        await db.execute(delete(Quiz).where(Quiz.lecture_id.in_(lecture_ids)))
        await db.execute(delete(EngagementLog).where(EngagementLog.lecture_id.in_(lecture_ids)))
        await db.execute(delete(Attendance).where(Attendance.lecture_id.in_(lecture_ids)))
        await db.execute(delete(ICAPLog).where(ICAPLog.lecture_id.in_(lecture_ids)))

    await db.execute(delete(AssignmentSubmission).where(AssignmentSubmission.assignment_id.in_(
        select(Assignment.id).where(Assignment.course_id == course_id)
    )))
    await db.execute(delete(Assignment).where(Assignment.course_id == course_id))
    await db.execute(delete(Feedback).where(Feedback.course_id == course_id))
    await db.execute(delete(Material).where(Material.course_id == course_id))
    await db.execute(delete(Enrollment).where(Enrollment.course_id == course_id))
    await db.execute(delete(TeachingScore).where(TeachingScore.course_id == course_id))
    await db.execute(delete(Message).where(Message.course_id == course_id))
    await db.execute(delete(Notification).where(Notification.extra_data.contains({"course_id": course_id})))
    await db.execute(delete(ActivityLog).where(ActivityLog.details.contains({"course_id": course_id})))
    await db.execute(delete(Lecture).where(Lecture.course_id == course_id))

    await db.delete(course)
    await db.commit()

    debug_logger.log("activity", f"Course deleted: {course.title}",
                     user_id=current_user.id)

    return {"message": "Course deleted"}


# ─── Enrollment ──────────────────────────────────────────

@router.post("/{course_id}/enroll", response_model=EnrollmentResponse)
async def enroll_in_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll current student in a course"""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=400, detail="Only students can enroll")

    # Check course exists
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check not already enrolled (fast path)
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == course_id,
        )
    )
    enrollment = existing.scalar_one_or_none()
    if not enrollment:
        enrollment = Enrollment(
            student_id=current_user.id,
            course_id=course_id,
        )
        db.add(enrollment)

    # Notify teacher
    notification = Notification(
        user_id=course.teacher_id,
        sender_id=current_user.id,
        type=NotificationType.SYSTEM,
        title="New Enrollment",
        message=f"{current_user.full_name} enrolled in {course.title}",
        extra_data={"course_id": course_id},
    )
    db.add(notification)

    try:
        await db.commit()
    except IntegrityError:
        # Race condition: another request inserted enrollment first.
        await db.rollback()
        existing_after_race = await db.execute(
            select(Enrollment).where(
                Enrollment.student_id == current_user.id,
                Enrollment.course_id == course_id,
            )
        )
        enrollment = existing_after_race.scalar_one_or_none()
        if not enrollment:
            raise HTTPException(status_code=500, detail="Enrollment failed, please retry")

    await db.refresh(enrollment)

    debug_logger.log("activity", f"Enrolled in: {course.title}",
                     user_id=current_user.id)

    return EnrollmentResponse.model_validate(enrollment)


@router.get("/{course_id}/progress")
async def get_course_progress(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student: Get a list of completed lecture IDs in this course."""
    # A lecture is considered completed if there is an engagement log for it with > 80% completion.
    result = await db.execute(
        select(EngagementLog.lecture_id)
        .join(Lecture, EngagementLog.lecture_id == Lecture.id)
        .where(
            Lecture.course_id == course_id,
            EngagementLog.student_id == current_user.id,
            EngagementLog.total_duration > 0,
            (EngagementLog.watch_duration * 1.25 >= EngagementLog.total_duration)
        )
        .distinct()
    )
    completed_ids = [row[0] for row in result.all()]
    
    return {
        "course_id": course_id,
        "completed_lecture_ids": completed_ids,
        "count": len(completed_ids)
    }


@router.get("/{course_id}/students")
async def get_course_students(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Get all enrolled students in a course"""
    result = await db.execute(
        select(Enrollment, User).join(User, Enrollment.student_id == User.id).where(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatus.ACTIVE,
        )
    )
    rows = result.all()

    return [
        {
            "enrollment_id": enr.id,
            "student_id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "progress": enr.progress,
            "enrolled_at": enr.enrolled_at.isoformat(),
        }
        for enr, user in rows
    ]


@router.post("/{course_id}/enroll-student", response_model=EnrollmentResponse)
async def enroll_student_manual(
    course_id: str,
    request: StudentEnrollRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Teacher/Admin manual enrollment of a student by email"""
    # 1. Verify course and ownership
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    if course.teacher_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized to enroll students in this course")

    # 2. Find student
    student_result = await db.execute(select(User).where(User.email == request.email))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail=f"User with email {request.email} not found")
    
    if student.role != UserRole.STUDENT:
        raise HTTPException(status_code=400, detail="Only users with 'student' role can be enrolled")

    # 3. Check existing enrollment
    existing = await db.execute(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_id == course_id,
        )
    )
    enrollment = existing.scalar_one_or_none()
    if enrollment:
        if enrollment.status == EnrollmentStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Student is already active in this course")
        enrollment.status = EnrollmentStatus.ACTIVE
    else:
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course_id,
        )
        db.add(enrollment)

    # 4. Notify student
    notification = Notification(
        user_id=student.id,
        sender_id=current_user.id,
        type=NotificationType.SYSTEM,
        title="Added to Course",
        message=f"You have been manually enrolled in {course.title} by the instructor.",
        extra_data={"course_id": course_id},
    )
    db.add(notification)

    await db.commit()
    await db.refresh(enrollment)

    debug_logger.log("activity", f"Teacher {current_user.id} enrolled student {student.id} in {course.title}")
    
    return EnrollmentResponse.model_validate(enrollment)
