"""
Smart LMS - Summary Service
Processes long transcripts into concise, high-impact cognitive summaries.
"""

from typing import List, Optional
import json
import re
from groq import AsyncGroq
from app.config import settings
from app.services.debug_logger import debug_logger
from app.services.groq_fallback import chat_completion_with_fallback

class SummaryService:
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

    async def summarize_transcript(self, transcript: str, max_words: int = 300) -> str:
        """Summarize a transcript using Groq. Handles long texts by chunking if necessary."""
        if not self.client or not transcript:
            return "Summary unavailable: No AI client or transcript provided."

        # If transcript is very long (> 6000 words), summarize in chunks
        words = transcript.split()
        if len(words) > 6000:
            return await self._summarize_in_chunks(transcript, max_words)
        
        try:
            model_chain = settings.groq_chat_models_for_task(
                task="tutor_general",
                primary_model="llama-3.3-70b-versatile"
            )

            response, _ = await chat_completion_with_fallback(
                self.client,
                primary_model=model_chain[0],
                fallback_models=model_chain[1:],
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are an expert academic summarizer. Provide a concise, high-impact summary of the following lecture in approximately {max_words} words. Focus on key concepts, architectural diagrams described, and core takeaways."
                    },
                    {"role": "user", "content": transcript}
                ],
                temperature=0.3,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            debug_logger.log("error", f"Summarization failed: {str(e)}")
            return "Summarization failed due to technical frequency shift. Please try again."

    async def _summarize_in_chunks(self, transcript: str, max_words: int) -> str:
        """Chunked summarization for very long lectures."""
        words = transcript.split()
        chunk_size = 4000
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            try:
                res, _ = await chat_completion_with_fallback(
                    self.client,
                    primary_model="llama-3.1-8b-instant", # Use faster model for sub-chunks
                    fallback_models=["mixtral-8x7b-32768"],
                    messages=[
                        {"role": "system", "content": f"Summarize this part ({i+1}/{len(chunks)}) of a long lecture. Focus on the main technical points."},
                        {"role": "user", "content": chunk}
                    ],
                    max_tokens=300
                )
                chunk_summaries.append(res.choices[0].message.content.strip())
            except:
                continue

        combined = "\n\n".join(chunk_summaries)
        return await self.summarize_transcript(combined, max_words)

summary_service = SummaryService()
