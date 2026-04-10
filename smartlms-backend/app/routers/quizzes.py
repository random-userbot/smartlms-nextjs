"""
Smart LMS - Quizzes Router
Quiz CRUD, AI generation, attempts, anti-cheating, grading
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import re
import json
from difflib import SequenceMatcher
from app.database import get_db
from app.models.models import (
    User, UserRole, Course, Lecture, Quiz, QuizAttempt, 
    Notification, ICAPLog, ICAPLevel, ActivityLog, Enrollment,
    EngagementLog
)
from app.middleware.auth import (
    get_current_user, require_teacher, require_admin, 
    require_teacher_or_admin
)
from app.config import settings
from app.services.debug_logger import debug_logger
from app.services.icap_service import map_action_to_icap, get_action_evidence
from app.services.youtube_service import get_video_transcript
from app.services.quiz_generator_service import generate_quiz_questions
from app.services.groq_fallback import AllModelsRateLimitedError, chat_completion_with_fallback

router = APIRouter(prefix="/api/quizzes", tags=["Quizzes"])


# ─── Schemas ─────────────────────────────────────────────

class QuizQuestion(BaseModel):
    type: str = "mcq"  # mcq, short_answer, true_false, fill_blank
    question: str
    options: Optional[List[str]] = None
    correct_answer: str
    points: int = 1
    icap_level: str = "active"  # passive, active, constructive, interactive
    explanation: Optional[str] = None


class QuizCreate(BaseModel):
    lecture_id: str
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    questions: List[QuizQuestion]
    time_limit: int = 600
    is_published: bool = True
    anti_cheat_enabled: bool = True
    webcam_required: bool = True


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Optional[List[QuizQuestion]] = None
    time_limit: Optional[int] = None
    is_published: Optional[bool] = None
    anti_cheat_enabled: Optional[bool] = None


class QuizResponse(BaseModel):
    id: str
    lecture_id: str
    title: str
    description: Optional[str]
    questions: List[Dict]
    time_limit: int
    is_published: bool
    anti_cheat_enabled: bool
    webcam_required: bool
    created_at: datetime

    class Config:
        from_attributes = True


class QuizAttemptSubmit(BaseModel):
    quiz_id: str
    answers: Dict[str, Any]  # {question_index: answer}
    violations: List[Dict[str, Any]] = []
    engagement_data: Optional[Dict] = None
    started_at: Optional[str] = None
    time_spent: int = 0  # seconds


class QuizAttemptResponse(BaseModel):
    id: str
    quiz_id: str
    score: float
    max_score: float
    percentage: float
    violations: List[Dict]
    integrity_score: float
    answers: Dict
    correct_answers: Dict
    completed_at: datetime

    class Config:
        from_attributes = True


class AIQuizGenerateRequest(BaseModel):
    lecture_id: str
    num_questions: int = 10
    difficulty: str = "medium"  # easy, medium, hard
    include_icap: bool = True


class AIQuizRefineRequest(BaseModel):
    lecture_id: str
    current_questions: List[Dict]
    feedback: str


def _normalize_text(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _split_expected_answers(correct_answer: Any) -> List[str]:
    if isinstance(correct_answer, list):
        return [str(x).strip() for x in correct_answer if str(x).strip()]

    if correct_answer is None:
        return []

    text = str(correct_answer).strip()
    if not text:
        return []

    if "|" in text:
        return [x.strip() for x in text.split("|") if x.strip()]

    if ";" in text:
        return [x.strip() for x in text.split(";") if x.strip()]

    return [text]


def _split_fill_blank_expected(correct_answer: Any, blanks_count: int) -> List[str]:
    """Split expected answers for fill-in-the-blank with tolerant delimiters."""
    raw = _split_expected_answers(correct_answer)
    if not raw:
        return []

    if len(raw) > 1:
        return raw

    if blanks_count <= 1:
        return raw

    single = raw[0]
    # Many generated quizzes store multi-blank keys in one string.
    pieces = [p.strip() for p in re.split(r"\s*(?:\||;|,)\s*", single) if p.strip()]
    if len(pieces) == blanks_count:
        return pieces

    return raw


def _is_free_text_match(student_answer: str, expected_answer: str) -> bool:
    s = _normalize_text(student_answer)
    e = _normalize_text(expected_answer)

    if not s or not e:
        return False

    if s == e:
        return True

    if len(s) >= 5 and len(e) >= 5 and (s in e or e in s):
        return True

    if _text_similarity(s, e) >= 0.82:
        return True

    s_tokens = set(s.split())
    e_tokens = set(e.split())
    if e_tokens:
        overlap = len(s_tokens & e_tokens) / len(e_tokens)
        if overlap >= 0.65:
            return True

    return False


def _is_answer_correct(question: Dict[str, Any], student_answer: Any, correct_answer: Any) -> bool:
    q_type = (question.get("type") or "").lower()

    # Handle MCQ / True-False with strict normalized equality.
    if q_type in {"mcq", "true_false"}:
        return _normalize_text(str(student_answer or "")) == _normalize_text(str(correct_answer or ""))

    expected_candidates = _split_expected_answers(correct_answer)
    if not expected_candidates:
        return False

    # Fill-in-the-blank can arrive as a list from the frontend.
    if isinstance(student_answer, list):
        student_parts = [str(x).strip() for x in student_answer if str(x).strip()]
        blanks_count = str(question.get("question") or "").count("___")
        expected_parts = _split_fill_blank_expected(correct_answer, blanks_count or len(student_parts))

        # If teacher stored a single expected answer but student sent multiple blanks,
        # compare concatenated form as a fallback.
        if len(expected_parts) == 1 and len(student_parts) > 1:
            return _is_free_text_match(" ".join(student_parts), expected_parts[0])

        if len(student_parts) != len(expected_parts):
            return False

        return all(_is_free_text_match(student_parts[i], expected_parts[i]) for i in range(len(student_parts)))

    # Short/descriptive answers: accept close matches, alternatives (A|B), and token overlap.
    student_text = str(student_answer or "")
    return any(_is_free_text_match(student_text, candidate) for candidate in expected_candidates)


async def _ai_semantic_grade(
    question: Dict[str, Any],
    student_answer: Any,
    correct_answer: Any,
) -> Optional[bool]:
    """Use LLM semantic comparison for non-objective answers.

    Returns:
        True/False when model gives a valid judgment, None when unavailable.
    """
    if not settings.GROQ_API_KEY:
        return None

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        payload = {
            "question_type": question.get("type", ""),
            "question": question.get("question", ""),
            "expected_answer": correct_answer,
            "student_answer": student_answer,
            "grading_rules": [
                "Judge conceptual correctness and semantic equivalence, not exact phrasing.",
                "Allow for variations in terminology, synonyms, and paraphrasing.",
                "Disregard minor spelling, grammar, or punctuation errors.",
                "For descriptive answers, award points if the core message aligns with the expected answer.",
                "Only penalize if the answer is factually incorrect or contradictory.",
            ],
            "response_format": {
                "is_correct": "boolean",
                "confidence": "0_to_1_float",
            },
        }

        model_chain = settings.groq_chat_models_for_task(
            task="semantic_grading",
            primary_model="llama-3.3-70b-versatile",
        )

        response, _ = await chat_completion_with_fallback(
            client,
            primary_model=model_chain[0],
            fallback_models=model_chain[1:],
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict but fair quiz grader. Return ONLY valid JSON.",
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            temperature=0.0,
            max_tokens=120,
            stream=False,
            retries_per_model=settings.GROQ_MODEL_RETRIES_PER_MODEL,
            retry_base_seconds=settings.GROQ_MODEL_RETRY_BASE_SECONDS,
            retry_max_seconds=settings.GROQ_MODEL_RETRY_MAX_SECONDS,
        )

        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?", "", content).strip()
            content = re.sub(r"```$", "", content).strip()

        parsed = json.loads(content)
        judged = parsed.get("is_correct")
        confidence = float(parsed.get("confidence", 0) or 0)
        if isinstance(judged, bool) and confidence >= 0.55:
            return judged
    except Exception as e:
        debug_logger.log("error", f"AI quiz grading fallback failed: {str(e)}")

    return None


# ─── Routes ──────────────────────────────────────────────

@router.get("/lecture/{lecture_id}", response_model=List[QuizResponse])
async def get_lecture_quizzes(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all quizzes for a lecture"""
    query = select(Quiz).where(Quiz.lecture_id == lecture_id)
    if current_user.role == UserRole.STUDENT:
        query = query.where(Quiz.is_published == True)

    result = await db.execute(query)
    quizzes = result.scalars().all()

    responses = []
    for q in quizzes:
        quiz_dict = QuizResponse.model_validate(q)
        # Strip correct answers for students
        if current_user.role == UserRole.STUDENT:
            for question in quiz_dict.questions:
                question.pop("correct_answer", None)
                question.pop("explanation", None)
        responses.append(quiz_dict)

    return responses


