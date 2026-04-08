"""
Smart LMS - Feedback Router
Post-lecture feedback submission with NLP analysis
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import string
import re
from app.database import get_db
from app.models.models import User, UserRole, Feedback, Lecture
from app.middleware.auth import get_current_user
from app.services.debug_logger import debug_logger
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

router = APIRouter(prefix="/api/feedback", tags=["Feedback"])
analyzer = SentimentIntensityAnalyzer()

class FeedbackSubmit(BaseModel):
    lecture_id: str
    course_id: str
    overall_rating: int = Field(..., ge=1, le=5)
    content_quality: Optional[int] = Field(None, ge=1, le=5)
    teaching_clarity: Optional[int] = Field(None, ge=1, le=5)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    text: Optional[str] = None
    suggestions: Optional[str] = None

class FeedbackResponse(BaseModel):
    id: str
    student_id: str
    lecture_id: str
    course_id: str
    overall_rating: int
    content_quality: Optional[int]
    teaching_clarity: Optional[int]
    difficulty_level: Optional[int]
    text: Optional[str]
    suggestions: Optional[str]
    sentiment: Optional[Dict[str, Any]]
    emotions: Optional[Dict[str, float]]
    keywords: Optional[List[str]]
    themes: Optional[List[str]]
    aspects: Optional[Dict[str, str]]
    created_at: datetime

    class Config:
        from_attributes = True

def analyze_emotions(text: str) -> Dict[str, float]:
    """Map text to core learning emotions"""
    text = text.lower()
    emotion_map = {
        "joy": ["great", "happy", "excellent", "love", "awesome", "perfect", "clear", "enjoyed", "best"],
        "anger": ["hate", "bad", "terrible", "worst", "annoying", "frustrated", "useless", "broken"],
        "sadness": ["boring", "long", "tired", "slow", "hard", "difficult", "too much", "unhappy"],
        "fear": ["scared", "confused", "lost", "don't know", "worry", "stress", "anxious", "overwhelmed"],
        "confusion": ["what", "huh", "unclear", "vague", "misleading", "messy", "jumbled", "didn't explain"],
    }
    
    results = {emo: 0.0 for emo in emotion_map}
    words = text.split()
    if not words: return results
    
    for emotion, keywords in emotion_map.items():
        count = sum(1 for word in words if any(k in word for k in keywords))
        results[emotion] = round(min(1.0, count / (len(words) * 0.2 + 1)), 2)
    
    return results

def analyze_aspects(text: str) -> Dict[str, str]:
    """Aspect-based sentiment analysis simplified"""
    text = text.lower()
    aspects = {
        "content": ["topic", "subject", "material", "slides", "lesson", "content", "knowledge"],
        "delivery": ["voice", "audio", "explanation", "speed", "talking", "teaching", "style"],
        "technical": ["video", "sound", "platform", "website", "lag", "ui", "ux", "connection"],
        "pacing": ["time", "fast", "slow", "break", "duration", "hours", "minutes"],
    }
    
    detected = {}
    for aspect, keywords in aspects.items():
        if any(k in text for k in keywords):
            # Simple local sentiment check
            local_scores = analyzer.polarity_scores(text)
            if local_scores['compound'] > 0.1: detected[aspect] = "positive"
            elif local_scores['compound'] < -0.1: detected[aspect] = "negative"
            else: detected[aspect] = "neutral"
            
    return detected

def analyze_sentiment_advanced(text: str) -> Dict[str, Any]:
    if not text:
        return {"label": "neutral", "positive": 0.0, "negative": 0.0, "neutral": 1.0}
    scores = analyzer.polarity_scores(text)
    compound = scores['compound']
    label = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
    return {
        "label": label,
        "positive": round(scores['pos'], 3),
        "negative": round(scores['neg'], 3),
        "neutral": round(scores['neu'], 3),
        "compound": round(compound, 3)
    }

def extract_keywords_advanced(text: str) -> List[str]:
    if not text: return []
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of", "in", "for", "on", "with"}
    words = re.findall(r'\w+', text.lower())
    filtered = [w for w in words if w not in stop_words and len(w) > 3]
    freq = {}
    for w in filtered: freq[w] = freq.get(w, 0) + 1
    return sorted(freq, key=freq.get, reverse=True)[:8]

@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    request: FeedbackSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    combined_text = f"{request.text or ''} {request.suggestions or ''}".strip()
    sentiment = analyze_sentiment_advanced(combined_text)
    keywords = extract_keywords_advanced(combined_text)
    emotions = analyze_emotions(combined_text)
    aspects = analyze_aspects(combined_text)

    feedback = Feedback(
        student_id=current_user.id,
        lecture_id=request.lecture_id,
        course_id=request.course_id,
        overall_rating=request.overall_rating,
        content_quality=request.content_quality,
        teaching_clarity=request.teaching_clarity,
        difficulty_level=request.difficulty_level,
        text=request.text,
        suggestions=request.suggestions,
        sentiment=sentiment,
        keywords=keywords,
        emotions=emotions,
        # themes was in model before, adding aspects to dynamic dict if needed or use themes
        themes=list(aspects.keys()), 
    )
    # Note: If database model doesn't have 'aspects' specifically, we store in themes or as part of sentiment dict
    # Update: Models usually have 'emotions' as JSON based on previous analysis.
    
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    debug_logger.log("activity",
                     f"Advanced NLP Feedback: rating={request.overall_rating}, top_emotion={max(emotions, key=emotions.get)}",
                     user_id=current_user.id)

    resp = FeedbackResponse.model_validate(feedback)
    resp.aspects = aspects
    return resp

@router.get("/lecture/{lecture_id}", response_model=List[FeedbackResponse])
async def get_lecture_feedback(
    lecture_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Feedback).where(Feedback.lecture_id == lecture_id)
    if current_user.role == UserRole.STUDENT:
        query = query.where(Feedback.student_id == current_user.id)
    result = await db.execute(query.order_by(Feedback.created_at.desc()))
    feedbacks = result.scalars().all()
    return [FeedbackResponse.model_validate(f) for f in feedbacks]

@router.get("/course/{course_id}")
async def get_course_feedback_summary(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Feedback).where(Feedback.course_id == course_id))
    feedbacks = result.scalars().all()
    if not feedbacks: return {"course_id": course_id, "count": 0, "avg_rating": 0}

    # Aggregate emotions
    total_emotions = {"joy": 0.0, "anger": 0.0, "sadness": 0.0, "fear": 0.0, "confusion": 0.0}
    for f in feedbacks:
        if f.emotions:
            for k, v in f.emotions.items(): total_emotions[k] += v
    
    avg_emotions = {k: round(v / len(feedbacks), 2) for k, v in total_emotions.items()}

    return {
        "course_id": course_id,
        "count": len(feedbacks),
        "avg_rating": round(sum(f.overall_rating for f in feedbacks) / len(feedbacks), 1),
        "dominant_emotion": max(avg_emotions, key=avg_emotions.get),
        "emotion_profile": avg_emotions,
        "all_keywords": list(set(k for f in feedbacks if f.keywords for k in f.keywords))[:20],
    }
