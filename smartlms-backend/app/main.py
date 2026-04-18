"""
Smart LMS Backend - Main Application
FastAPI app with all routers, middleware, and startup events
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import os
import asyncio
from sqlalchemy import text

from app.config import settings
from app.database import async_session, create_tables
from app.database_indexes import ensure_performance_indexes
from app.middleware.rate_limit import InMemoryRateLimiter, key_for_request
from app.services.debug_logger import debug_logger

# Import routers
from app.routers import auth, courses, lectures
from app.routers import engagement as engagement_router
from app.routers import quizzes as quizzes_router
from app.routers import feedback as feedback_router
from app.routers import notifications as notifications_router
from app.routers import analytics as analytics_router
from app.routers import admin as admin_router
from app.routers import users as users_router
from app.routers import gamification as gamification_router
from app.routers import assignments as assignments_router
from app.routers import activity as activity_router
from app.routers import tutor as tutor_router
from app.routers import messaging as messaging_router



from app.services.db_sync import run_db_sync



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print("\n" + "=" * 60)
    print("  Smart LMS Backend Starting...")
    print("=" * 60)

    # Database Initialization (Container-Sourced Construction)
    if settings.AUTO_CREATE_TABLES:
        print("[DB] Fresh RDS initialization triggered...")
        await create_tables()
        print("[DB] [OK] Schema generated successfully.")
    else:
        print("\n" + "!" * 60)
        print("  [SECURITY] Manual Schema Management is ACTIVE.")
        print("  Bypassing all automated sync and table creation.")
        print("!" * 60 + "\n")

    # CORS Diagnostic
    print(f"[CORS] Allowed Origins: {settings.allowed_origins()}")
    print(f"[CORS] Mode: {'Universal' if settings.ALLOW_ALL_CORS_IN_DEV else 'Restricted'}")

    if settings.AUTO_CREATE_INDEXES:
        await ensure_performance_indexes()
        print("[OK] Runtime performance indexes ensured")
    else:
        print("[INFO] AUTO_CREATE_INDEXES disabled")

    debug_logger.log("activity", "Server started",
                     data={"env": settings.APP_ENV, "debug": settings.DEBUG_MODE})

    # Check for insecure JWT warnings (but don't crash)
    if (
        settings.APP_ENV == "production"
        and settings.REQUIRE_SECURE_JWT_IN_PROD
        and settings.JWT_SECRET_KEY == "change-this-to-a-secure-secret-key"
    ):
        print(f"\n[WARNING] JWT_SECRET_KEY is insecure! Please update environment variables immediately.\n")

    # ---- PRODUCTION AI ENGINE: Distributed Mode ----
    # Local model loading is disabled here to save RAM.
    # The dedicated ML Worker or ML Service handles model inference.
    debug_logger.log("activity", "Async ML Client initialized (SQS Mode)")

    yield

    # Shutdown
    if hasattr(app, "neural_monitor"):
        app.neural_monitor.cancel()
    debug_logger.log("activity", "Server shutting down")
    print("\n[INFO] Smart LMS Backend stopped.")


app = FastAPI(
    title="Smart LMS API",
    description="Smart Learning Management System with AI-powered engagement tracking",
    version="2.0.0",
    lifespan=lifespan,
)

rate_limiter = InMemoryRateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)
rate_limit_exempt_paths = settings.rate_limit_exempt_paths()

# --- MIDDLEWARE STACK ---

# 1. Request logging & Security Headers middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Add Security Headers for Google Auth & Resilience
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    response.headers["Cross-Origin-Embedder-Policy"] = "credentialless" # Optional, but helps with isolation
    
    # Log to debug logger
    if settings.DEBUG_MODE and not request.url.path.startswith("/docs"):
        debug_logger.log_api(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

    return response


# 2. Global Exception Handler for CORS Resilience
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure all exceptions return a valid JSON response so CORSMiddleware can add headers."""
    print(f"[FATAL] Global Exception: {str(exc)}", flush=True)
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal Server Error. Security headers persisted.",
            "detail": str(exc) if not settings.APP_ENV == "production" else "Check backend logs for details"
        }
    )