@router.get("/mine")
async def get_my_quizzes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all quizzes visible to the current user.

    Students receive quizzes from their enrolled courses only.
    Teachers/Admin receive all quizzes.
    """
    query = (
        select(Quiz, Lecture.title, Course.title)
        .join(Lecture, Lecture.id == Quiz.lecture_id)
        .join(Course, Course.id == Lecture.course_id)
        .order_by(desc(Quiz.created_at))
    )

    if current_user.role == UserRole.STUDENT:
        query = (
            query.join(Enrollment, Enrollment.course_id == Course.id)
            .where(
                Enrollment.student_id == current_user.id,
                Quiz.is_published == True,
            )
        )

    rows = (await db.execute(query)).all()
    if not rows:
        return []

    quiz_ids = [q.id for q, _, _ in rows]
    attempts_by_quiz: Dict[str, List[QuizAttempt]] = {}
    lecture_watch_by_id: Dict[str, int] = {}

    if current_user.role == UserRole.STUDENT:
        attempts = (
            await db.execute(
                select(QuizAttempt)
                .where(QuizAttempt.student_id == current_user.id, QuizAttempt.quiz_id.in_(quiz_ids))
                .order_by(desc(QuizAttempt.completed_at))
            )
        ).scalars().all()
        for a in attempts:
            attempts_by_quiz.setdefault(a.quiz_id, []).append(a)

        lecture_ids = list({q.lecture_id for q, _, _ in rows if q.lecture_id})
        if lecture_ids:
            watch_rows = (
                await db.execute(
                    select(
                        EngagementLog.lecture_id,
                        func.coalesce(func.sum(EngagementLog.watch_duration), 0),
                    )
                    .where(
                        EngagementLog.student_id == current_user.id,
                        EngagementLog.lecture_id.in_(lecture_ids),
                    )
                    .group_by(EngagementLog.lecture_id)
                )
            ).all()
            lecture_watch_by_id = {lecture_id: int(total_watch or 0) for lecture_id, total_watch in watch_rows}

    response = []
    for quiz, lecture_title, course_title in rows:
        q_dict = QuizResponse.model_validate(quiz).model_dump()
        if current_user.role == UserRole.STUDENT:
            for question in q_dict.get("questions", []):
                question.pop("correct_answer", None)
                question.pop("explanation", None)

        attempts = attempts_by_quiz.get(quiz.id, [])
        latest_percentage = None
        best_percentage = None
        if attempts:
            latest = attempts[0]
            latest_percentage = round((latest.score / latest.max_score * 100) if latest.max_score else 0, 1)
            best_percentage = round(
                max((a.score / a.max_score * 100) if a.max_score else 0 for a in attempts),
                1,
            )

        response.append(
            {
                **q_dict,
                "lecture_title": lecture_title,
                "course_title": course_title,
                "attempt_count": len(attempts),
                "latest_percentage": latest_percentage,
                "best_percentage": best_percentage,
                "lecture_watch_seconds": lecture_watch_by_id.get(quiz.lecture_id, 0) if current_user.role == UserRole.STUDENT else None,
                "lecture_watched": bool(lecture_watch_by_id.get(quiz.lecture_id, 0) > 0) if current_user.role == UserRole.STUDENT else None,
            }
        )

    return response


@router.get("/student/{student_id}/course/{course_id}")
async def get_student_course_quizzes(
    student_id: str,
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Get all quiz attempts for a specific student in a specific course.
    Used for the Student Intelligence detail page.
    """
    # 1. Fetch attempts joined with quiz and lecture
    query = (
        select(QuizAttempt, Quiz.title.label("quiz_title"), Lecture.title.label("lecture_title"))
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Lecture, Lecture.id == Quiz.lecture_id)
        .where(
            QuizAttempt.student_id == student_id,
            Lecture.course_id == course_id
        )
        .order_by(desc(QuizAttempt.completed_at))
    )
    
    result = await db.execute(query)
    attempts = result.all()
    
    response = []
    for row in attempts:
        attempt = row[0]
        response.append({
            "id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "quiz_title": row.quiz_title,
            "lecture_title": row.lecture_title,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "percentage": round((attempt.score / max(attempt.max_score, 1)) * 100, 1),
            "integrity_score": attempt.integrity_score,
            "violations_count": len(attempt.violations) if attempt.violations else 0,
            "completed_at": attempt.completed_at.isoformat()
        })
        
    return response


