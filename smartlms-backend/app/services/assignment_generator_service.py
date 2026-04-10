"""
Smart LMS - Assignment Generator Service
AI-powered assignment generation with subject-aware branching.
Supports Technical (Coding) and Descriptive (Humanities/Languages) modes.
"""

import json
import re
from typing import List, Dict, Optional
from app.config import settings
from app.services.groq_fallback import chat_completion_with_fallback
from app.services.summary_service import summary_service
from app.services.debug_logger import debug_logger

ASSIGNMENT_PROMPT = """You are an expert academic curriculum designer. Generate a high-fidelity assignment based on the provided Lecture Content.

SUBJECT CONTEXT: {subject_type}
DIFFICULTY: {difficulty}

LECTURE CONTENT:
{content}

CORE DIRECTIVES:
1. STRUCTURE: The assignment MUST follow this 3-tier Forensic Review format:
   - STAGE 1: NEURAL WARMUP (Foundational recall and base concepts).
   - STAGE 2: COGNITIVE DEEP DIVE (Analytical questions, application of theory).
   - STAGE 3: INDUSTRY PULSE (Real-world scenario or a "Future-Proof" challenge).

2. SUBJECT BRANCHING:
   {branching_instructions}

3. TONE: Use a precise, academic, yet "Bold Tech" tone (Neural context, Forensic analysis, Systemic review).

4. FORMAT: Return a JSON object with:
   {{
     "title": "...",
     "description": "...",
     "questions": [
        {{ "question": "...", "points": 10, "type": "...", "suggested_answer_key": "..." }}
     ],
     "max_score": 100
   }}

Output ONLY the JSON object. No markdown blocks.
"""

TECHNICAL_BRANCHING = """
- For this TECHNICAL assignment, you MUST include:
  - At least 2 actual CODING EXERCISES (Python/Data Science focused).
  - Use markdown code blocks (```python) inside the question text.
  - One debugging task where the student must find a logic error.
  - One algorithmic complexity analysis question.
"""

DESCRIPTIVE_BRANCHING = """
- For this LANGUAGES/HUMANITIES assignment, you MUST include:
  - Long-form descriptive prompts requiring textual analysis.
  - A creative synthesis task based on the lecture theme.
  - A comparative analysis question involving external pedagogical concepts.
"""

async def generate_assignment(
    content: str,
    subject_type: str = "technical", # technical, descriptive
    difficulty: str = "medium"
) -> Dict:
    """Generate a subject-aware assignment using Groq AI"""
    if not settings.GROQ_API_KEY:
        raise Exception("Groq API key not configured")

    try:
        # Pre-process content (summarize if extremely long)
        processed_content = content
        if len(content.split()) > 1000:
            debug_logger.log("activity", "Summarizing long content for assignment generation...")
            processed_content = await summary_service.summarize_transcript(content, max_words=1200)

        branching = TECHNICAL_BRANCHING if subject_type.lower() == "technical" else DESCRIPTIVE_BRANCHING
        
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        prompt = ASSIGNMENT_PROMPT.format(
            subject_type=subject_type.upper(),
            difficulty=difficulty,
            content=processed_content,
            branching_instructions=branching
        )

        model_chain = settings.groq_chat_models_for_task(
            task="assignment_generation",
            primary_model="llama-3.3-70b-versatile",
        )

        response, _ = await chat_completion_with_fallback(
            client,
            primary_model=model_chain[0],
            fallback_models=model_chain[1:],
            messages=[
                {"role": "system", "content": "You are a precise curriculum generator. Output ONLY a valid JSON object."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4000
        )

        raw_content = response.choices[0].message.content.strip()
        
        # JSON extraction
        if "```" in raw_content:
            raw_content = re.sub(r"```(json)?", "", raw_content).split("```")[0].strip()
        
        assignment_data = json.loads(raw_content)
        
        # Ensure title and description are present
        if "title" not in assignment_data: assignment_data["title"] = "AI Generated Assignment"
        if "description" not in assignment_data: assignment_data["description"] = "Generated from lecture context."
        
        return assignment_data

    except Exception as e:
        debug_logger.log("error", f"Assignment generation failed: {str(e)}")
        raise Exception(f"AI Assignment generation failed: {str(e)}")
