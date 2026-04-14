"""
Smart LMS - Admin Router
User management, system analytics, moderation
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.models import (
    User, UserRole, Course, Lecture, Quiz, Enrollment, EngagementLog,
    QuizAttempt, Feedback, TeachingScore, ActivityLog
)
from app.middleware.auth import get_current_user, require_admin, require_role
from app.services.debug_logger import debug_logger
from app.services.youtube_service import youtube_service

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class YoutubeCookieUpdate(BaseModel):
    cookie_data: str


@router.post("/youtube/cookies")
async def update_youtube_cookies(
    request: YoutubeCookieUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.TEACHER))
):
    """Dynamically update YouTube cookies at runtime."""
    success = youtube_service.update_cookies(request.cookie_data)
    if success:
        return {"success": True, "message": "YouTube cookies updated successfully."}
    else:
        raise HTTPException(status_code=400, detail="Invalid cookie format.")


@router.get("/teachers")
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all teachers with their teaching scores"""
    result = await db.execute(
        select(User).where(User.role == UserRole.TEACHER)
    )
    teachers = result.scalars().all()
    teacher_ids = [teacher.id for teacher in teachers]

    latest_scores_by_teacher = {}
    course_counts_by_teacher = {}

    if teacher_ids:
        scores_result = await db.execute(
            select(TeachingScore)
            .where(TeachingScore.teacher_id.in_(teacher_ids))
            .order_by(TeachingScore.teacher_id, TeachingScore.calculated_at.desc())
        )
        for score in scores_result.scalars().all():
            if score.teacher_id not in latest_scores_by_teacher:
                latest_scores_by_teacher[score.teacher_id] = score

        course_count_result = await db.execute(
            select(Course.teacher_id, func.count(Course.id))
            .where(Course.teacher_id.in_(teacher_ids))
            .group_by(Course.teacher_id)
        )
        course_counts_by_teacher = {
            teacher_id: count for teacher_id, count in course_count_result.all()
        }

    response = []
    for teacher in teachers:
        latest_score = latest_scores_by_teacher.get(teacher.id)

        response.append({
            "id": teacher.id,
            "username": teacher.username,
            "full_name": teacher.full_name,
            "email": teacher.email,
            "is_active": teacher.is_active,
            "last_login": teacher.last_login.isoformat() if teacher.last_login else None,
            "course_count": int(course_counts_by_teacher.get(teacher.id, 0) or 0),
            "overall_teaching_score": latest_score.overall_score if latest_score else None,
            "score_breakdown": latest_score.shap_breakdown if latest_score else None,
        })

    return response


@router.get("/teacher/{teacher_id}")
async def get_teacher_detail(
    teacher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get detailed teacher analytics"""
    result = await db.execute(select(User).where(User.id == teacher_id))
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Get courses
    courses_result = await db.execute(
        select(Course).where(Course.teacher_id == teacher_id)
    )
    courses = courses_result.scalars().all()
    course_ids = [course.id for course in courses]

    latest_scores_by_course = {}
    student_counts_by_course = {}

    if course_ids:
        scores_result = await db.execute(
            select(TeachingScore)
            .where(TeachingScore.course_id.in_(course_ids))
            .order_by(TeachingScore.course_id, TeachingScore.calculated_at.desc())
        )
        for score in scores_result.scalars().all():
            if score.course_id not in latest_scores_by_course:
                latest_scores_by_course[score.course_id] = score

        student_count_result = await db.execute(
            select(Enrollment.course_id, func.count(Enrollment.id))
            .where(Enrollment.course_id.in_(course_ids))
            .group_by(Enrollment.course_id)
        )
        student_counts_by_course = {
            cid: count for cid, count in student_count_result.all()
        }

    course_data = []
    for course in courses:
        score = latest_scores_by_course.get(course.id)

        course_data.append({
            "id": course.id,
            "title": course.title,
            "student_count": int(student_counts_by_course.get(course.id, 0) or 0),
            "teaching_score": score.overall_score if score else None,
            "score_breakdown": score.shap_breakdown if score else None,
            "recommendations": score.recommendations if score else [],
        })

    return {
        "teacher": {
            "id": teacher.id,
            "full_name": teacher.full_name,
            "email": teacher.email,
            "is_active": teacher.is_active,
        },
        "courses": course_data,
        "overall_avg_score": round(
            sum(c["teaching_score"] or 0 for c in course_data) / max(len(course_data), 1), 1
        ),
    }


@router.get("/users")
async def list_all_users(
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all users with optional role filter"""
    query = select(User)
    if role:
        query = query.where(User.role == UserRole(role))
    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate/deactivate a user"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    await db.commit()

    debug_logger.log("activity",
                     f"User {'activated' if user.is_active else 'deactivated'}: {user.username}",
                     user_id=current_user.id)

    return {"message": f"User {'activated' if user.is_active else 'deactivated'}", "is_active": user.is_active}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete a user and all associated data"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    await db.delete(user)
    await db.commit()

    debug_logger.log("activity", f"User deleted: {user.username}",
                     user_id=current_user.id)

    return {"message": "User deleted"}


@router.delete("/courses/{course_id}")
async def admin_delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin: delete any course"""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    await db.delete(course)
    await db.commit()

    debug_logger.log("activity", f"Admin deleted course: {course.title}",
                     user_id=current_user.id)

    return {"message": "Course deleted"}


@router.get("/system-stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get system-wide statistics"""
    users_count = await db.execute(select(func.count()).select_from(User))
    students_count = await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.STUDENT)
    )
    teachers_count = await db.execute(
        select(func.count()).select_from(User).where(User.role == UserRole.TEACHER)
    )
    courses_count = await db.execute(select(func.count()).select_from(Course))
    engagement_count = await db.execute(select(func.count()).select_from(EngagementLog))

    return {
        "total_users": users_count.scalar() or 0,
        "students": students_count.scalar() or 0,
        "teachers": teachers_count.scalar() or 0,
        "courses": courses_count.scalar() or 0,
        "engagement_sessions": engagement_count.scalar() or 0,
    }


