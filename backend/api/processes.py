from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.process_scanner import scan_agent_sessions

router = APIRouter(tags=["processes"])


@router.get("/discover")
async def api_discover():
    """Auto-discover running agent processes grouped by cwd."""
    sessions = scan_agent_sessions()
    return {"count": len(sessions), "sessions": [s.model_dump(mode="json") for s in sessions]}


@router.get("/discover/{session_id}")
async def api_discover_session(session_id: str):
    """Get details of a discovered session by ID."""
    sessions = scan_agent_sessions()
    for s in sessions:
        if s.session_id == session_id:
            return s.model_dump(mode="json")
    raise HTTPException(404, f"Session {session_id!r} not found")
