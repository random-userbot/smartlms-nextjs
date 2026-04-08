"""
Smart LMS - Quiz Generator Service
AI-powered quiz generation with cognitive summarization and internet-augmented research.
"""

from typing import List, Dict, Optional
import asyncio
import json
import re
import urllib.parse
from app.config import settings
from app.services.groq_fallback import AllModelsRateLimitedError, chat_completion_with_fallback
from app.services.summary_service import summary_service
from app.services.internet_service import internet_service
from app.services.debug_logger import debug_logger

QUIZ_GENERATION_PROMPT = """You are an educational quiz generator. Generate {num_questions} quiz questions based on the provided Lecture Content and External Research.

Core Directives:
1. SOURCE INTEGRATION: Use the primary Lecture Content for approximately 70% of questions and the External Research for 30% of questions to provide "Related Context" that goes beyond the classroom material.
2. ICAP TAXONOMY:
   - Passive (P): Basic recall of facts or definitions.
   - Active (A): Explaining relationships or summarizing concepts.
   - Constructive (C): Real-world application or problem solving based on theory.
   - Interactive (I): Critical analysis or evaluating different viewpoints.
3. DIVERSITY: Mix MCQ, True/False, and Short Answer.
4. LANGUAGE: Always output in English.

Difficulty Level: {difficulty}

Lecture Content (Summary):
{transcript_summary}

External Research / Related Context:
{external_context}

Output as a strict JSON array with NO markdown wrapping:
[
  {{
    "type": "mcq|true_false|short_answer",
    "question": "...",
    "options": ["A", "B", "C", "D"], // only for mcq
    "correct_answer": "...",
    "points": 1,
    "icap_level": "passive|active|constructive|interactive",
    "explanation": "..."
  }}
]
"""

async def generate_quiz_questions(
    transcript: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    include_icap: bool = True,
) -> List[Dict]:
    """Generate quiz questions using AI + External Research"""
    if not settings.GROQ_API_KEY:
        raise Exception("Groq API key not configured")

    try:
        # Step 1: Cognitive Summarization (Pre-processing)
        # If transcript is large, we summarize it to fit better in context and focus the AI
        transcript_summary = transcript
        if len(transcript.split()) > 400:
             debug_logger.log("activity", f"Summarizing long transcript for quiz generation...")
             transcript_summary = await summary_service.summarize_transcript(transcript, max_words=800)

        # Step 2: External Research (Internet Augmentation)
        # Extract keywords for search
        search_query = transcript[:150] # Heuristic
        debug_logger.log("activity", f"Searching internet for: {search_query}")
        external_context = await internet_service.search_related_context(search_query)

        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        prompt = QUIZ_GENERATION_PROMPT.format(
            num_questions=num_questions,
            difficulty=difficulty,
            transcript_summary=transcript_summary,
            external_context=external_context
        )

        model_chain = settings.groq_chat_models_for_task(
            task="quiz_generation",
            primary_model="llama-3.3-70b-versatile",
        )

        response, used_model = await chat_completion_with_fallback(
            client,
            primary_model=model_chain[0],
            fallback_models=model_chain[1:],
            messages=[
                {"role": "system", "content": "You are a precise educational quiz generator. Output ONLY a valid JSON array. No markdown blocks."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=4000
        )

        content = response.choices[0].message.content.strip()
        
        # Simple JSON extraction
        if "```" in content:
            content = re.sub(r"```(json)?", "", content).split("```")[0].strip()
        
        questions = json.loads(content)

        # Post-process and ensure integrity
        valid_questions = []
        for q in questions:
            if "question" in q and "correct_answer" in q:
                valid_questions.append({
                    "type": q.get("type", "mcq"),
                    "question": q["question"],
                    "options": q.get("options", []),
                    "correct_answer": q["correct_answer"],
                    "points": q.get("points", 1),
                    "icap_level": q.get("icap_level", "active"),
                    "explanation": q.get("explanation", ""),
                })

        return valid_questions

    except Exception as e:
        debug_logger.log("error", f"Advanced quiz generation failed: {str(e)}")
        raise Exception(f"Quiz generation failed: {str(e)}")

async def refine_quiz_questions(
    transcript: str,
    current_questions: List[Dict],
    feedback: str
) -> List[Dict]:
    """Refine generated quiz questions based on teacher feedback"""
    if not settings.GROQ_API_KEY:
        raise Exception("Groq API key not configured")

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        prompt = f"""You are an educational quiz generator. The teacher has requested changes:
        
Feedback: "{feedback}"
Current Questions: {json.dumps(current_questions, indent=2)}
Source: {transcript[:4000]}

Modify or add new questions as requested. Maintain the same JSON format.
"""

        model_chain = settings.groq_chat_models_for_task(
            task="quiz_refinement",
            primary_model="llama-3.3-70b-versatile",
        )

        response, _ = await chat_completion_with_fallback(
            client,
            primary_model=model_chain[0],
            fallback_models=model_chain[1:],
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON array."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=4000
        )

        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = re.sub(r"```(json)?", "", content).split("```")[0].strip()
        
        return json.loads(content)

    except Exception as e:
        debug_logger.log("error", f"Quiz refinement failed: {str(e)}")
        raise Exception(f"Quiz refinement failed: {str(e)}")
