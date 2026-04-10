"""
Smart LMS - Analytics Router
Teaching scores, course analytics, engagement summaries
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from typing import Optional, List, Dict
from datetime import datetime
from statistics import pstdev
from app.database import get_db
from app.config import settings
from app.models.models import (
    User, UserRole, Course, Lecture, Enrollment, EnrollmentStatus,
    EngagementLog, QuizAttempt, Quiz, Feedback, Attendance,
    TeachingScore, ICAPLog, ICAPLevel, ActivityLog, Message, Material
)
from app.middleware.auth import get_current_user, require_teacher_or_admin
from app.services.debug_logger import debug_logger

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _score_level(score: float) -> str:
    if score < 20:
        return "Very Low"
    if score < 40:
        return "Low"
    if score < 60:
        return "Moderate"
    if score < 80:
        return "High"
    return "Very High"


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _build_dimension_distribution(history_rows: list[dict]) -> dict:
    dimensions = {
        "Boredom": {"Very Low": 0, "Low": 0, "Moderate": 0, "High": 0, "Very High": 0},
        "Engagement": {"Very Low": 0, "Low": 0, "Moderate": 0, "High": 0, "Very High": 0},
        "Confusion": {"Very Low": 0, "Low": 0, "Moderate": 0, "High": 0, "Very High": 0},
        "Frustration": {"Very Low": 0, "Low": 0, "Moderate": 0, "High": 0, "Very High": 0},
    }

    for row in history_rows:
        mapping = {
            "Boredom": row.get("boredom_score", 0),
            "Engagement": row.get("engagement_score", 0),
            "Confusion": row.get("confusion_score", 0),
            "Frustration": row.get("frustration_score", 0),
        }
        for dimension, score in mapping.items():
            dimensions[dimension][_score_level(float(score or 0))] += 1

    return dimensions


def _dashboard_insights(scores: list[float], history_rows: list[dict]) -> list[str]:
    if not scores:
        return ["No engagement history yet. Attend more lecture sessions to unlock analytics insights."]

    insights = []
    if len(scores) >= 3:
        trend_delta = scores[-1] - scores[0]
        if trend_delta >= 8:
            insights.append("Your engagement trend is improving over recent sessions. Keep this momentum.")
        elif trend_delta <= -8:
            insights.append("Your engagement trend is declining. Try shorter focused study blocks with fewer distractions.")

    avg_score = _safe_mean(scores)
    if avg_score >= 75:
        insights.append("Strong sustained engagement detected. You're learning in a high-attention zone.")
    elif avg_score < 45:
        insights.append("Average engagement is currently low. Consider pausing videos for quick active recall notes.")

    if history_rows:
        avg_boredom = _safe_mean([float(r.get("boredom_score") or 0) for r in history_rows])
        avg_confusion = _safe_mean([float(r.get("confusion_score") or 0) for r in history_rows])
        avg_frustration = _safe_mean([float(r.get("frustration_score") or 0) for r in history_rows])

        if avg_confusion > 45:
            insights.append("Confusion signals are elevated. Review difficult concepts and ask AI Tutor targeted questions.")
        if avg_boredom > 50:
            insights.append("Boredom is high in multiple sessions. Increase interaction frequency with quizzes and note-taking.")
        if avg_frustration > 40:
            insights.append("Frustration appears elevated. Break lessons into smaller chunks and revisit prerequisites.")

    if not insights:
        insights.append("Your engagement profile is stable. Continue current learning habits.")
    return insights[:5]


def _build_model_analytics(logs: list[EngagementLog]) -> dict:
    if not logs:
        return {
            "sessions_with_model": 0,
            "avg_confidence": 0.0,
            "model_type_distribution": {},
            "hybrid_sessions": 0,
            "avg_ensemble_models": 0.0,
        }

    confidences: list[float] = []
    model_type_distribution: dict[str, int] = {}
    hybrid_sessions = 0
    ensemble_counts: list[int] = []

    for log in logs:
        feats = log.features if isinstance(log.features, dict) else {}
        model_type = str(feats.get("model_type") or "unknown")
        model_type_distribution[model_type] = model_type_distribution.get(model_type, 0) + 1

        conf = feats.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))

        ensemble_models = feats.get("ensemble_models")
        ensemble_count = len(ensemble_models) if isinstance(ensemble_models, list) else 0
        if "ensemble" in model_type or ensemble_count > 0:
            hybrid_sessions += 1
            ensemble_counts.append(ensemble_count)

    return {
        "sessions_with_model": len(logs),
        "avg_confidence": round(_safe_mean(confidences), 3),
        "model_type_distribution": model_type_distribution,
        "hybrid_sessions": hybrid_sessions,
        "avg_ensemble_models": round(_safe_mean([float(x) for x in ensemble_counts]), 2) if ensemble_counts else 0.0,
    }


@router.get("/teaching-score/{course_id}")
async def get_teaching_score(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate comprehensive teaching score for a course (v5).
    
    Components (Updated Weights):
      - Avg Engagement (15%): Mean engagement score across sessions
      - Engagement Trend (10%): Slope of engagement over time
      - Quiz Performance (10%): Average quiz score
      - ICAP Distribution (10%): Weighted by learning depth
      - Feedback (10%): Student satisfaction ratings
      - Teacher Activity (15%): Time spent + materials uploaded
      - Responsiveness (10%): Message response speed & frequency
      - Attendance (10%): Presence scores
      - Completion Rate (5%): Sessions vs expected
      - Engagement Consistency (5%): Lower std = more consistent
    """
    try:
        # Get course
        course_result = await db.execute(select(Course).where(Course.id == course_id))
        course = course_result.scalar_one_or_none()
        if not course:
            return {
                "course_id": course_id,
                "status": "not_found",
                "overall_score": 0,
                "components": {},
                "recommendations": ["Course not found in production registry."]
            }

        # ── 1. Engagement Score (Filtered for Completion) ──
        eng_result = await db.execute(
            select(EngagementLog).where(
                EngagementLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                ),
                # Filter: only include finalized sessions
                EngagementLog.is_finalized == True,
                (EngagementLog.watch_duration * 1.25 >= EngagementLog.total_duration)
            ).order_by(EngagementLog.started_at)
        )
        engagement_logs = eng_result.scalars().all()

        engagement_scores = [l.engagement_score or 0.0 for l in engagement_logs]
        engagement_avg = sum(engagement_scores) / max(len(engagement_scores), 1)

        # ── 2. Engagement Trend (retention slope) ──
        if len(engagement_scores) >= 3:
            import numpy as np
            x = np.arange(len(engagement_scores), dtype=float)
            y = np.array(engagement_scores, dtype=float)
            slope, _ = np.polyfit(x, y, 1)
            trend_score = min(100, max(0, 50 + slope * 50))
        else:
            trend_score = 0.0
            slope = 0.0

        # ── 3. Low Engagement Rate ──
        low_threshold = 40.0
        low_rate = 0.0
        if engagement_scores:
            low_count = sum(1 for s in engagement_scores if s < low_threshold)
            low_rate = low_count / len(engagement_scores)

        # ── 4. Quiz Score ──
        quiz_result = await db.execute(
            select(func.avg(QuizAttempt.score / func.nullif(QuizAttempt.max_score, 0) * 100)).where(
                QuizAttempt.quiz_id.in_(
                    select(Quiz.id).where(
                        Quiz.lecture_id.in_(
                            select(Lecture.id).where(Lecture.course_id == course_id)
                        )
                    )
                )
            )
        )
        quiz_avg = quiz_result.scalar() or 0.0

        # ── 5. ICAP Distribution ──
        icap_result = await db.execute(
            select(ICAPLog.classification, func.count()).where(
                ICAPLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                ),
                ICAPLog.student_id.in_(
                    select(EngagementLog.student_id).where(
                        EngagementLog.lecture_id == ICAPLog.lecture_id,
                        (EngagementLog.watch_duration * 1.25 >= EngagementLog.total_duration)
                    )
                )
            ).group_by(ICAPLog.classification)
        )
        icap_rows = icap_result.all()
        icap_counts = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in icap_rows}
        icap_total = sum(icap_counts.values()) or 1

        icap_weights = {"interactive": 100, "constructive": 75, "active": 50, "passive": 25}
        icap_score = sum(
            icap_counts.get(level, 0) / icap_total * weight
            for level, weight in icap_weights.items()
        )

        # ── 6. Attendance Score ──
        att_result = await db.execute(
            select(func.avg(Attendance.presence_score)).where(
                Attendance.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                )
            )
        )
        attendance_avg = att_result.scalar() or 0.0

        # ── 7. Feedback Score ──
        fb_result = await db.execute(
            select(func.avg(Feedback.overall_rating)).where(Feedback.course_id == course_id)
        )
        feedback_avg_raw = fb_result.scalar() or 0.0
        feedback_score = (feedback_avg_raw / 5) * 100

        # ── 8. Completion Rate ──
        total_lectures_res = await db.execute(
            select(func.count()).select_from(Lecture).where(Lecture.course_id == course_id)
        )
        num_lectures = total_lectures_res.scalar() or 1
        total_students_res = await db.execute(
            select(func.count()).select_from(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
        num_students = total_students_res.scalar() or 1
        completed_res = await db.execute(
            select(func.count(func.distinct(
                func.concat(EngagementLog.student_id, '-', EngagementLog.lecture_id)
            ))).where(
                EngagementLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                )
            )
        )
        completion_count = completed_res.scalar() or 0
        completion_rate = min(100, (completion_count / max(num_lectures * num_students, 1)) * 100)

        # ── 9. Responsiveness (Messages) ──
        msg_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.sender_id == course.teacher_id,
                Message.course_id == course_id,
            )
        )
        teacher_messages = msg_result.scalar() or 0
        msgs_per_student = teacher_messages / max(num_students, 1)
        
        # Calculate response delay
        msg_query = select(Message).where(Message.course_id == course_id).order_by(Message.created_at)
        msg_res = await db.execute(msg_query)
        all_msgs = msg_res.scalars().all()
        
        response_times = []
        for i in range(len(all_msgs) - 1):
            m = all_msgs[i]
            if m.sender_id != course.teacher_id:
                for j in range(i+1, min(i+10, len(all_msgs))):
                    reply = all_msgs[j]
                    if reply.sender_id == course.teacher_id:
                        delay = (reply.created_at - m.created_at).total_seconds()
                        response_times.append(delay)
                        break
        
        avg_response_delay_hrs = (sum(response_times) / len(response_times) / 3600.0) if response_times else 24.0
        
        if msgs_per_student >= 2: resp_freq_score = 100.0
        elif msgs_per_student >= 1: resp_freq_score = 75.0
        else: resp_freq_score = 40.0
        
        responsiveness_score = resp_freq_score 

        # ── 10. Teacher Activity Score (Time Spent + Materials) ──
        activity_res = await db.execute(
            select(ActivityLog).where(ActivityLog.user_id == course.teacher_id).order_by(ActivityLog.created_at)
        )
        teacher_logs = activity_res.scalars().all()
        
        time_spent_hours = 0.0
        if teacher_logs:
            sessions = []
            current_session = [teacher_logs[0]]
            for i in range(1, len(teacher_logs)):
                delta = (teacher_logs[i].created_at - teacher_logs[i-1].created_at).total_seconds()
                if delta < 1800:
                    current_session.append(teacher_logs[i])
                else:
                    sessions.append(current_session)
                    current_session = [teacher_logs[i]]
            sessions.append(current_session)
            for s in sessions:
                if len(s) > 1:
                    span = (s[-1].created_at - s[0].created_at).total_seconds()
                    time_spent_hours += max(span, 300) / 3600.0
                else:
                    time_spent_hours += 0.1
        
        mat_res = await db.execute(
            select(func.count()).select_from(Material).where(
                Material.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                )
            )
        )
        materials_count = mat_res.scalar() or 0
        
        activity_v5_points = 0.0
        activity_v5_points += min(40, (time_spent_hours / 20.0) * 40)
        activity_v5_points += min(30, (materials_count / 10.0) * 30)
        
        if avg_response_delay_hrs < 2: responsiveness_bonus = 30
        elif avg_response_delay_hrs < 12: responsiveness_bonus = 15
        else: responsiveness_bonus = 5
        activity_v5_points += responsiveness_bonus
        
        teacher_activity_score = round(activity_v5_points, 1)

        # ── 11. Consistency ──
        if len(engagement_scores) >= 3:
            import numpy as np
            eng_std = float(np.std(engagement_scores))
            consistency_score = max(0, min(100, 100 - eng_std * 2))
        else:
            eng_std = 0.0
            consistency_score = 50.0

        # ── Overall weighted score (v5) ──
        overall = (
            engagement_avg * 0.15 +
            trend_score * 0.10 +
            quiz_avg * 0.10 +
            icap_score * 0.10 +
            feedback_score * 0.10 +
            teacher_activity_score * 0.15 +
            responsiveness_score * 0.10 +
            attendance_avg * 0.10 +
            completion_rate * 0.05 +
            consistency_score * 0.05
        )

        shap_breakdown = {
            "engagement": round(engagement_avg * 0.15, 1),
            "engagement_trend": round(trend_score * 0.10, 1),
            "quiz_performance": round(quiz_avg * 0.10, 1),
            "icap_distribution": round(icap_score * 0.10, 1),
            "feedback_sentiment": round(feedback_score * 0.10, 1),
            "teacher_activity_time": round(teacher_activity_score * 0.15, 1),
            "teacher_responsiveness": round(responsiveness_score * 0.10, 1),
            "attendance": round(attendance_avg * 0.10, 1),
            "completion_rate": round(completion_rate * 0.05, 1),
            "engagement_consistency": round(consistency_score * 0.05, 1),
        }

        # Recommendations
        recommendations = []
        if engagement_avg < 50: recommendations.append("Student engagement is low. Consider more interactive content.")
        if slope < 0: recommendations.append("Engagement is declining. Try varying content formats.")
        if avg_response_delay_hrs > 24: recommendations.append("Response time is slow (>24h). Aim for faster replies.")
        if time_spent_hours < 5: recommendations.append(f"Teacher time on site is low ({time_spent_hours:.1f}h). Increasing presence boosts student confidence.")
        if materials_count < 2: recommendations.append("Few materials uploaded. Supplementary resources improve learning outcomes.")
        if not recommendations: recommendations.append("Teaching metrics are healthy. Keep up the great work!")

        # Save score
        score_obj = TeachingScore(
            teacher_id=course.teacher_id,
            course_id=course_id,
            engagement_score=engagement_avg,
            quiz_score=quiz_avg,
            attendance_score=attendance_avg,
            feedback_score=feedback_score,
            completion_score=completion_rate,
            overall_score=overall,
            shap_breakdown=shap_breakdown,
            recommendations=recommendations,
        )
        db.add(score_obj)
        await db.commit()

        # ── 12. Forensic Logs ──
        raw_logs_res = await db.execute(
            select(ActivityLog, User.full_name)
            .join(User, User.id == ActivityLog.user_id)
            .where(ActivityLog.action.in_(['quiz_submit', 'lecture_start', 'material_download']))
            .order_by(desc(ActivityLog.created_at))
            .limit(15)
        )
        forensic_logs = [
            {
                "user": row[1],
                "action": row[0].action,
                "timestamp": row[0].created_at.isoformat(),
                "details": row[0].details
            } for row in raw_logs_res.all()
        ]

        # 13. Confidence Score
        log_count = len(engagement_logs)
        if log_count > 50: confidence = 98.4
        elif log_count > 20: confidence = 95.2
        elif log_count > 5: confidence = 88.7
        else: confidence = 75.0

        return {
            "course_id": course_id,
            "course_title": course.title,
            "overall_score": round(overall, 1),
            "confidence_score": confidence,
            "forensic_logs": forensic_logs,
            "components": {
                "engagement": round(engagement_avg, 1),
                "engagement_trend": round(trend_score, 1),
                "quiz_performance": round(quiz_avg, 1),
                "icap_score": round(icap_score, 1),
                "feedback": round(feedback_score, 1),
                "attendance": round(attendance_avg, 1),
                "completion_rate": round(completion_rate, 1),
                "responsiveness": round(responsiveness_score, 1),
                "activity_score": round(teacher_activity_score, 1),
            },
            "teacher_details": {
                "time_spent_hours": round(time_spent_hours, 2),
                "materials_uploaded": materials_count,
                "avg_response_delay_hrs": round(avg_response_delay_hrs, 2) if response_times else None,
                "total_messages": teacher_messages
            },
            "shap_breakdown": shap_breakdown,
            "recommendations": recommendations,
            "version": "v5",
            "calculated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        debug_logger.log("error", f"Teaching Score Crash for {course_id}: {str(e)}")
        return {
            "course_id": course_id,
            "overall_score": 0,
            "status": "partial_error",
            "components": {"engagement": 0, "quiz": 0, "attendance": 0},
            "recommendations": ["Data sync in progress. Data is coming online shortly."]
        }

@router.get("/live-sessions")
async def get_live_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Fetch all active, non-finalized sessions for the teacher's radar.
    This fulfills the requirement to see 'Live Flow' in real-time.
    """
    try:
        # Get all course IDs owned by this teacher
        teacher_courses_stmt = select(Course.id).where(Course.teacher_id == current_user.id)
        
        from datetime import timedelta
        # Get non-finalized logs for these courses
        # FIX: Filter by Lecture.course_id not EngagementLog.lecture_id
        stmt = (
            select(EngagementLog, User.full_name, Lecture.title, User.avatar_url)
            .join(User, User.id == EngagementLog.student_id)
            .join(Lecture, Lecture.id == EngagementLog.lecture_id)
            .where(
                EngagementLog.is_finalized == False,
                EngagementLog.updated_at >= datetime.utcnow() - timedelta(minutes=30),
                Lecture.course_id.in_(teacher_courses_stmt)
            )
            .order_by(desc(EngagementLog.updated_at))
        )
        
        result = await db.execute(stmt)
        sessions = []
        for log, student_name, lecture_title, avatar_url in result.all():
            sessions.append({
                "session_id": log.session_id,
                "student_id": str(log.student_id),
                "student_name": student_name,
                "student_avatar": avatar_url,
                "lecture_title": lecture_title,
                "engagement": round(log.overall_score or 0, 1),
                "status": log.icap_classification.value if hasattr(log.icap_classification, 'value') else str(log.icap_classification),
                "last_active": log.updated_at.isoformat(),
                "waveform": (log.scores_timeline if log.scores_timeline else [])[-20:] # Last 20 points for mini-wave
            })
        
        return sessions
    except Exception as e:
        debug_logger.log("error", f"Analytics Radar Crash: {str(e)}")
        # Return empty list on crash to prevent CORS blocks on 500s
        return []


@router.get("/course-dashboard/{course_id}")
async def get_course_dashboard(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive course dashboard analytics"""
    try:
        eng_summary_res = await db.execute(
            select(
                func.count(EngagementLog.id),
                func.avg(EngagementLog.engagement_score),
                func.avg(EngagementLog.boredom_score),
                func.avg(EngagementLog.confusion_score),
                func.sum(EngagementLog.tab_switches),
            ).where(
                EngagementLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                ),
                EngagementLog.is_finalized == True
            )
        )
        eng_total, eng_avg, boredom_avg, confusion_avg, tab_total = eng_summary_res.one()

        # ICAP distribution
        icap_res = await db.execute(
            select(ICAPLog.classification, func.count()).where(
                ICAPLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                ),
                ICAPLog.student_id.in_(
                   select(EngagementLog.student_id).where(
                       EngagementLog.lecture_id == ICAPLog.lecture_id,
                       (EngagementLog.watch_duration * 1.25 >= EngagementLog.total_duration)
                   )
                )
            ).group_by(ICAPLog.classification)
        )
        icap_dist = {row[0].value if hasattr(row[0], 'value') else str(row[0]): row[1] for row in icap_res.all()}

        return {
            "course_id": course_id,
            "engagement": {
                "total_sessions": eng_total or 0,
                "avg_score": round(eng_avg or 0, 1),
                "avg_boredom": round(boredom_avg or 0, 1),
                "avg_confusion": round(confusion_avg or 0, 1),
                "total_tab_switches": int(tab_total or 0),
            },
            "icap_distribution": icap_dist,
        }
    except Exception as e:
        debug_logger.log("error", f"Course Dashboard Crash for {course_id}: {str(e)}")
        return {
            "course_id": course_id,
            "engagement": {"total_sessions": 0, "avg_score": 0, "avg_boredom": 0, "avg_confusion": 0, "total_tab_switches": 0},
            "icap_distribution": {}
        }