# 2b. Detailed Validation Error Logger (For 422 Debugging)
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Capture and log 422 errors to see exactly which field failed."""
    errors = exc.errors()
    print("\n" + "!" * 40)
    print(f"  [VALIDATION ERROR] {request.method} {request.url.path}")
    for err in errors:
        print(f"  - Field: {' -> '.join(str(p) for p in err.get('loc', []))}")
        print(f"    Message: {err.get('msg')}")
        print(f"    Input Type: {err.get('type')}")
    print("!" * 40 + "\n")
    
    debug_logger.log("error", f"Validation failure on {request.url.path}", data={"errors": errors})
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation Failed",
            "detail": errors
        }
    )


# 3. Root heartbeat for ALB
@app.get("/")
async def root_heartbeat():
    """Root heartbeat for AWS ALB default health checks"""
    return {
        "status": "SmartLMS Core Online",
        "node": "Matrix-Production-01",
        "timestamp": time.time()
    }


# 3. Rate limiting middleware
@app.middleware("http")
async def apply_rate_limit(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    if request.method == "OPTIONS" or request.url.path in rate_limit_exempt_paths:
        return await call_next(request)

    if not request.url.path.startswith("/api"):
        return await call_next(request)

    result = await rate_limiter.check(key_for_request(request))
    if not result.allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please retry shortly."},
            headers={
                "Retry-After": str(result.reset_in_seconds),
                "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result.reset_in_seconds),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_in_seconds)
    return response


# Register routers
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(lectures.router)
app.include_router(engagement_router.router)
app.include_router(quizzes_router.router)
app.include_router(feedback_router.router)
app.include_router(notifications_router.router)
app.include_router(analytics_router.router)
app.include_router(admin_router.router)
app.include_router(users_router.router)
app.include_router(gamification_router.router)
app.include_router(assignments_router.router)
app.include_router(activity_router.router)
app.include_router(tutor_router.router)
app.include_router(messaging_router.router)


# --- FINAL MIDDLEWARE WRAPPER (OUTERMOST) ---
# We add CORS last so it is the first to handle the request 
# and the last to handle the response (wrapping all other middlewares).
allow_origin_regex = "https?://.*\.vercel\.app|chrome-extension://.*"
if settings.APP_ENV != "production" and settings.ALLOW_ALL_CORS_IN_DEV:
    allow_origin_regex = "https?://.*|chrome-extension://.*"

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins(),
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "env": settings.APP_ENV,
        "debug_mode": settings.DEBUG_MODE,
    }


@app.get("/api/health/checkpoint")
async def health_checkpoint():
    db_ok = True
    db_error = ""
    db_latency_ms = None
    db_start = time.perf_counter()

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - db_start) * 1000, 2)
    except Exception as e:
        db_ok = False
        db_error = str(e)

    limiter_state = {
        "enabled": settings.RATE_LIMIT_ENABLED,
    }
    if settings.RATE_LIMIT_ENABLED:
        limiter_state["runtime"] = await rate_limiter.snapshot()

    chat_pool = settings.groq_chat_model_pool()
    audio_pool = settings.groq_audio_model_pool()

    overall_status = "healthy" if db_ok else "degraded"

    return {
        "status": overall_status,
        "version": "2.0.0",
        "env": settings.APP_ENV,
        "checkpoint": {
            "database": {
                "ok": db_ok,
                "latency_ms": db_latency_ms,
                "error": db_error,
            },
            "rate_limit": limiter_state,
            "groq": {
                "api_key_configured": bool(settings.GROQ_API_KEY),
                "chat_model_pool_size": len(chat_pool),
                "audio_model_pool_size": len(audio_pool),
                "chat_models": chat_pool,
                "audio_models": audio_pool,
                "retries_per_model": settings.GROQ_MODEL_RETRIES_PER_MODEL,
            },
        },
    }
