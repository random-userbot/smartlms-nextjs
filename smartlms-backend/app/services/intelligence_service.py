"""
Smart LMS - Intelligence Service (Cognitive Friction Analysis)
Correlates engagement telemetry with pedagogical content to identify struggle zones.
"""

import json
import re
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from groq import AsyncGroq
from app.config import settings
from app.models.models import EngagementLog, Lecture, Material
from app.services.debug_logger import debug_logger
from app.services.groq_fallback import chat_completion_with_fallback

class IntelligenceService:
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

    async def get_lecture_intelligence(self, db: AsyncSession, lecture_id: str) -> Dict:
        """
        Main entry point for generating lecture-level pedagogical intelligence.
        """
        # 1. Fetch Lecture and Transcripts
        lecture_result = await db.execute(select(Lecture).where(Lecture.id == lecture_id))
        lecture = lecture_result.scalar_one_or_none()
        if not lecture:
            return {"error": "Lecture not found"}

        # 2. Fetch all student engagement timelines for this lecture
        logs_result = await db.execute(
            select(EngagementLog).where(EngagementLog.lecture_id == lecture_id)
        )
        logs = logs_result.scalars().all()
        
        if not logs:
            return {
                "lecture_id": lecture_id,
                "status": "insufficient_data",
                "message": "No engagement data recorded for this lecture yet."
            }

        # 3. Aggregate Timelines (Compute Friction Zones)
        aggregated_timeline = self._aggregate_timelines(logs)
        friction_zones = self._detect_friction_zones(aggregated_timeline)

        # 4. Map Friction Zones to Topics (AI Analysis)
        intelligence = await self._analyze_content_friction(lecture, friction_zones)

        return {
            "lecture_id": lecture_id,
            "lecture_title": lecture.title,
            "total_students": len(logs),
            "transcript": lecture.transcript,
            "friction_zones": friction_zones,
            "topic_analysis": intelligence.get("topics", []),
            "recommendations": intelligence.get("recommendations", []),
            "overall_sentiment": intelligence.get("overall_sentiment", "Neutral")
        }

    def _aggregate_timelines(self, logs: List[EngagementLog]) -> Dict[int, List[float]]:
        """Group engagement scores by second (or minute)."""
        aggregated = {} # timestamp (sec) -> list of scores
        for log in logs:
            timeline = log.scores_timeline
            if isinstance(timeline, str):
                try: timeline = json.loads(timeline)
                except: continue
            
            if not isinstance(timeline, list): continue

            for point in timeline:
                ts = int(point.get('timestamp', 0))
                score = float(point.get('engagement', 50))
                # Bin by 10-second intervals to smooth data
                interval = (ts // 10) * 10
                if interval not in aggregated:
                    aggregated[interval] = []
                aggregated[interval].append(score)
        
        # Calculate mean for each interval
        final_timeline = {ts: sum(scores)/len(scores) for ts, scores in aggregated.items()}
        return final_timeline

    def _detect_friction_zones(self, timeline: Dict[int, float]) -> List[Dict]:
        """Identify intervals where engagement is significantly below class average."""
        if not timeline: return []
        
        avg_class_engagement = sum(timeline.values()) / len(timeline)
        threshold = avg_class_engagement * 0.8 # 20% below average
        
        sorted_ts = sorted(timeline.keys())
        friction_zones = []
        current_zone = None

        for ts in sorted_ts:
            score = timeline[ts]
            if score < threshold:
                if not current_zone:
                    current_zone = {"start": ts, "end": ts, "avg_engagement": score}
                else:
                    current_zone["end"] = ts
                    current_zone["avg_engagement"] = (current_zone["avg_engagement"] + score) / 2
            else:
                if current_zone:
                    # Ignore zones shorter than 30 seconds
                    if current_zone["end"] - current_zone["start"] >= 30:
                        friction_zones.append(current_zone)
                    current_zone = None
        
        if current_zone and current_zone["end"] - current_zone["start"] >= 30:
            friction_zones.append(current_zone)

        return friction_zones

    async def _analyze_content_friction(self, lecture: Lecture, friction_zones: List[Dict]) -> Dict:
        """Use LLM to correlate friction zones with transcript content and generate advice."""
        if not self.client:
            return {"topics": [], "recommendations": ["AI Client not available."]}

        transcript = lecture.transcript or lecture.description or "No transcript available."
        
        # Prepare friction zone data for prompt
        zones_summary = "\n".join([
            f"- Time {z['start']}s to {z['end']}s (Avg Engagement: {z['avg_engagement']:.1f}%)"
            for z in friction_zones
        ])

        prompt = f"""
        You are a Pedagogical Intelligence Analyst. Analyze the following lecture content and identified student 'Friction Zones' (periods of low engagement/confusion).
        
        Lecture Title: {lecture.title}
        Transcript Segment: {transcript[:6000]}
        
        Friction Zones Detected:
        {zones_summary}
        
        TASK:
        1. TOPIC CORRELATION: Identify the EXACT technical topics being discussed during EACH friction zone.
        2. EXPLANATION GAP: Hypothesize WHY students struggled (was it jargon? abstract theory? lack of visual aids?).
        3. RECOMMENDATIONS: Provide 3 concrete, actionable teaching tips (e.g., 'Use an analogy of a spiderweb for X' or 'Break Y into 3 steps').
        
        Format as JSON (topics: [{{timestamp: str, topic: str, friction_reason: str}}], recommendations: [str], overall_sentiment: str)
        """

        try:
            model_chain = settings.groq_chat_models_for_task("tutor_general", "llama-3.3-70b-versatile")
            
            response, _ = await chat_completion_with_fallback(
                self.client,
                primary_model=model_chain[0],
                fallback_models=model_chain[1:],
                messages=[
                    {"role": "system", "content": "You are a precise pedagogical analyst. Output ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=2000
            )

            content = response.choices[0].message.content.strip()
            # Clean JSON if it has markdown blocks
            if "```" in content:
                content = re.sub(r'```json\n?|\n?```', '', content).strip()
            
            return json.loads(content)
        except Exception as e:
            debug_logger.log("error", f"Intelligence Analysis failed: {e}")
            return {
                "topics": [{"timestamp": "N/A", "topic": "Analysis Failed", "friction_reason": str(e)}],
                "recommendations": ["Ensure transcripts are fully synced.", "Retrying analysis later."],
                "overall_sentiment": "Undetermined"
            }

intelligence_service = IntelligenceService()