@router.get("/engagement-correlation")
async def get_engagement_correlation(
    course_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Correlate Predicted Engagement (average from logs) 
    vs Actual Performance (average quiz scores).
    """
    # Base query for students and their average engagement
    eng_query = select(
        EngagementLog.student_id,
        func.avg(EngagementLog.engagement_score).label("avg_engagement")
    ).group_by(EngagementLog.student_id)
    
    if course_id:
        # Filter by course (join with Lecture)
        eng_query = eng_query.join(Lecture, EngagementLog.lecture_id == Lecture.id).where(Lecture.course_id == course_id)
        
    eng_results = await db.execute(eng_query)
    eng_data = {row.student_id: row.avg_engagement for row in eng_results.all()}
    
    # Query for students and their average quiz scores
    quiz_query = select(
        QuizAttempt.student_id,
        func.avg(QuizAttempt.score / QuizAttempt.max_score).label("avg_quiz_score")
    ).where(QuizAttempt.max_score > 0).group_by(QuizAttempt.student_id)
    
    if course_id:
        quiz_query = quiz_query.join(QuizAttempt.quiz).where(Quiz.lecture_id != None).outerjoin(Lecture, Quiz.lecture_id == Lecture.id).where(Lecture.course_id == course_id)
        
    quiz_results = await db.execute(quiz_query)
    quiz_data = {row.student_id: (row.avg_quiz_score * 100) for row in quiz_results.all()}
    
    # Merge datasets
    correlation_points = []
    all_student_ids = set(eng_data.keys()) | set(quiz_data.keys())
    
    # Get student names for tooltips
    student_names = {}
    if all_student_ids:
        names_res = await db.execute(select(User.id, User.full_name).where(User.id.in_(list(all_student_ids))))
        student_names = {r.id: r.full_name for r in names_res.all()}
    
    for sid in all_student_ids:
        predicted = eng_data.get(sid)
        actual = quiz_data.get(sid)
        
        if predicted is not None and actual is not None:
            correlation_points.append({
                "student_id": sid,
                "student_name": student_names.get(sid, "Unknown Student"),
                "predicted_engagement": round(predicted, 2),
                "actual_performance": round(actual, 2),
                "delta": round(actual - predicted, 2)
            })
            
    return {
        "course_id": course_id,
        "data_points": correlation_points,
        "sample_size": len(correlation_points),
        "avg_delta": round(sum(p["delta"] for p in correlation_points) / max(len(correlation_points), 1), 2) if correlation_points else 0
    }


@router.get("/student/{student_id}/course/{course_id}/analytics")
async def get_admin_student_analytics(
    student_id: str,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Detailed forensic engagement summary for a student in a course"""
    # Verify student and course exist
    student_res = await db.execute(select(User).where(User.id == student_id))
    student = student_res.scalar_one_or_none()
    if not student: raise HTTPException(404, "Student not found")
    
    # Get all engagement logs for lectures in this course
    lectures_query = select(Lecture.id).where(Lecture.course_id == course_id)
    eng_res = await db.execute(
        select(EngagementLog)
        .where(EngagementLog.student_id == student_id)
        .where(EngagementLog.lecture_id.in_(lectures_query))
        .order_by(EngagementLog.started_at.desc())
    )
    engagement_logs = eng_res.scalars().all()
    
    # Get all ICAP activities
    activity_res = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == student_id)
        .where(ActivityLog.details["icap_level"].as_string() != None)
        .order_by(ActivityLog.created_at.desc())
    )
    icap_activities = activity_res.scalars().all()
    
    # Get quiz attempts
    quiz_res = await db.execute(
        select(QuizAttempt)
        .join(QuizAttempt.quiz)
        .outerjoin(Lecture, Quiz.lecture_id == Lecture.id)
        .where(QuizAttempt.student_id == student_id, Lecture.course_id == course_id)
        .order_by(QuizAttempt.completed_at.desc())
    )
    quiz_attempts = quiz_res.scalars().all()

    return {
        "student": {"id": student.id, "name": student.full_name},
        "engagement_summary": {
            "avg_score": round(sum(l.engagement_score for l in engagement_logs) / max(len(engagement_logs), 1), 2) if engagement_logs else 0,
            "sessions_count": len(engagement_logs)
        },
        "icap_evidence": [
            {
                "timestamp": a.created_at.isoformat(),
                "action": a.action,
                "level": a.details.get("icap_level"),
                "summary": a.details.get("evidence_summary")
            } for a in icap_activities
        ],
        "quiz_performance": [
            {
                "quiz_title": q.quiz.title,
                "score": q.score,
                "max": q.max_score,
                "integrity": q.integrity_score,
                "date": q.completed_at.isoformat() if q.completed_at else None
            } for q in quiz_attempts
        ]
    }

