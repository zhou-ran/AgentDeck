from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.process_scanner import scan_agent_sessions
from backend.rules import (
    create_rule,
    delete_rule,
    list_rules,
    matching_rules,
    restore_ignored_rule,
)

router = APIRouter(tags=["processes"])


class RuleCreate(BaseModel):
    type: str
    value: str
    note: str = ""


@router.get("/discover")
async def api_discover(include_ignored: bool = Query(False)):
    """Auto-discover running agent processes grouped by cwd."""
    sessions = scan_agent_sessions(include_ignored=include_ignored)
    return {"count": len(sessions), "sessions": [s.model_dump(mode="json") for s in sessions]}


@router.get("/discover/{session_id}")
async def api_discover_session(session_id: str):
    """Get details of a discovered session by ID."""
    sessions = scan_agent_sessions(include_ignored=True)
    for s in sessions:
        if s.session_id == session_id:
            return s.model_dump(mode="json")
    raise HTTPException(404, f"Session {session_id!r} not found")


@router.get("/pins")
async def api_list_pins():
    return {"version": 1, "rules": [rule.model_dump(mode="json") for rule in list_rules("pins")]}


@router.post("/pins")
async def api_create_pin(body: RuleCreate):
    rule = create_rule("pins", body.type, body.value, body.note)
    return rule.model_dump(mode="json")


@router.delete("/pins/{rule_id}")
async def api_delete_pin(rule_id: str):
    if not delete_rule("pins", rule_id):
        raise HTTPException(404, f"Pin rule {rule_id!r} not found")
    return {"ok": True}


@router.get("/ignored")
async def api_list_ignored(include_inactive: bool = Query(False)):
    return {
        "version": 1,
        "rules": [rule.model_dump(mode="json") for rule in list_rules("ignored", include_inactive=include_inactive)],
    }


@router.post("/ignored")
async def api_create_ignored(body: RuleCreate):
    rule = create_rule("ignored", body.type, body.value, body.note)
    return rule.model_dump(mode="json")


@router.delete("/ignored/{rule_id}")
async def api_delete_ignored(rule_id: str):
    if not delete_rule("ignored", rule_id):
        raise HTTPException(404, f"Ignored rule {rule_id!r} not found")
    return {"ok": True}


@router.post("/ignored/{rule_id}/restore")
async def api_restore_ignored(rule_id: str):
    if not restore_ignored_rule(rule_id):
        raise HTTPException(404, f"Ignored rule {rule_id!r} not found")
    return {"ok": True}


def _find_session(session_id: str):
    for session in scan_agent_sessions(include_ignored=True):
        if session.session_id == session_id:
            return session
    raise HTTPException(404, f"Session {session_id!r} not found")


@router.post("/sessions/{session_id}/pin")
async def api_pin_session(session_id: str):
    session = _find_session(session_id)
    existing = matching_rules("pins", session)
    if existing:
        return existing[0].model_dump(mode="json")
    rule = create_rule("pins", "project_key", session.project_key, session.display_name or session.project)
    return rule.model_dump(mode="json")


@router.post("/sessions/{session_id}/unpin")
async def api_unpin_session(session_id: str):
    session = _find_session(session_id)
    removed = False
    for rule in matching_rules("pins", session):
        removed = delete_rule("pins", rule.id) or removed
    return {"ok": True, "removed": removed}


@router.post("/sessions/{session_id}/ignore")
async def api_ignore_session(session_id: str):
    session = _find_session(session_id)
    existing = matching_rules("ignored", session)
    if existing:
        return existing[0].model_dump(mode="json")
    rule = create_rule("ignored", "project_key", session.project_key, session.display_name or session.project)
    return rule.model_dump(mode="json")


@router.post("/sessions/{session_id}/unignore")
async def api_unignore_session(session_id: str):
    session = _find_session(session_id)
    changed = False
    for rule in matching_rules("ignored", session):
        changed = restore_ignored_rule(rule.id) or changed
    return {"ok": True, "restored": changed}
