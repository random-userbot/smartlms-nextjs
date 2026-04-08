"""
Smart LMS - Internet Research Service
Augments lecture content with external web context for advanced quiz generation.
"""

from typing import List, Dict, Optional
import httpx
import json
from app.config import settings
from app.services.debug_logger import debug_logger

class InternetService:
    def __init__(self):
        self.tavily_key = getattr(settings, 'TAVILY_API_KEY', None)
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    async def search_related_context(self, query: str, max_results: int = 3) -> str:
        """Search the web for related context. Standardizes the output to a single text block."""
        if not query:
            return ""

        # Tier 1: Tavily (if configured)
        if self.tavily_key:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.tavily_key,
                            "query": query,
                            "search_depth": "basic",
                            "max_results": max_results
                        }
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        return "\n".join([f"- {r['title']}: {r['content']}" for r in results])
            except Exception as e:
                debug_logger.log("warning", f"Tavily search failed: {str(e)}")

        # Tier 2: Wikipedia Fallback
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Simple Wikipedia API for factual reinforcement
                resp = await client.get(
                    f"https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={query}&srlimit={max_results}"
                )
                if resp.status_code == 200:
                    search_results = resp.json().get("query", {}).get("search", [])
                    if search_results:
                        return "\n".join([f"- {r['title']}: {r['snippet']}" for r in search_results])
        except Exception as e:
            debug_logger.log("warning", f"Wikipedia lookup failed: {str(e)}")

        return "External context unavailable. Proceeding with internal knowledge."

internet_service = InternetService()