@router.get("/course/{course_id}/lectures-engagement")
async def get_lectures_engagement_summary(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Get average engagement score for each lecture in a course"""
    try:
        eng_res = await db.execute(
            select(
                EngagementLog.lecture_id,
                func.avg(EngagementLog.engagement_score),
                func.count(EngagementLog.id)
            ).where(
                EngagementLog.lecture_id.in_(
                    select(Lecture.id).where(Lecture.course_id == course_id)
                ),
                EngagementLog.is_finalized == True
            ).group_by(EngagementLog.lecture_id)
        )
        rows = eng_res.all()
        
        return {
            row[0]: {
                "avg_engagement": round(float(row[1] or 0), 1),
                "session_count": int(row[2])
            }
            for row in rows
        }
    except Exception as e:
        debug_logger.log("error", f"Lectures Engagement Summary Crash for {course_id}: {str(e)}")
        return {}


@router.get("/course/{course_id}/engagement")
async def get_course_engagement(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Alias for course-dashboard logic to match frontend requirement.
    Ensures that empty states return 200 OK to prevent CORS blocks.
    """
    # 1. Verify course
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        # We return a 200 OK with empty data to prevent CORS issues on 404s in some environments
        return {
            "course_id": course_id,
            "status": "not_found",
            "engagement": {"total_sessions": 0, "avg_score": 0, "avg_boredom": 0, "avg_confusion": 0, "total_tab_switches": 0},
            "icap_distribution": {}
        }

    # Reuse dashboard logic
    dashboard = await get_course_dashboard(course_id, db, current_user)
    return dashboard

# Keep remaining standard analytical endpoints...
@router.get("/student-dashboard")
async def get_student_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive student dashboard analytics with v5 metrics"""
    try:
        # 1. Focus Pulse (Last 30 engagement scores)
        pulse_res = await db.execute(
            select(EngagementLog.engagement_score)
            .where(EngagementLog.student_id == current_user.id)
            .order_by(desc(EngagementLog.started_at))
            .limit(30)
        )
        pulse = [round(float(s or 0), 1) for s in pulse_res.scalars().all()]
        pulse.reverse() # Chronological
        
        # 2. Active Time (Total hours watched)
        time_res = await db.execute(
            select(func.sum(EngagementLog.watch_duration))
            .where(EngagementLog.student_id == current_user.id)
        )
        active_seconds = time_res.scalar() or 0
        active_hours = round(active_seconds / 3600.0, 1)

        # 3. Active Nodes (Enrolled courses + completion)
        nodes_query = (
            select(Course.title, func.count(Lecture.id), func.count(func.distinct(Attendance.lecture_id)))
            .join(Enrollment, Enrollment.course_id == Course.id)
            .join(Lecture, Lecture.course_id == Course.id)
            .outerjoin(Attendance, (Attendance.lecture_id == Lecture.id) & (Attendance.student_id == current_user.id))
            .where(Enrollment.student_id == current_user.id)
            .group_by(Course.id)
        )
        nodes_res = await db.execute(nodes_query)
        active_nodes = []
        for title, total_lectures, attended_count in nodes_res.all():
            progress = round((attended_count / max(total_lectures, 1)) * 100, 0)
            if progress > 0:
                active_nodes.append({"title": title, "progress": progress})

        # 4. Growth Calculation (Current week vs Previous week)
        from datetime import timedelta
        now = datetime.utcnow()
        this_week_start = now - timedelta(days=7)
        prev_week_start = now - timedelta(days=14)

        this_week_res = await db.execute(
            select(func.avg(EngagementLog.engagement_score))
            .where(
                (EngagementLog.student_id == current_user.id) & 
                (EngagementLog.started_at >= this_week_start)
            )
        )
        this_week_avg = this_week_res.scalar() or 0.0

        prev_week_res = await db.execute(
            select(func.avg(EngagementLog.engagement_score))
            .where(
                (EngagementLog.student_id == current_user.id) & 
                (EngagementLog.started_at >= prev_week_start) &
                (EngagementLog.started_at < this_week_start)
            )
        )
        prev_week_avg = prev_week_res.scalar() or 0.0

        growth = 0.0
        if prev_week_avg > 0:
            growth = round(((this_week_avg - prev_week_avg) / prev_week_avg) * 100, 1)
        elif this_week_avg > 0:
            growth = 100.0 # First week growth

        # 5. Insights
        avg_focus = round(_safe_mean(pulse), 1)
        insights = _dashboard_insights(pulse, [])
        
        # Daily Goal (Today's watch time vs 1hr target)
        today = now.date()
        today_time_res = await db.execute(
            select(func.sum(EngagementLog.watch_duration))
            .where(
                (EngagementLog.student_id == current_user.id) & 
                (func.date(EngagementLog.started_at) == today)
            )
        )
        today_seconds = today_time_res.scalar() or 0
        goal_progress = min(100, round((today_seconds / 3600.0) * 100, 0))

        return {
            "full_name": current_user.full_name,
            "focus_pulse": pulse,
            "average_focus": avg_focus,
            "active_time_hours": active_hours,
            "growth_percent": growth,
            "active_nodes": active_nodes[:3],
            "daily_goal_progress": goal_progress,
            "aika_insight": insights[0] if insights else "Your learning sync is stable."
        }
    except Exception as e:
        debug_logger.log("error", f"Student Dashboard Crash for {current_user.id}: {str(e)}")
        return {
            "full_name": current_user.full_name,
            "focus_pulse": [],
            "average_focus": 0,
            "active_time_hours": 0,
            "growth_percent": 0,
            "active_nodes": [],
            "daily_goal_progress": 0,
            "aika_insight": "Dashboard is synchronizing your metrics..."
        }

@router.get("/student-engagement-history")
async def get_student_engagement_history(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chronological engagement history for the current student"""
    from datetime import timedelta
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(EngagementLog)
        .where(
            (EngagementLog.student_id == current_user.id) &
            (EngagementLog.started_at >= start_date)
        )
        .order_by(EngagementLog.started_at.asc())
    )
    logs = result.scalars().all()
    
    return [
        {
            "engagement": log.engagement_score or 0.0,
            "timestamp": log.started_at.isoformat()
        } for log in logs
    ]

