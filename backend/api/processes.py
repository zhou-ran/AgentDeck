from __future__ import annotations

from fastapi import APIRouter

from backend.process_scanner import discover_agent_processes

router = APIRouter(tags=["processes"])


@router.get("/discover")
async def api_discover():
    """Auto-discover running agent processes not managed by agentctl."""
    procs = discover_agent_processes()
    return {"count": len(procs), "processes": procs}
