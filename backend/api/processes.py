from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models import DiscoveredSession, ImportPidRequest, Task
from backend.process_scanner import discover_sessions, get_process_info
from backend.task_manager import import_pid

router = APIRouter(tags=["processes"])


@router.get("/discover")
async def api_discover():
    """Auto-discover running agent processes grouped by cwd."""
    sessions = discover_sessions()
    return {"count": len(sessions), "sessions": [s.model_dump(mode="json") for s in sessions]}


@router.get("/discover/{session_id}")
async def api_discover_session(session_id: str):
    """Get details of a discovered session by ID."""
    sessions = discover_sessions()
    for s in sessions:
        if s.session_id == session_id:
            return s.model_dump(mode="json")
    raise HTTPException(404, f"Session {session_id!r} not found")


@router.post("/import-pid", response_model=Task, status_code=201)
async def api_import_pid(req: ImportPidRequest):
    """Import an existing PID as a managed task."""
    info = get_process_info(req.pid)
    if not info:
        raise HTTPException(404, f"Process {req.pid} not found")
    task = import_pid(req.pid, req.name)
    if not task:
        raise HTTPException(409, f"Task name '{req.name}' already exists or PID {req.pid} not found")
    return task