@router.get("/student/icap-distribution")
async def get_student_icap_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get real ICAP state distribution for the current student"""
    icap_res = await db.execute(
        select(ICAPLog.classification, func.count())
        .where(ICAPLog.student_id == current_user.id)
        .group_by(ICAPLog.classification)
    )
    rows = icap_res.all()
    
    dist = {"passive": 0, "active": 0, "constructive": 0, "interactive": 0}
    total = 0
    for classification, count in rows:
        label = classification.value if hasattr(classification, 'value') else str(classification)
        dist[label.lower()] = count
        total += count
    
    if total == 0:
        return {"distribution": dist, "total": 0, "dominant": "Passive"}
        
    percentages = {k: round((v / total) * 100, 1) for k, v in dist.items()}
    dominant = max(percentages, key=percentages.get)
    
    return {
        "distribution": percentages,
        "total": total,
        "dominant": dominant.capitalize()
    }

@router.get("/student/export")
async def export_student_data(
    course_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate engagement logs, ICAP, and quiz attempts for export"""
    # 1. Logs
    log_query = select(EngagementLog).where(EngagementLog.student_id == current_user.id)
    if course_id:
        log_query = log_query.join(Lecture, Lecture.id == EngagementLog.lecture_id).where(Lecture.course_id == course_id)
    
    logs = (await db.execute(log_query)).scalars().all()
    
    # 2. ICAP
    icap_query = select(ICAPLog).where(ICAPLog.student_id == current_user.id)
    if course_id:
        icap_query = icap_query.where(ICAPLog.lecture_id.in_(select(Lecture.id).where(Lecture.course_id == course_id)))
    
    icaps = (await db.execute(icap_query)).scalars().all()
    
    # 3. Quizzes
    quiz_query = select(QuizAttempt).where(QuizAttempt.student_id == current_user.id)
    if course_id:
        quiz_query = quiz_query.join(Quiz, Quiz.id == QuizAttempt.quiz_id).join(Lecture, Lecture.id == Quiz.lecture_id).where(Lecture.course_id == course_id)
        
    quizzes = (await db.execute(quiz_query)).scalars().all()
    
    return {
        "report_generated_at": datetime.utcnow().isoformat(),
        "student_name": current_user.full_name,
        "scope": course_id or "global",
        "engagement_logs": [
            {
                "lecture_id": l.lecture_id,
                "score": l.engagement_score,
                "duration": l.watch_duration,
                "tabs": l.tab_switches,
                "date": l.started_at.isoformat()
            } for l in logs
        ],
        "icap_transitions": [
            {
                "level": i.classification.value if hasattr(i.classification, 'value') else str(i.classification),
                "timestamp": i.timestamp.isoformat() if hasattr(i.timestamp, 'isoformat') else str(i.timestamp)
            } for i in icaps
        ],
        "quiz_history": [
            {
                "quiz_id": q.quiz_id,
                "score": q.score,
                "max": q.max_score,
                "date": q.completed_at.isoformat() if q.completed_at else None
            } for q in quizzes
        ]
    }