@router.get("/student/{student_id}/course/all")
async def get_student_all_quizzes(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Get all quiz attempts for a specific student across all courses.
    """
    query = (
        select(QuizAttempt, Quiz.title.label("quiz_title"), Course.title.label("course_title"))
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .join(Lecture, Lecture.id == Quiz.lecture_id)
        .join(Course, Course.id == Lecture.course_id)
        .where(QuizAttempt.student_id == student_id)
        .order_by(desc(QuizAttempt.completed_at))
    )
    
    result = await db.execute(query)
    attempts = result.all()
    
    return [
        {
            "id": r[0].id,
            "quiz_title": r.quiz_title,
            "course_title": r.course_title,
            "score": r[0].score,
            "max_score": r[0].max_score,
            "percentage": round((r[0].score / max(r[0].max_score, 1)) * 100, 1),
            "completed_at": r[0].completed_at.isoformat()
        }
        for r in attempts
    ]


@router.post("", response_model=QuizResponse, status_code=201)
async def create_quiz(
    request: QuizCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Create a new quiz"""
    quiz = Quiz(
        lecture_id=request.lecture_id,
        title=request.title,
        description=request.description,
        questions=[q.model_dump() for q in request.questions],
        time_limit=request.time_limit,
        is_published=request.is_published,
        anti_cheat_enabled=request.anti_cheat_enabled,
        webcam_required=request.webcam_required,
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)

    debug_logger.log("activity", f"Quiz created: {quiz.title}",
                     user_id=current_user.id)

    return QuizResponse.model_validate(quiz)


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single quiz by ID"""
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    quiz_dict = QuizResponse.model_validate(quiz)
    # Strip correct answers for students
    if current_user.role == UserRole.STUDENT:
        for question in quiz_dict.questions:
            question.pop("correct_answer", None)
            question.pop("explanation", None)

    return quiz_dict


@router.put("/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    quiz_id: str,
    request: QuizUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Update a quiz"""
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    update_data = request.model_dump(exclude_unset=True)
    if "questions" in update_data and update_data["questions"] is not None:
        update_data["questions"] = [q.model_dump() if hasattr(q, 'model_dump') else q for q in update_data["questions"]]

    for field, value in update_data.items():
        setattr(quiz, field, value)

    await db.commit()
    await db.refresh(quiz)

    return QuizResponse.model_validate(quiz)

@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Delete a quiz"""
    result = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    await db.delete(quiz)
    await db.commit()
    return {"message": "Quiz deleted"}


@router.post("/attempt", response_model=QuizAttemptResponse)
async def submit_quiz_attempt(
    request: QuizAttemptSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a quiz attempt for grading"""
    # Get quiz
    result = await db.execute(select(Quiz).where(Quiz.id == request.quiz_id))
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Auto-grade
    score = 0
    max_score = 0
    correct_answers = {}

    for i, question in enumerate(quiz.questions):
        idx = str(i)
        max_score += question.get("points", 1)
        correct = question.get("correct_answer", "")
        correct_answers[idx] = correct

        student_answer = request.answers.get(idx, "")
        q_type = (question.get("type") or "").lower()
        is_correct = _is_answer_correct(question, student_answer, correct)

        # Semantic AI fallback for free-text style questions.
        if not is_correct and q_type not in {"mcq", "true_false"}:
            ai_decision = await _ai_semantic_grade(question, student_answer, correct)
            if ai_decision is True:
                is_correct = True

        if is_correct:
            score += question.get("points", 1)

    # Calculate integrity score (penalize violations)
    integrity_score = 100.0
    for v in request.violations:
        v_type = v.get("type", "")
        if v_type == "tab_switch":
            integrity_score -= 5
        elif v_type == "copy_paste":
            integrity_score -= 10
        elif v_type == "focus_loss":
            integrity_score -= 2
        elif v_type == "multiple_faces":
            integrity_score -= 15
    integrity_score = max(0, integrity_score)

    # Save attempt
    attempt = QuizAttempt(
        student_id=current_user.id,
        quiz_id=request.quiz_id,
        answers=request.answers,
        score=score,
        max_score=max_score,
        violations=request.violations,
        engagement_data=request.engagement_data,
        integrity_score=integrity_score,
        completed_at=datetime.utcnow(),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    percentage = (score / max_score * 100) if max_score > 0 else 0

    debug_logger.log("activity",
                     f"Quiz submitted: {quiz.title} | Score: {score}/{max_score} ({percentage:.0f}%) | Integrity: {integrity_score}",
                     user_id=current_user.id)

    return QuizAttemptResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        score=score,
        max_score=max_score,
        percentage=round(percentage, 1),
        violations=attempt.violations,
        integrity_score=integrity_score,
        answers=request.answers,
        correct_answers=correct_answers,
        completed_at=attempt.completed_at,
    )


@router.get("/attempts/{quiz_id}")
async def get_quiz_attempts(
    quiz_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get quiz attempts (student sees own, teacher sees all)"""
    query = select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id)

    if current_user.role == UserRole.STUDENT:
        query = query.where(QuizAttempt.student_id == current_user.id)

    result = await db.execute(query.order_by(QuizAttempt.completed_at.desc()))
    attempts = result.scalars().all()

    return [
        {
            "id": a.id,
            "student_id": a.student_id,
            "score": a.score,
            "max_score": a.max_score,
            "percentage": round((a.score / a.max_score * 100) if a.max_score else 0, 1),
            "violations": a.violations,
            "integrity_score": a.integrity_score,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in attempts
    ]


@router.post("/generate-ai")
async def generate_ai_quiz(
    request: AIQuizGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Generate quiz questions using AI from lecture transcript and materials"""
    # Get lecture
    result = await db.execute(select(Lecture).where(Lecture.id == request.lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    transcript = lecture.transcript or ""
    if not transcript:
        if lecture.youtube_url:
            transcript = await get_video_transcript(lecture.youtube_url, prefer_local=True)
            if transcript:
                lecture.transcript = transcript
                await db.commit()
                await db.refresh(lecture)
        # Fallback logic: If no transcript, use description/summary to avoid 400 errors
        context_fallback = []
        if lecture.description: context_fallback.append(f"Description: {lecture.description}")
        if lecture.summary: context_fallback.append(f"Summary: {lecture.summary}")
        
        transcript = "\n".join(context_fallback)
        
        if transcript:
            debug_logger.log("activity", f"Quiz generation using fallback context for lecture {lecture.id}")
            print(f"DEBUG: Quiz generation fallback: Using {len(context_fallback)} metadata fields as context.")
        else:
            debug_logger.log("error", f"Quiz generation failed: No transcript or metadata context for lecture {lecture.id}")
            print(f"ERROR: Quiz generation failed: No context available.")
            raise HTTPException(
                status_code=400, 
                detail="No context available for quiz generation. Please ensure the lecture has a description, summary, or transcript."
            )

    try:
        questions = await generate_quiz_questions(
            transcript=transcript,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            include_icap=request.include_icap,
        )
        return {"questions": questions, "count": len(questions)}
    except AllModelsRateLimitedError as e:
        debug_logger.log("warning", f"AI quiz generation rate-limited: {str(e)}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        debug_logger.log("error", f"AI quiz generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")

@router.post("/generate-ai-refine")
async def refine_ai_quiz(
    request: AIQuizRefineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Refine generated quiz questions using AI from lecture transcript and feedback"""
    # Get lecture
    result = await db.execute(select(Lecture).where(Lecture.id == request.lecture_id))
    lecture = result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    transcript = lecture.transcript or ""
    if not transcript:
        if lecture.youtube_url:
            transcript = await get_video_transcript(lecture.youtube_url, prefer_local=True)
            if transcript:
                lecture.transcript = transcript
                await db.commit()
                await db.refresh(lecture)
        if not transcript:
            raise HTTPException(status_code=400, detail="Transcript is not ready yet. Please retry shortly.")

    try:
        from app.services.quiz_generator_service import refine_quiz_questions
        questions = await refine_quiz_questions(
            transcript=transcript,
            current_questions=request.current_questions,
            feedback=request.feedback,
        )
        return {"questions": questions, "count": len(questions)}
    except AllModelsRateLimitedError as e:
        debug_logger.log("warning", f"AI quiz refinement rate-limited: {str(e)}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        debug_logger.log("error", f"AI quiz refinement failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Quiz refinement failed: {str(e)}")