@router.get("/export-datasets")
async def export_neural_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Export all finalized high-fidelity engagement logs platform-wide.
    Returns a streamed JSON response to handle large telemetry sets.
    """
    from fastapi.responses import StreamingResponse
    import json

    async def generate_dataset():
        yield "[\n"
        
        stmt = (
            select(EngagementLog)
            .where(EngagementLog.is_finalized == True)
            .order_by(EngagementLog.started_at.desc())
        )
        
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        for i, log in enumerate(logs):
            item = {
                "id": log.id,
                "student_id": log.student_id,
                "lecture_id": log.lecture_id,
                "overall_score": log.overall_score,
                "icap_classification": log.icap_classification.value if log.icap_classification else None,
                "telemetry": log.feature_timeline or [],
                "started_at": log.started_at.isoformat() if log.started_at else None
            }
            
            comma = "," if i < len(logs) - 1 else ""
            yield json.dumps(item) + comma + "\n"
            
        yield "]"

    return StreamingResponse(
        generate_dataset(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=platform_neural_dataset.json"}
    )


# --- LIVE MATRIX DATABASE EXPLORER ---

@router.get("/db/tables")
async def get_db_tables(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all available tables in the RDS schema"""
    from sqlalchemy import inspect
    from app.database import engine
    
    def sync_get_tables(conn):
        inspector = inspect(conn)
        return inspector.get_table_names()
        
    async with engine.connect() as conn:
        tables = await conn.run_sync(sync_get_tables)
        
    return {"tables": sorted(tables)}


@router.get("/db/tables/{table_name}")
async def get_table_data(
    table_name: str,
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Fetch raw records from a specific table with pagination"""
    from sqlalchemy import text
    
    # 1. Validate table name exists (prevents SQL injection)
    from sqlalchemy import inspect
    from app.database import engine
    
    def sync_verify_table(conn):
        inspector = inspect(conn)
        return table_name in inspector.get_table_names()
        
    async with engine.connect() as conn:
        exists = await conn.run_sync(sync_verify_table)
        
    if not exists:
        raise HTTPException(status_code=404, detail="Table not found")

    # 2. Fetch data (Limited for safety)
    offset = (page - 1) * limit
    
    # Use raw SQL for flexibility across reflected tables
    # Note: table_name is verified against the schema above to prevent injection
    query = text(f"SELECT * FROM {table_name} LIMIT {limit} OFFSET {offset}")
    count_query = text(f"SELECT COUNT(*) FROM {table_name}")
    
    result = await db.execute(query)
    count_result = await db.execute(count_query)
    
    rows = [dict(row._mapping) for row in result.all()]
    total_count = count_result.scalar()
    
    # Format rows for JSON serialization
    import datetime
    for row in rows:
        for k, v in row.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                row[k] = v.isoformat()
            if isinstance(v, bytes):
                row[k] = "<Binary Data>"

    return {
        "table": table_name,
        "rows": rows,
        "total": total_count,
        "page": page,
        "limit": limit
    }
