"""
Smart LMS Backend - Configuration
Environment-based settings with Pydantic
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    API_BASE_URL: str = "http://localhost:8000"
    APP_TRUSTED_ORIGINS: str = ""
    ALLOW_ALL_CORS_IN_DEV: bool = True
    AUTO_CREATE_TABLES: bool = False     # DISABLED: Manual management only
    AUTO_CREATE_INDEXES: bool = True
    SYNC_SCHEMA_ON_STARTUP: bool = False # DISABLED: Manual management only
    REQUIRE_SECURE_JWT_IN_PROD: bool = True
    ANALYTICS_MAX_LOG_ROWS: int = 1200
    STORAGE_PROVIDER: str = "s3"  # prioritized 's3', fallback to 'cloudinary' or 'local'
    ML_SERVICE_URL: str = "http://localhost:8001"  # dedicated ML instance

    # API rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 300
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_EXEMPT_PATHS: str = "/api/health,/api/health/checkpoint,/docs,/openapi.json,/redoc"

    # Database (Neon DB)
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/smartlms"
    DATABASE_URL_SYNC: str = "postgresql://user:password@localhost/smartlms"

    # JWT
    JWT_SECRET_KEY: str = "change-this-to-a-secure-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Google Auth
    GOOGLE_CLIENT_ID: str = ""

    # Groq (AI)
    GROQ_API_KEY: str = ""
    GROQ_CHAT_FALLBACK_MODELS: str = "llama-3.1-8b-instant,mixtral-8x7b-32768,gemma2-9b-it"
    GROQ_AUDIO_FALLBACK_MODELS: str = "whisper-large-v3-turbo"
    GROQ_CHAT_MODEL_POOL: str = "llama-3.3-70b-versatile,llama-3.1-8b-instant,mixtral-8x7b-32768,gemma2-9b-it,llama-4-scout-17b-16e-instruct"
    GROQ_AUDIO_MODEL_POOL: str = "whisper-large-v3,whisper-large-v3-turbo"
    GROQ_MODEL_RETRIES_PER_MODEL: int = 1
    GROQ_MODEL_RETRY_BASE_SECONDS: float = 1.2
    GROQ_MODEL_RETRY_MAX_SECONDS: float = 12.0

    # AWS & S3 Storage (Multi-Cloud Fallback)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "smartlms-assets-friedrice"
    AWS_S3_MODEL_BUCKET: str = "smartlms-assets-friedrice"
    AWS_S3_PATH_STYLE: bool = False
    
    # AWS SQS (Async ML Pipeline)
    SQS_QUEUE_URL: str = ""
    SQS_WAIT_TIME_SECONDS: int = 20

    # YouTube resilience
    YOUTUBE_PROXY: Optional[str] = None
    YOUTUBE_COOKIES: Optional[str] = None  # Raw string or base64 encoded cookies.txt
    YOUTUBE_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    YOUTUBE_PO_TOKEN: Optional[str] = None
    YOUTUBE_VISITOR_DATA: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    YOUTUBE_TRANSCRIPT_PROXY_URL: Optional[str] = None
    YOUTUBE_TRANSCRIPT_PROXY_KEY: Optional[str] = None

    # Debug
    DEBUG_MODE: bool = False
    DEBUG_LOG_DIR: str = "./debug_logs"

    # SQL / Performance
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 3600
    DB_CONNECT_TIMEOUT_SECONDS: float = 30.0
    DB_COMMAND_TIMEOUT_SECONDS: float = 30.0

    # Local media storage (store file path in DB, bytes on disk/object store)
    UPLOAD_DIR: str = "./uploads"
    MAX_VIDEO_UPLOAD_MB: int = 250
    MAX_MATERIAL_UPLOAD_MB: int = 50

    class Config:
        env_file = ".env"
        extra = "allow"

    def allowed_origins(self) -> list[str]:
        origins = []
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL.strip())

        if self.APP_TRUSTED_ORIGINS:
            for origin in self.APP_TRUSTED_ORIGINS.split(","):
                cleaned = origin.strip()
                if cleaned:
                    origins.append(cleaned)

        # Production Vercel Deployment whitelisting
        origins.append("https://smartlms-nextjs.vercel.app")
        
        if self.APP_ENV != "production" and self.ALLOW_ALL_CORS_IN_DEV:
            origins.extend([
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:5175",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:5174",
                "http://127.0.0.1:5175",
                "http://127.0.0.1:3000",
            ])

        # Finalized Production Whitelist
        origins.extend([
            "https://smartlms.online",
            "https://smartlms-nextjs.vercel.app",
            "chrome-extension://pehjijfanpifbgpjliiaplegdeikmfkg"
        ])
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(origins))

    def groq_chat_fallback_models(self) -> list[str]:
        if not self.GROQ_CHAT_FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.GROQ_CHAT_FALLBACK_MODELS.split(",") if m.strip()]

    def groq_audio_fallback_models(self) -> list[str]:
        if not self.GROQ_AUDIO_FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.GROQ_AUDIO_FALLBACK_MODELS.split(",") if m.strip()]

    def groq_chat_model_pool(self) -> list[str]:
        if not self.GROQ_CHAT_MODEL_POOL:
            return []
        return [m.strip() for m in self.GROQ_CHAT_MODEL_POOL.split(",") if m.strip()]

    def groq_audio_model_pool(self) -> list[str]:
        if not self.GROQ_AUDIO_MODEL_POOL:
            return []
        return [m.strip() for m in self.GROQ_AUDIO_MODEL_POOL.split(",") if m.strip()]

    def groq_chat_models_for_task(
        self,
        *,
        task: str,
        primary_model: str,
        task_fallbacks: Optional[list[str]] = None,
    ) -> list[str]:
        task_defaults = {
            "tutor_general": ["llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            "tutor_language_practice": ["mixtral-8x7b-32768", "llama-3.1-8b-instant"],
            "tutor_grammar_check": ["gemma2-9b-it", "llama-3.1-8b-instant"],
            "quiz_generation": ["llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            "quiz_refinement": ["llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            "semantic_grading": ["llama-3.1-8b-instant", "gemma2-9b-it"],
        }

        ordered: list[str] = [primary_model]
        ordered.extend(task_defaults.get(task, []))
        if task_fallbacks:
            ordered.extend([m for m in task_fallbacks if m])
        ordered.extend(self.groq_chat_fallback_models())
        ordered.extend(self.groq_chat_model_pool())
        return list(dict.fromkeys([m for m in ordered if m]))

    def groq_audio_models_for_task(
        self,
        *,
        primary_model: str,
        task_fallbacks: Optional[list[str]] = None,
    ) -> list[str]:
        ordered: list[str] = [primary_model]
        if task_fallbacks:
            ordered.extend([m for m in task_fallbacks if m])
        ordered.extend(self.groq_audio_fallback_models())
        ordered.extend(self.groq_audio_model_pool())
        return list(dict.fromkeys([m for m in ordered if m]))

    def rate_limit_exempt_paths(self) -> set[str]:
        if not self.RATE_LIMIT_EXEMPT_PATHS:
            return set()
        return {p.strip() for p in self.RATE_LIMIT_EXEMPT_PATHS.split(",") if p.strip()}


settings = Settings()

# --- PRODUCTION PERSISTENCE SHIELD ---
# Verify that we are NOT using an ephemeral database in production.
if settings.APP_ENV == "production":
    if "sqlite" in settings.DATABASE_URL:
        print("\n" + "!" * 60)
        print("  [CRITICAL WARNING] PRODUCTION IS RUNNING ON EPHEMERAL SQLITE!")
        print("  Changes will be LOST on every container restart.")
        print("  Ensure DATABASE_URL is set to your RDS instance.")
        print("!" * 60 + "\n")
    elif "localhost" in settings.DATABASE_URL:
        print("\n" + "!" * 60)
        print("  [WARNING] PRODUCTION IS TARGETING LOCALHOST DATABASE.")
        print("  This will likely fail unless a tunnel is present.")
        print("!" * 60 + "\n")
    else:
        print(f"[OK] Production Persistence: Remote Database Detected")

# Ensure debug log directory exists
if settings.DEBUG_MODE:
    os.makedirs(settings.DEBUG_LOG_DIR, exist_ok=True)

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
