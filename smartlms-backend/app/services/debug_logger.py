"""
Smart LMS - Debug Logger Service
Logs all actions to terminal + local files + database
Toggle-able via DEBUG_MODE env variable
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from app.config import settings


class DebugLogger:
    """Centralized debug logger that writes to terminal and files"""

    def __init__(self):
        self.enabled = settings.DEBUG_MODE
        self.log_dir = settings.DEBUG_LOG_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        if self.enabled:
            for subdir in ["sessions", "engagement", "models", "activity", "api"]:
                os.makedirs(os.path.join(self.log_dir, subdir), exist_ok=True)

    def log(self, category: str, action: str, data: Optional[Dict] = None,
            user_id: Optional[str] = None, session_id: Optional[str] = None):
        """Log an event to terminal and file"""
        if not self.enabled:
            return

        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "category": category,
            "action": action,
            "user_id": user_id,
            "session_id": session_id,
            "data": data,
        }

        # Terminal output
        color = self._get_color(category)
        print(f"{color}[{timestamp}] [{category.upper()}] {action}{self._reset()}")
        if data:
            # Print compact data summary
            summary = self._summarize(data)
            print(f"  {summary}")

        # File output
        self._write_to_file(category, log_entry)

    def log_engagement(self, student_id: str, lecture_id: str, features: Dict,
                       scores: Dict, shap_data: Optional[Dict] = None):
        """Log engagement data specifically"""
        self.log(
            "engagement",
            f"Student {student_id[:8]} | Lecture {lecture_id[:8]}",
            {
                "features": features,
                "scores": scores,
                "shap": shap_data,
            },
            user_id=student_id,
        )

    def log_model(self, model_name: str, input_data: Dict, output: Dict,
                  explanation: Optional[Dict] = None):
        """Log ML model predictions"""
        self.log(
            "models",
            f"Model: {model_name}",
            {
                "input_summary": {k: type(v).__name__ for k, v in input_data.items()},
                "output": output,
                "explanation": explanation,
            },
        )

    def log_api(self, method: str, path: str, status_code: int,
                user_id: Optional[str] = None, duration_ms: float = 0):
        """Log API requests"""
        self.log(
            "api",
            f"{method} {path} -> {status_code} ({duration_ms:.0f}ms)",
            user_id=user_id,
        )

    def _write_to_file(self, category: str, entry: Dict):
        """Write log entry to category-specific file"""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        filepath = os.path.join(self.log_dir, category, f"{date_str}.jsonl")
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            print(f"[DEBUG_LOGGER_ERROR] Failed to write log: {e}")

    def _summarize(self, data: Dict, max_len: int = 200) -> str:
        """Create a compact summary of data"""
        try:
            s = json.dumps(data, default=str)
            if len(s) > max_len:
                return s[:max_len] + "..."
            return s
        except Exception:
            return str(data)[:max_len]

    @staticmethod
    def _get_color(category: str) -> str:
        colors = {
            "engagement": "\033[36m",   # Cyan
            "models": "\033[35m",       # Magenta
            "activity": "\033[33m",     # Yellow
            "api": "\033[32m",          # Green
            "sessions": "\033[34m",     # Blue
            "error": "\033[31m",        # Red
        }
        return colors.get(category, "\033[0m")

    @staticmethod
    def _reset() -> str:
        return "\033[0m"


# Singleton
debug_logger = DebugLogger()