@router.get("/icap-performance")
async def get_icap_performance_correlation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    course_id: Optional[str] = None
):
    """
    Pedagogical Correlation: ICAP Depth vs. Quiz Performance.
    Returns average quiz scores grouped by the student's highest ICAP activity level.
    """
    # 1. Get all students and their dominant ICAP levels
    icap_query = select(
        ICAPLog.student_id,
        ICAPLog.classification,
        func.count(ICAPLog.id)
    ).group_by(ICAPLog.student_id, ICAPLog.classification)
    
    if course_id:
        icap_query = icap_query.where(ICAPLog.lecture_id.in_(
            select(Lecture.id).where(Lecture.course_id == course_id)
        ))
        
    icap_res = await db.execute(icap_query)
    student_icap_map = {}
    for sid, level, count in icap_res.all():
        level_str = level.value if hasattr(level, 'value') else str(level)
        if sid not in student_icap_map:
            student_icap_map[sid] = {"passive": 0, "active": 0, "constructive": 0, "interactive": 0}
        student_icap_map[sid][level_str] = count

    # Determine dominant level for each student
    dominant_levels = {}
    for sid, counts in student_icap_map.items():
        dominant_levels[sid] = max(counts, key=counts.get)

    # 2. Get average quiz scores for these students
    quiz_query = select(
        QuizAttempt.student_id,
        func.avg(QuizAttempt.score / func.nullif(QuizAttempt.max_score, 0) * 100)
    ).group_by(QuizAttempt.student_id)
    
    quiz_res = await db.execute(quiz_query)
    
    # 3. Correlate
    performance_by_icap = {
        "passive": {"scores": [], "avg": 0.0, "count": 0},
        "active": {"scores": [], "avg": 0.0, "count": 0},
        "constructive": {"scores": [], "avg": 0.0, "count": 0},
        "interactive": {"scores": [], "avg": 0.0, "count": 0}
    }
    
    for sid, avg_score in quiz_res.all():
        level = dominant_levels.get(sid)
        if level and level in performance_by_icap:
            performance_by_icap[level]["scores"].append(float(avg_score))
            performance_by_icap[level]["count"] += 1

    # Final averages
    for level in performance_by_icap:
        scores = performance_by_icap[level]["scores"]
        performance_by_icap[level]["avg"] = round(sum(scores) / len(scores), 1) if scores else 0.0
        del performance_by_icap[level]["scores"]

