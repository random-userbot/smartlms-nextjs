"""Smart LMS - Activity Tracking Router: batch events, session end, session summary"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.models import ActivityLog, User, ICAPLevel
from app.middleware.auth import get_current_user
from app.services.debug_logger import debug_logger
from app.services.icap_service import map_action_to_icap, get_action_evidence


router = APIRouter(prefix="/api/activity", tags=["Activity Tracking"])


class ActivityEvent(BaseModel):
    action: str
    details: Optional[dict] = None
    timestamp: Optional[str] = None
    page: Optional[str] = None
    session_id: Optional[str] = None


class BatchRequest(BaseModel):
    session_id: str
    events: List[ActivityEvent]
    session_duration: Optional[int] = 0


class SessionEndRequest(BaseModel):
    session_id: str
    duration: int
    page_views: Optional[list] = []
    events: Optional[list] = []


@router.post("/batch")
async def submit_activity_batch(
    request: BatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Receive batched activity events from frontend"""
    saved = 0
    for event in request.events:
        icap_level = map_action_to_icap(event.action)
        evidence = get_action_evidence(event.action, event.details or {})
        
        log = ActivityLog(
            user_id=current_user.id,
            action=event.action,
            details={
                **(event.details or {}),
                "session_id": request.session_id,
                "page": event.page,
                "event_timestamp": event.timestamp,
                "session_duration": request.session_duration,
                "icap_level": icap_level.value if icap_level else None,
                "evidence_summary": evidence
            },
        )
        db.add(log)
        saved += 1

    await db.commit()

    debug_logger.log("activity", f"Batch: {saved} events from {current_user.username} (session: {request.session_id[:12]}...)")

    return {"saved": saved, "session_id": request.session_id}


@router.post("/session-end")
async def submit_session_end(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive session end data (via sendBeacon - no auth header).
    We use the session_id to link to the user.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    session_id = body.get("session_id", "")
    duration = body.get("duration", 0)
    page_views = body.get("page_views", [])
    events = body.get("events", [])

    # Find user from recent activity logs with this session_id
    result = await db.execute(
        select(ActivityLog.user_id)
        .where(ActivityLog.details["session_id"].as_string() == session_id)
        .limit(1)
    )
    row = result.first()

    if row:
        user_id = row[0]

        # Save session end event
        log = ActivityLog(
            user_id=user_id,
            action="session_end",
            details={
                "session_id": session_id,
                "duration_seconds": duration,
                "total_page_views": len(page_views),
                "page_views": page_views[-10:],  # Last 10 pages
            },
        )
        db.add(log)

        # Save any remaining buffered events
        for event in events[-20:]:  # Max 20 events
            ev_log = ActivityLog(
                user_id=user_id,
                action=event.get("action", "unknown"),
                details={
                    **event.get("details", {}),
                    "session_id": session_id,
                    "page": event.get("page"),
                },
            )
            db.add(ev_log)

        await db.commit()
        debug_logger.log("activity", f"Session end: {session_id[:12]}... duration={duration}s pages={len(page_views)}")

    return {"status": "ok"}


@router.get("/session-summary")
async def get_session_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get session analytics for the current user"""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Get all activity logs
    result = await db.execute(
        select(ActivityLog)
        .where(
            ActivityLog.user_id == current_user.id,
            ActivityLog.created_at >= cutoff,
        )
        .order_by(ActivityLog.created_at.desc())
    )
    logs = result.scalars().all()

    # Aggregate
    sessions = []
    page_views = {}
    total_time = 0
    total_events = len(logs)
    idle_events = 0
    tab_switches = 0

    for log in logs:
        details = log.details or {}

        if log.action == "session_end":
            duration = details.get("duration_seconds", 0)
            total_time += duration
            sessions.append({
                "session_id": details.get("session_id", ""),
                "duration": duration,
                "pages": details.get("total_page_views", 0),
                "date": log.created_at.isoformat(),
            })

        if log.action == "page_view":
            page = details.get("page_name", details.get("page", "unknown"))
            time_on = details.get("time_on_page", 0)
            if page not in page_views:
                page_views[page] = {"views": 0, "total_time": 0}
            page_views[page]["views"] += 1
            page_views[page]["total_time"] += time_on

        if log.action == "idle_start":
            idle_events += 1

        if log.action in ("tab_hidden", "tab_switch"):
            tab_switches += 1

    return {
        "total_sessions": len(sessions),
        "total_time_seconds": total_time,
        "total_time_formatted": f"{total_time // 3600}h {(total_time % 3600) // 60}m",
        "total_events": total_events,
        "idle_events": idle_events,
        "tab_switches": tab_switches,
        "avg_session_duration": total_time // max(len(sessions), 1),
        "page_views": dict(sorted(
            page_views.items(),
            key=lambda x: x[1]["views"],
            reverse=True,
        )),
        "recent_sessions": sessions[:10],
    }


@router.get("/recent")
async def get_recent_activity(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent activity logs for the Neural Evidence Ledger"""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "action": log.action,
            "details": log.details,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]
