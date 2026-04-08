"""Smart LMS - Assignments Router"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.models import (
    User, UserRole, Assignment, AssignmentSubmission, Course, 
    ActivityLog, ICAPLevel
)
from app.middleware.auth import get_current_user, require_teacher_or_admin
from app.services.icap_service import map_action_to_icap, get_action_evidence

router = APIRouter(prefix="/api/assignments", tags=["Assignments"])


class AssignmentCreate(BaseModel):
    course_id: str
    title: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    max_score: float = 100.0
    due_date: Optional[str] = None


class SubmissionCreate(BaseModel):
    assignment_id: str
    file_url: Optional[str] = None
    text: Optional[str] = None


class GradeSubmission(BaseModel):
    grade: float
    teacher_feedback: Optional[str] = None


@router.get("/course/{course_id}")
async def get_course_assignments(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Assignment).where(Assignment.course_id == course_id)
        .order_by(Assignment.created_at.desc())
    )
    assignments = result.scalars().all()
    return [
        {
            "id": a.id, "title": a.title, "description": a.description,
            "file_url": a.file_url, "max_score": a.max_score,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in assignments
    ]


@router.post("", status_code=201)
async def create_assignment(
    request: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    assignment = Assignment(
        course_id=request.course_id,
        title=request.title,
        description=request.description,
        file_url=request.file_url,
        max_score=request.max_score,
        due_date=datetime.fromisoformat(request.due_date) if request.due_date else None,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return {"id": assignment.id, "title": assignment.title, "message": "Assignment created"}


@router.post("/submit", status_code=201)
async def submit_assignment(
    request: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = AssignmentSubmission(
        assignment_id=request.assignment_id,
        student_id=current_user.id,
        file_url=request.file_url,
        text=request.text,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # Log as ICAP activity
    action = "assignment_submit"
    icap_level = map_action_to_icap(action)
    log = ActivityLog(
        user_id=current_user.id,
        action=action,
        details={
            "assignment_id": submission.assignment_id,
            "submission_id": submission.id,
            "icap_level": icap_level.value if icap_level else None,
            "evidence_summary": get_action_evidence(action, {})
        }
    )
    db.add(log)
    await db.commit()

    return {"id": submission.id, "message": "Assignment submitted"}


@router.get("/{assignment_id}/submissions")
async def get_submissions(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AssignmentSubmission, User).join(
        User, AssignmentSubmission.student_id == User.id
    ).where(AssignmentSubmission.assignment_id == assignment_id)

    if current_user.role == UserRole.STUDENT:
        query = query.where(AssignmentSubmission.student_id == current_user.id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": sub.id, "student_name": user.full_name,
            "file_url": sub.file_url, "text": sub.text,
            "grade": sub.grade, "teacher_feedback": sub.teacher_feedback,
            "submitted_at": sub.submitted_at.isoformat(),
            "graded_at": sub.graded_at.isoformat() if sub.graded_at else None,
        }
        for sub, user in rows
    ]


@router.put("/submissions/{submission_id}/grade")
async def grade_submission(
    submission_id: str,
    request: GradeSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    result = await db.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission.grade = request.grade
    submission.teacher_feedback = request.teacher_feedback
    submission.graded_at = datetime.utcnow()
    await db.commit()

    return {"message": "Submission graded", "grade": request.grade}
