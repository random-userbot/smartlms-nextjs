from sqlalchemy import Column, String, Float, Text, JSON, Enum as SQLEnum, DateTime, Integer
from datetime import datetime
import enum
from .database import Base

class EngagementStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ICAPLevel(str, enum.Enum):
    INTERACTIVE = "interactive"
    CONSTRUCTIVE = "constructive"
    ACTIVE = "active"
    PASSIVE = "passive"

class EngagementLog(Base):
    __tablename__ = "engagement_logs"

    id = Column(String, primary_key=True)
    student_id = Column(String)
    lecture_id = Column(String)
    session_id = Column(String)
    
    # Status
    status = Column(SQLEnum(EngagementStatus, native_enum=False, length=50), default=EngagementStatus.PROCESSING)
    error_message = Column(Text, nullable=True)

    # Scores
    overall_score = Column(Float, nullable=True)
    boredom_score = Column(Float, nullable=True)
    engagement_score = Column(Float, nullable=True)
    confusion_score = Column(Float, nullable=True)
    frustration_score = Column(Float, nullable=True)

    # Feature data
    features = Column(JSON, nullable=True)
    scores_timeline = Column(JSON, nullable=True)
    shap_explanations = Column(JSON, nullable=True)

    # Prediction
    forecast_score = Column(Float, nullable=True)
    actual_vs_forecast_error = Column(Float, nullable=True)

    # ICAP
    icap_classification = Column(SQLEnum(ICAPLevel, native_enum=False, length=50), nullable=True)
    icap_evidence = Column(JSON, nullable=True)

    # Metadata
    watch_duration = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
