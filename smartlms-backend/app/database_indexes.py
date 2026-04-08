"""
Runtime index bootstrap for existing databases.

This complements model-level __table_args__ indexes by ensuring critical
indexes exist even when tables were created before index declarations.
"""

from sqlalchemy import text
from app.database import engine


INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_course_teacher ON courses (teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_course_published_created ON courses (is_published, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_lecture_course_order ON lectures (course_id, order_index)",
    "CREATE INDEX IF NOT EXISTS idx_lecture_course_published ON lectures (course_id, is_published)",
    "CREATE INDEX IF NOT EXISTS idx_material_course_created ON materials (course_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_material_lecture ON materials (lecture_id)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_lecture_published ON quizzes (lecture_id, is_published)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_created ON quizzes (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_attempt_student_completed ON quiz_attempts (student_id, completed_at)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_attempt_quiz_student ON quiz_attempts (quiz_id, student_id)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_course_created ON feedbacks (course_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_student_lecture ON feedbacks (student_id, lecture_id)",
    "CREATE INDEX IF NOT EXISTS idx_teaching_score_teacher_calculated ON teaching_scores (teacher_id, calculated_at)",
    "CREATE INDEX IF NOT EXISTS idx_teaching_score_course_calculated ON teaching_scores (course_id, calculated_at)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_lecture_student ON attendance (lecture_id, student_id)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_student_joined ON attendance (student_id, joined_at)",
    "CREATE INDEX IF NOT EXISTS idx_notification_user_read_created ON notifications (user_id, is_read, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_notification_sender ON notifications (sender_id)",
    "CREATE INDEX IF NOT EXISTS idx_icap_student_created ON icap_logs (student_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_icap_lecture_created ON icap_logs (lecture_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_message_conversation_created ON messages (sender_id, receiver_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_ai_tutor_session_student_updated ON ai_tutor_sessions (student_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_ai_tutor_message_session_created ON ai_tutor_messages (session_id, created_at)",
]


async def ensure_performance_indexes() -> None:
    """Create high-value indexes if missing on existing deployments."""
    async with engine.begin() as conn:
        for stmt in INDEX_STATEMENTS:
            await conn.execute(text(stmt))
