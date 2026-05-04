"""
Smart LMS - AI Tutor Router
Multimodal language practice and conversational tutoring via Groq LLaMA
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
import json
import asyncio
from groq import AsyncGroq

from app.database import get_db, async_session
from app.models.models import (
    User, AITutorSession, AITutorMessage, Lecture, 
    EngagementLog, QuizAttempt, ICAPLog, ActivityLog, ICAPLevel
)
from app.middleware.auth import get_current_user
from app.config import settings
from app.services.debug_logger import debug_logger
from app.services.groq_fallback import AllModelsRateLimitedError, chat_completion_with_fallback
from app.services.icap_service import map_action_to_icap, get_action_evidence
from sqlalchemy import select, func, desc, delete

router = APIRouter(prefix="/api/tutor", tags=["AI Tutor"])

class ChatMessage(BaseModel):
    role: str
    content: str

class TutorChatRequest(BaseModel):
    messages: List[ChatMessage]
    mode: str = "general" # general, language_practice, grammar_check
    target_language: Optional[str] = None # e.g. "Spanish"
    lecture_id: Optional[str] = None # Context-aware tutoring
    session_id: Optional[str] = None # To append to existing DB session
    preferred_model: Optional[str] = None # Explicit model override from UI
    attachments: Optional[List[Dict[str, str]]] = None # [{type: "image", data: "base64..."}]

SYSTEM_PROMPTS = {
    "general": "You are a friendly, encouraging, and highly knowledgeable AI Tutor for the Smart LMS. Explain concepts clearly using the socratic method when appropriate.",
    "language_practice": "You are a native-speaking language exchange partner. The user wants to practice {target_language}. Keep responses conversational, natural, and relatively brief to mimic real chat. Gently correct major errors without breaking the flow.",
    "grammar_check": "You are a strict but helpful grammar teacher for {target_language}. Analyze the user's latest message, point out any grammar/spelling errors, explain why they are wrong, and provide the correct version.",
    "speaking": "You are a specialized vocal coach. Help the student improve their pronunciation and verbal confidence. Provide feedback on how to phase sentences more naturally.",
    "listening": "You are a comprehension expert. Summarize key points from the lecture and ask the student specific questions to test their auditory retention.",
    "conversing": "You are a peer learning buddy. Engage in deep, open-ended discussions about the lecture's implications. Challenge the student's perspectives constructively."
}

MODEL_ALIASES = {
    "groq-llama-3": "llama-3.3-70b-versatile",
    "groq-mixtral": "mixtral-8x7b-32768",
    "groq-gemma2": "gemma2-9b-it",
    "groq-llama-3.1-8b": "llama-3.1-8b-instant",
    # Legacy UI aliases mapped to available Groq models.
    "gemini-1.5-pro": "mixtral-8x7b-32768",
    "gpt-4o": "llama-3.3-70b-versatile",
}

@router.get("/sessions")
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all tutoring sessions for the user"""
    result = await db.execute(
        select(AITutorSession)
        .where(AITutorSession.student_id == current_user.id)
        .order_by(desc(AITutorSession.updated_at))
    )
    return result.scalars().all()