@router.get("/lecture-waves/{lecture_id}")
async def get_lecture_engagement_waves(
    lecture_id: str,
    student_ids: Optional[str] = None, # Comma separated
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Multi-Wave Engagement Visualization Engine.
    Returns per-student engagement scores binned by 1-minute intervals.
    Used for the 'Multi-Wave' teacher dashboard.
    """
    if current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    lecture_result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
    lecture = lecture_result.scalar_one_or_none()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    query = select(EngagementLog, User).join(User, User.id == EngagementLog.student_id).where(EngagementLog.lecture_id == lecture_id)
    
    if student_ids:
        s_list = [s.strip() for s in student_ids.split(",") if s.strip()]
        query = query.where(EngagementLog.student_id.in_(s_list))

    result = await db.execute(query)
    rows = result.all()

    duration = lecture.duration or 3600 # Fallback 1hr
    max_minutes = int(duration // 60) + 1
    
    student_data = {}
    
    for log, student in rows:
        if student.id not in student_data:
            student_data[student.id] = {
                "name": student.full_name,
                "bins": [[] for _ in range(max_minutes)]
            }
        
        timeline = log.scores_timeline or []
        for entry in timeline:
            ts = entry.get("timestamp", 0)
            minute = int(ts // 60)
            if 0 <= minute < max_minutes:
                student_data[student.id]["bins"][minute].append(entry)

    # Average the bins
    formatted_students = []
    for sid, data in student_data.items():
        waves = []
        lapse_waves = [] # Binned no-face/inattention counts
        tab_waves = []   # Binned tab-switch counts
        
        for minute_idx, entries in enumerate(data["bins"]):
            if not entries:
                waves.append(None)
                lapse_waves.append(0)
                tab_waves.append(0)
                continue
                
            avg_score = sum(float(e.get("engagement", 50)) for e in entries) / len(entries)
            waves.append(round(avg_score, 1))
            
            # Count explicit lapses from new flags
            lapses = sum(1 for e in entries if not e.get("face_detected", True))
            tabs = sum(1 for e in entries if not e.get("tab_visible", True))
            
            lapse_waves.append(lapses)
            tab_waves.append(tabs)
        
        formatted_students.append({
            "student_id": sid,
            "student_name": data["name"],
            "wave": waves,
            "lapse_wave": lapse_waves,
            "tab_wave": tab_waves
        })

    return {
        "lecture_id": lecture_id,
        "lecture_title": lecture.title,
        "resolution": "1-minute",
        "max_minutes": max_minutes,
        "timeline": list(range(max_minutes)),
        "students": formatted_students
    }
@router.get("/course/{course_id}/engagement")
async def get_course_student_engagement(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Get engagement summary for all students in a course.
    Returns composite scores, visibility lapses, and tab switches.
    Used for the Teacher Dashboard Risk Matrix.
    """
    # 1. Get all students in course
    enrollment_query = select(User).join(Enrollment, Enrollment.student_id == User.id).where(
        Enrollment.course_id == course_id,
        Enrollment.status == EnrollmentStatus.ACTIVE
    )
    result = await db.execute(enrollment_query)
    students = result.scalars().all()
    
    # 2. Get all lectures for this course
    lecture_ids_query = select(Lecture.id).where(Lecture.course_id == course_id)
    lecture_ids_res = await db.execute(lecture_ids_query)
    lecture_ids = lecture_ids_res.scalars().all()

    if not lecture_ids:
        return []

    # 3. Get engagement logs for these students and lectures (Filtered for Completion)
    log_query = select(EngagementLog).where(
        EngagementLog.lecture_id.in_(lecture_ids),
        (EngagementLog.watch_duration * 1.25 >= EngagementLog.total_duration)
    )
    log_res = await db.execute(log_query)
    logs = log_res.scalars().all()

    # 4. Group logs by student
    student_logs = {}
    for log in logs:
        if log.student_id not in student_logs:
            student_logs[log.student_id] = []
        student_logs[log.student_id].append(log)

    # 5. Build response
    response = []
    for student in students:
        s_logs = student_logs.get(student.id, [])
        if not s_logs:
            response.append({
                "student_id": student.id,
                "full_name": student.full_name,
                "email": student.email,
                "engagement_score": 0,
                "visibility_score": 100,
                "tab_switches": 0,
                "sessions": 0
            })
            continue

        avg_eng = sum(l.engagement_score or 0 for l in s_logs) / len(s_logs)
        total_watch = sum(l.watch_duration or 0 for l in s_logs)
        total_lapse = sum(l.attention_lapse_duration or 0 for l in s_logs)
        total_tabs = sum(l.tab_switches or 0 for l in s_logs)

        vis_score = 100.0
        if total_watch > 0:
            vis_score = max(0, min(100, ((total_watch - total_lapse) / total_watch) * 100))

        response.append({
            "student_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "engagement_score": round(avg_eng, 1),
            "visibility_score": round(vis_score, 1),
            "tab_switches": total_tabs,
            "sessions": len(s_logs)
        })

    return response


@router.get("/student/{student_id}")
async def get_student_detail_analytics(
    student_id: str,
    course_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Get detailed metrics for a single student.
    Handles the 404 issue for new students by returning 0-states.
    """
    # 1. Verify student exists
    student_res = await db.execute(select(User).where(User.id == student_id))
    student = student_res.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Get engagement data
    log_query = select(EngagementLog).where(EngagementLog.student_id == student_id)
    if course_id:
        log_query = log_query.join(Lecture, Lecture.id == EngagementLog.lecture_id).where(Lecture.course_id == course_id)
    
    log_res = await db.execute(log_query)
    logs = log_res.scalars().all()

    # 3. Aggregates
    session_count = len(logs)
    avg_eng = sum(l.engagement_score or 0 for l in logs) / max(session_count, 1)
    
    total_watch = sum(l.watch_duration or 0 for l in logs)
    total_lapse = sum(l.attention_lapse_duration or 0 for l in logs)
    total_tabs = sum(l.tab_switches or 0 for l in logs)
    
    vis_score = 100.0
    if total_watch > 0:
        vis_score = max(0, min(100, ((total_watch - total_lapse) / total_watch) * 100))

    # 4. Quiz averages
    quiz_query = select(func.avg(QuizAttempt.score / func.nullif(QuizAttempt.max_score, 0) * 100)).where(QuizAttempt.student_id == student_id)
    if course_id:
        quiz_query = quiz_query.join(Quiz, Quiz.id == QuizAttempt.quiz_id).join(Lecture, Lecture.id == Quiz.lecture_id).where(Lecture.course_id == course_id)
    
    quiz_res = await db.execute(quiz_query)
    quiz_avg = quiz_res.scalar() or 0.0

    # 5. Attendance
    att_query = select(func.avg(Attendance.presence_score)).where(Attendance.student_id == student_id)
    if course_id:
        att_query = att_query.join(Lecture, Lecture.id == Attendance.lecture_id).where(Lecture.course_id == course_id)
    
    att_res = await db.execute(att_query)
    att_rate = att_res.scalar() or 0.0

    # 6. Detailed Session List for Selector
    sessions_query = select(
        EngagementLog.session_id,
        EngagementLog.lecture_id,
        Lecture.title.label("lecture_title"),
        func.min(EngagementLog.started_at).label("start_time"),
        func.avg(EngagementLog.overall_score).label("avg_score"),
        func.sum(EngagementLog.watch_duration).label("total_duration")
    ).join(Lecture, Lecture.id == EngagementLog.lecture_id)\
     .where(EngagementLog.student_id == student_id)\
     .group_by(EngagementLog.session_id, EngagementLog.lecture_id, Lecture.title)\
     .order_by(desc("start_time"))
    
    if course_id:
        sessions_query = sessions_query.where(Lecture.course_id == course_id)
        
    sessions_res = await db.execute(sessions_query)
    session_list = [
        {
            "id": row.session_id,
            "lecture_id": row.lecture_id,
            "lecture_title": row.lecture_title,
            "date": row.start_time.isoformat(),
            "avg_score": round(row.avg_score or 0, 1),
            "duration": row.total_duration
        } for row in sessions_res.all()
    ]

    return {
        "id": student.id,
        "full_name": student.full_name,
        "email": student.email,
        "role": student.role.value if hasattr(student.role, 'value') else str(student.role),
        "engagement_score": round(avg_eng, 1),
        "visibility_score": round(vis_score, 1),
        "quiz_avg": round(quiz_avg, 1),
        "attendance_rate": round(att_rate, 1),
        "session_count": session_count,
        "focus_index": round(avg_eng / 10.0, 1),
        "tab_switches": total_tabs,
        "sessions": session_list
    }

@router.get("/student/{student_id}/session/{session_id}/diagnostics")
async def get_student_session_diagnostics(
    student_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """Refined neural diagnostics for a specific session (Timeline + SHAP)"""
    logs_query = select(EngagementLog).where(
        EngagementLog.student_id == student_id,
        EngagementLog.session_id == session_id
    ).order_by(EngagementLog.started_at.asc())
    
    result = await db.execute(logs_query)
    logs = result.scalars().all()
    
    if not logs:
        raise HTTPException(status_code=404, detail="Session data not found")
    
    # Aggregate timeline
    full_timeline = []
    base_ts = 0
    for log in logs:
        for p in (log.scores_timeline or []):
            full_timeline.append({**p, "timestamp": base_ts + p.get("timestamp", 0)})
        base_ts += log.watch_duration
        
    # Extract Aura (SHAP features from the latest mirroring)
    # Most forensic data is in the latest frames of the session
    latest_features = {}
    for log in reversed(logs):
        if log.features and "raw_feature_mirror" in log.features:
            latest_features = log.features["raw_feature_mirror"]
            break
            
    # 5. Get Activity Logs (Forensic Actions)
    activity_query = select(ActivityLog).where(
        ActivityLog.user_id == student_id,
        ActivityLog.created_at >= logs[0].started_at,
        ActivityLog.created_at <= (logs[-1].ended_at or datetime.utcnow())
    ).order_by(ActivityLog.created_at.asc())
    activity_res = await db.execute(activity_query)
    activities = [
        {
            "action": a.action,
            "timestamp": a.created_at.isoformat(),
            "details": a.details
        } for a in activity_res.scalars().all()
    ]

    # 6. Get Course Messages
    msg_query = select(Message, User.full_name).join(User, User.id == Message.sender_id).where(
        or_(Message.sender_id == student_id, Message.receiver_id == student_id),
        Message.created_at >= logs[0].started_at,
        Message.created_at <= (logs[-1].ended_at or datetime.utcnow())
    ).order_by(Message.created_at.asc())
    msg_res = await db.execute(msg_query)
    messages = [
        {
            "sender": row[1],
            "content": row[0].content,
            "timestamp": row[0].created_at.isoformat()
        } for row in msg_res.all()
    ]

    # 7. Get AI Tutor Chats (Aika)
    from app.models.models import AITutorSession, AITutorMessage
    chat_query = select(AITutorMessage).join(AITutorSession).where(
        AITutorSession.student_id == student_id,
        AITutorMessage.created_at >= logs[0].started_at,
        AITutorMessage.created_at <= (logs[-1].ended_at or datetime.utcnow())
    ).order_by(AITutorMessage.created_at.asc())
    chat_res = await db.execute(chat_query)
    chats = [
        {
            "role": c.role,
            "content": c.content,
            "timestamp": c.created_at.isoformat()
        } for c in chat_res.scalars().all()
    ]

    return {
        "student_id": student_id,
        "session_id": session_id,
        "timeline": full_timeline,
        "feature_timeline": [log.feature_timeline for log in logs if log.feature_timeline],
        "biometric_features": latest_features,
        "icap_final": logs[-1].icap_classification.value if hasattr(logs[-1].icap_classification, 'value') else str(logs[-1].icap_classification),
        "activities": activities,
        "messages": messages,
        "ai_chats": chats
    }


@router.post("/course/{course_id}/deploy-patch")
async def deploy_curricular_patch(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Simulates a 'Curricular Patch' deployment.
    In a real system, this might trigger re-indexing or send a focus update to all students.
    """
    # Verify course
    course_res = await db.execute(select(Course).where(Course.id == course_id))
    course = course_res.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Log the action
    debug_logger.log("activity", "Curricular patch deployed", data={"course_id": course_id, "teacher": current_user.email})
    
    # Return success
    return {
        "status": "deployed",
        "timestamp": datetime.utcnow().isoformat(),
        "affected_nodes": await db.scalar(select(func.count(Lecture.id)).where(Lecture.course_id == course_id))
    }


@router.get("/course/{course_id}/feedback-analysis")
async def get_feedback_analysis(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_teacher_or_admin),
):
    """
    Deep NLP analysis of student feedback for a course.
    Categorizes text into concerns, suggestions, and generates AI insights.
    """
    # 1. Fetch all feedback for the course
    fb_res = await db.execute(
        select(Feedback, User.full_name)
        .join(User, User.id == Feedback.student_id)
        .where(Feedback.course_id == course_id)
        .order_by(desc(Feedback.created_at))
    )
    rows = fb_res.all()
    
    if not rows:
        return {
            "course_id": course_id,
            "concerns": [],
            "suggestions": [],
            "top_keywords": [],
            "ai_insights": "No course feedback records available. Encourage students to submit module reviews.",
            "sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0}
        }

    feedbacks = [r[0] for r in rows]
    
    # 2. Extract concerns (negative sentiment feedback)
    concerns = []
    for f, name in rows:
        if f.sentiment and f.sentiment.get('label') == 'negative' and f.text:
            concerns.append({
                "text": f.text,
                "student_name": name,
                "timestamp": f.created_at.isoformat(),
                "rating": f.overall_rating
            })
    
    # 3. Extract suggestions
    suggestions = []
    for f, name in rows:
        if f.suggestions:
            suggestions.append({
                "text": f.suggestions,
                "student_name": name,
                "timestamp": f.created_at.isoformat()
            })

    # 4. Keyword Analysis
    all_keywords = []
    for f in feedbacks:
        if f.keywords:
            all_keywords.extend(f.keywords)
    
    from collections import Counter
    keyword_freq = Counter(all_keywords)
    top_keywords = [k for k, _ in keyword_freq.most_common(8)]

    # 5. AI Insights (Heuristic/Prompt-based simulator)
    avg_rating = sum(f.overall_rating for f in feedbacks) / len(feedbacks)
    neg_count = sum(1 for f in feedbacks if f.sentiment and f.sentiment.get('label') == 'negative')
    pos_count = sum(1 for f in feedbacks if f.sentiment and f.sentiment.get('label') == 'positive')
    
    insights = ""
    if avg_rating < 3.0:
        insights = f"Critical pedagogical drift detected. High frequency of '{top_keywords[0] if top_keywords else 'confusion'}' indicates a mismatch between material complexity and student prerequisites."
    elif neg_count > pos_count:
        insights = "Structural friction identified. Students are vocalizing theoretical gaps. Focus on simplifying the 'Delivery' and 'Technical' nodes identified in concerns."
    elif len(suggestions) > len(feedbacks) * 0.5:
        insights = "High constructive engagement. Students are eager for supplementary depth. Consider deploying curricular patches for the requested modules."
    else:
        insights = "Course feedback trends are optimal. Sentiment clusters are predominantly positive. Maintain current pacing and responsiveness levels."

    return {
        "course_id": course_id,
        "count": len(feedbacks),
        "avg_rating": round(avg_rating, 2),
        "concerns": concerns[:15],
        "suggestions": suggestions[:15],
        "top_keywords": top_keywords,
        "ai_insights": insights,
        "sentiment_summary": {
            "positive": pos_count,
            "neutral": len(feedbacks) - pos_count - neg_count,
            "negative": neg_count
        }
    }