@router.post("/sessions")
async def create_session(
    title: str = "New Session",
    mode: str = "general",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new tutoring session"""
    session = AITutorSession(student_id=current_user.id, title=title, mode=mode)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get messages for a specific session"""
    result = await db.execute(
        select(AITutorSession).where(AITutorSession.id == session_id, AITutorSession.student_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = await db.execute(
        select(AITutorMessage)
        .where(AITutorMessage.session_id == session_id)
        .order_by(AITutorMessage.created_at.asc())
    )
    return messages.scalars().all()

@router.delete("/sessions/{session_id}/clear")
async def clear_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all messages from a session"""
    result = await db.execute(
        select(AITutorSession).where(AITutorSession.id == session_id, AITutorSession.student_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")
        
    await db.execute(delete(AITutorMessage).where(AITutorMessage.session_id == session_id))
    await db.commit()
    return {"message": "Session cleared"}

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific message"""
    result = await db.execute(
        select(AITutorMessage)
        .join(AITutorSession, AITutorMessage.session_id == AITutorSession.id)
        .where(AITutorMessage.id == message_id, AITutorSession.student_id == current_user.id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    await db.delete(msg)
    await db.commit()
    return {"message": "Message deleted"}

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a specific session"""
    result = await db.execute(
        select(AITutorSession).where(AITutorSession.id == session_id, AITutorSession.student_id == current_user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": "Session deleted"}

@router.post("/chat")
async def chat_with_tutor(
    request: TutorChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a chat response from the AI tutor"""
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key not configured")

    try:
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        session = None
        if request.session_id:
            session_res = await db.execute(
                select(AITutorSession).where(
                    AITutorSession.id == request.session_id,
                    AITutorSession.student_id == current_user.id,
                )
            )
            session = session_res.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # Determine system prompt
        sys_prompt_template = SYSTEM_PROMPTS.get(request.mode, SYSTEM_PROMPTS["general"])
        sys_prompt = sys_prompt_template.replace("{target_language}", request.target_language or "the language")
        
        # Deep Context: Fetch Student History
        
        # Get avg engagement
        avg_eng_res = await db.execute(select(func.avg(EngagementLog.engagement_score)).where(EngagementLog.student_id == current_user.id))
        avg_eng = avg_eng_res.scalar() or 50.0
        
        # Get latest ICAP
        icap_res = await db.execute(select(ICAPLog.classification).where(ICAPLog.student_id == current_user.id).order_by(ICAPLog.created_at.desc()).limit(1))
        latest_icap = icap_res.scalar() or "passive"
        
        # Get avg quiz
        quiz_res = await db.execute(select(func.avg(QuizAttempt.score / QuizAttempt.max_score)).where(QuizAttempt.student_id == current_user.id, QuizAttempt.max_score > 0))
        avg_quiz = (quiz_res.scalar() or 0.0) * 100
        
        sys_prompt += f"\n\nStudent Deep Context:\n- Average Engagement: {avg_eng:.1f}%\n- Recent Learning State (ICAP): {latest_icap.upper()}\n- Average Quiz Score: {avg_quiz:.1f}%\n"
        sys_prompt += "Use this context to adapt your teaching style. If engagement is low or state is passive, be more interactive and engaging. If quiz scores are low, break down concepts simpler."
        
        # Make context-aware if lecture_id provided
        if request.lecture_id:
            result = await db.execute(select(Lecture).where(Lecture.id == request.lecture_id))
            lecture = result.scalar_one_or_none()
            if lecture and lecture.transcript:
                sys_prompt += f"\n\nCurrent Lecture Transcript Context ('{lecture.title}'):\n{lecture.transcript[:4000]}...\n\nCRITICAL: The transcript might be in a different language. Native parse it, but always converse with the student in their preferred language, explaining the concepts clearly."
        
        # Intelligent Model Routing based on use case
        model_name = "llama-3.3-70b-versatile" # Default robust model
        if request.mode == "general":
            model_name = "llama-3.3-70b-versatile" 
        elif request.mode == "language_practice":
            model_name = "mixtral-8x7b-32768" 
        elif request.mode == "grammar_check":
            model_name = "gemma2-9b-it" 

        if request.preferred_model:
            model_name = MODEL_ALIASES.get(request.preferred_model, request.preferred_model)

        model_chain = settings.groq_chat_models_for_task(
            task=f"tutor_{request.mode}",
            primary_model=model_name,
        )
        model_name = model_chain[0]
        fallback_models = model_chain[1:]

        
        messages = [{"role": "system", "content": sys_prompt}]
        for msg in request.messages[-10:]: # Keep last 10 messages for context window
            # If msg has attachments, we'd handle multi-modal formatting here for Groq
            # For now, we append a notice if attachments were sent
            content = msg.content
            if request.attachments and msg.role == "user" and msg == request.messages[-1]:
                content += f"\n\n[Attached {len(request.attachments)} files/images]"
            messages.append({"role": msg.role, "content": content})

        # Pre-save the user message to DB if session exists
        if request.session_id and request.messages:
            user_msg = request.messages[-1]
            if user_msg.role == "user":
                db_msg = AITutorMessage(session_id=request.session_id, role="user", content=user_msg.content)
                db.add(db_msg)
                # optionally update session title if it's new
                if session and session.title == "New Session" and len(request.messages) <= 2:
                    session.title = user_msg.content[:50] + "..." if len(user_msg.content) > 50 else user_msg.content
                
                # Log as ICAP activity
                action = "ai_chat"
                icap_level = map_action_to_icap(action)
                log = ActivityLog(
                    user_id=current_user.id,
                    action=action,
                    details={
                        "session_id": request.session_id,
                        "lecture_id": request.lecture_id,
                        "mode": request.mode,
                        "icap_level": icap_level.value if icap_level else None,
                        "evidence_summary": get_action_evidence(action, {"content": user_msg.content})
                    }
                )
                db.add(log)
                await db.commit()

        async def generate_response():
            full_content = ""
            try:
                stream, used_model = await chat_completion_with_fallback(
                    client,
                    primary_model=model_name,
                    fallback_models=fallback_models,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                    stream=True,
                    retries_per_model=settings.GROQ_MODEL_RETRIES_PER_MODEL,
                    retry_base_seconds=settings.GROQ_MODEL_RETRY_BASE_SECONDS,
                    retry_max_seconds=settings.GROQ_MODEL_RETRY_MAX_SECONDS,
                )
                if used_model != model_name:
                    debug_logger.log("activity", f"Tutor model fallback engaged: {model_name} -> {used_model}", user_id=current_user.id)
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_content += content
                        yield content
            except AllModelsRateLimitedError as e:
                debug_logger.log("warning", f"Tutor all-models-rate-limited: {str(e)}", user_id=current_user.id)
                yield "\n\n[All tutor models are currently rate-limited. Please retry shortly.]"
            except Exception as e:
                debug_logger.log("error", f"Tutor streaming error: {str(e)}")
                yield f"\n\n[Error communicating with AI Tutor: {str(e)}]"
            finally:
                if request.session_id and full_content:
                    async with async_session() as db_session:
                        msg = AITutorMessage(session_id=request.session_id, role="assistant", content=full_content)
                        db_session.add(msg)
                        
                        # Update session updated_at timestamp
                        session_res = await db_session.execute(select(AITutorSession).where(AITutorSession.id == request.session_id))
                        session = session_res.scalar_one_or_none()
                        if session:
                            session.updated_at = func.now()
                            
                        await db_session.commit()

        debug_logger.log("activity", f"AI Tutor chat ({request.mode}) initiated", user_id=current_user.id)
        
        return StreamingResponse(
            generate_response(), 
            media_type="text/event-stream"
        )
        
    except Exception as e:
        debug_logger.log("error", f"Tutor initiation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
