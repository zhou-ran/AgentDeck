"""Session file parsing for codex, claude, and kimi agents.

Borrows design patterns from agent-foreman's monitor_server.py:
- parse_codex_session() (ref lines 788-850)
- parse_claude_session() (ref lines 900-956)
- Session-process matching (ref lines 1164-1189)
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def _parse_iso_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _truncate(text: str | None, limit: int = 240) -> str:
    if not text:
        return ""
    one = " ".join(str(text).split())
    return one if len(one) <= limit else one[: limit - 1] + "…"


def _expand(path: str | None) -> Path | None:
    if not path:
        return None
    return Path(os.path.expanduser(path))


# ---------------------------------------------------------------------------
# Session file discovery
# ---------------------------------------------------------------------------

SESSION_SEARCH_PATHS: dict[str, list[str]] = {
    "codex": [
        "~/.codex/sessions",
        "~/.codex/logs",
    ],
    "claude": [
        "~/.claude/projects",
        "~/.claude/logs",
    ],
    "kimi-code": [
        "~/.kimi/logs",
        "~/.kimi/user-history",
        "~/.kimi-code/logs",
        "~/.kimi-code/user-history",
    ],
    "kimi": [
        "~/.kimi/logs",
        "~/.kimi/user-history",
        "~/.kimi-code/logs",
        "~/.kimi-code/user-history",
    ],
}


def discover_session_files(agent_type: str, project_dir: str | None = None, limit: int = 40) -> list[Path]:
    """Find candidate session files for the given agent type.

    Searches both global paths and project-local paths.
    Returns files sorted by mtime (most recent first).
    """
    search_key = agent_type
    if search_key not in SESSION_SEARCH_PATHS:
        # Try partial match (e.g. "kimi-code" for "kimi")
        for key in SESSION_SEARCH_PATHS:
            if key in agent_type:
                search_key = key
                break
        else:
            return []

    bases: list[Path] = []
    for raw in SESSION_SEARCH_PATHS[search_key]:
        p = _expand(raw)
        if p and p.exists():
            bases.append(p)

    # Also check project-local dirs
    if project_dir:
        proj = Path(project_dir)
        for name in (".codex", ".claude", ".kimi", ".kimi-code"):
            local = proj / name
            if local.exists():
                bases.append(local)

    suffixes = {".jsonl", ".json", ".log"}
    candidates: list[tuple[float, Path]] = []
    for base in bases:
        try:
            for path in base.rglob("*"):
                if len(candidates) >= limit * 3:
                    break
                if not path.is_file():
                    continue
                if path.suffix.lower() not in suffixes:
                    continue
                # Skip config/settings files
                if "settings" in path.name.lower() or "config" in path.name.lower():
                    continue
                try:
                    candidates.append((path.stat().st_mtime, path))
                except OSError:
                    continue
        except OSError:
            continue

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in candidates[:limit]]


# ---------------------------------------------------------------------------
# Codex session parser
# ---------------------------------------------------------------------------

def _extract_codex_message(payload: dict[str, Any]) -> str | None:
    """Extract assistant message from codex response_item payload."""
    ptype = payload.get("type")
    if ptype == "message" and payload.get("role") == "assistant":
        parts = []
        for item in payload.get("content", []):
            if item.get("type") in {"output_text", "text"} and item.get("text"):
                parts.append(item["text"])
        if parts:
            return " ".join(parts)
    if ptype == "function_call":
        name = payload.get("name")
        if name:
            return f"tool:{name}"
    return None


def _extract_codex_pending(payload: dict[str, Any]) -> list[str]:
    """Extract pending plan items from codex update_plan function call."""
    if payload.get("type") != "function_call" or payload.get("name") != "update_plan":
        return []
    raw_args = payload.get("arguments", "")
    try:
        data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    pending = []
    for item in data.get("plan", []):
        if item.get("status") != "completed":
            status = item.get("status", "pending")
            step = item.get("step", "")
            pending.append(f"[{status}] {step}".strip())
    return pending


def parse_codex_session(path: Path) -> dict[str, Any] | None:
    """Parse a codex .jsonl session file.

    Returns a session dict with: session_id, cwd, start_ts, heartbeat_ts,
    recent_output, pending_items, last_user_message, source_file.
    """
    meta: dict[str, Any] = {
        "session_id": None,
        "cwd": None,
        "start_ts": None,
        "heartbeat_ts": path.stat().st_mtime,
        "recent_output": "",
        "pending_items": [],
        "last_user_message": "",
        "source_file": str(path),
        "git_branch": None,
    }
    tail: deque[str] = deque(maxlen=80)
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            first = f.readline()
            if first:
                obj = _safe_json_loads(first)
                if isinstance(obj, dict) and obj.get("type") == "session_meta":
                    payload = obj.get("payload", {})
                    meta["session_id"] = payload.get("id")
                    meta["cwd"] = payload.get("cwd")
                    meta["start_ts"] = _parse_iso_ts(payload.get("timestamp")) or _parse_iso_ts(obj.get("timestamp"))
                    meta["heartbeat_ts"] = _parse_iso_ts(obj.get("timestamp")) or meta["heartbeat_ts"]
                tail.append(first)
            for line in f:
                tail.append(line)
    except Exception:
        return None

    pending: list[str] = []
    recent_text = ""
    recent_tool = ""
    last_user = ""
    last_ts = meta["heartbeat_ts"]
    for line in reversed(tail):
        obj = _safe_json_loads(line)
        if not isinstance(obj, dict):
            continue
        ts = _parse_iso_ts(obj.get("timestamp"))
        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts
        if obj.get("type") == "event_msg":
            ep = obj.get("payload", {})
            if ep.get("type") == "agent_message" and not recent_text:
                recent_text = ep.get("message", "")
        elif obj.get("type") == "response_item":
            candidate = _extract_codex_message(obj.get("payload", {})) or ""
            if candidate and candidate.startswith("tool:") and not recent_tool:
                recent_tool = candidate
            elif candidate and not recent_text:
                recent_text = candidate
        if not last_user and obj.get("type") == "event_msg":
            ep = obj.get("payload", {})
            if ep.get("type") == "user_message":
                last_user = ep.get("message", "")
        if not pending and obj.get("type") == "response_item":
            pending = _extract_codex_pending(obj.get("payload", {}))

    meta["recent_output"] = _truncate(recent_text or recent_tool)
    meta["pending_items"] = pending or ([_truncate(last_user, 180)] if last_user else [])
    meta["last_user_message"] = _truncate(last_user, 180)
    meta["heartbeat_ts"] = last_ts
    return meta


# ---------------------------------------------------------------------------
# Claude session parser
# ---------------------------------------------------------------------------

def _extract_claude_assistant_text(obj: dict[str, Any]) -> str | None:
    """Extract assistant text from a claude session line."""
    if obj.get("type") == "summary" and obj.get("summary"):
        return obj["summary"]
    if obj.get("type") == "assistant":
        message = obj.get("message", {})
        content = message.get("content", [])
        if isinstance(content, str):
            return content
        parts = []
        for item in content:
            if item.get("type") == "text" and item.get("text"):
                parts.append(item["text"])
        if parts:
            return " ".join(parts)
    if obj.get("type") == "last-prompt":
        return obj.get("lastPrompt")
    return None


def _parse_claude_todos(session_id: str) -> list[str]:
    """Parse claude task/todo files for pending items."""
    items: list[str] = []
    home = Path.home()

    # Check ~/.claude/tasks/{session_id}/*.json
    tasks_dir = home / ".claude" / "tasks" / session_id
    if tasks_dir.exists():
        try:
            for path in sorted(tasks_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    continue
                if isinstance(data, dict) and data.get("status") != "completed":
                    subject = data.get("activeForm") or data.get("subject") or path.name
                    items.append(f"[{data.get('status', 'pending')}] {subject}")
        except OSError:
            pass

    # Check ~/.claude/todos/{session_id}-agent-*.json
    todos_dir = home / ".claude" / "todos"
    if todos_dir.exists():
        try:
            for path in todos_dir.glob(f"{session_id}-agent-*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    continue
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("status") != "completed":
                            subject = item.get("activeForm") or item.get("content") or "todo"
                            items.append(f"[{item.get('status', 'pending')}] {subject}")
        except OSError:
            pass

    # Deduplicate
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped[:8]


def parse_claude_session(path: Path) -> dict[str, Any] | None:
    """Parse a claude .jsonl session file.

    Returns a session dict with: session_id, cwd, start_ts, heartbeat_ts,
    recent_output, pending_items, last_user_message, source_file, git_branch.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    if not lines:
        return None

    session_id = path.stem
    cwd = None
    start_ts = None
    heartbeat_ts = path.stat().st_mtime
    recent_output = ""
    last_user = ""
    git_branch = None

    for raw in lines:
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue
        ts = _parse_iso_ts(obj.get("timestamp"))
        if ts:
            heartbeat_ts = max(heartbeat_ts, ts)
            if start_ts is None or ts < start_ts:
                start_ts = ts
        if not cwd and obj.get("cwd"):
            cwd = obj.get("cwd")
        if not git_branch and obj.get("gitBranch"):
            git_branch = obj.get("gitBranch")

    for raw in reversed(lines[-80:]):
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue
        if not recent_output:
            recent_output = _extract_claude_assistant_text(obj) or recent_output
        if not last_user and obj.get("type") == "user":
            msg = obj.get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                last_user = content

    pending_items = _parse_claude_todos(session_id)
    if not pending_items and last_user:
        pending_items = [_truncate(last_user, 180)]

    return {
        "session_id": session_id,
        "cwd": cwd,
        "start_ts": start_ts,
        "heartbeat_ts": heartbeat_ts,
        "recent_output": _truncate(recent_output),
        "pending_items": pending_items,
        "last_user_message": _truncate(last_user, 180),
        "source_file": str(path),
        "git_branch": git_branch,
    }


# ---------------------------------------------------------------------------
# Kimi session parser
# ---------------------------------------------------------------------------

def parse_kimi_session(path: Path) -> dict[str, Any] | None:
    """Parse a kimi/kimi-code session file (.jsonl or .log format).

    Returns a session dict with the standard fields.
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    if not lines:
        return None

    session_id = path.stem
    cwd = None
    start_ts = None
    heartbeat_ts = path.stat().st_mtime
    recent_output = ""
    last_user = ""

    # Scan all lines for metadata
    for raw in lines:
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue
        ts = _parse_iso_ts(obj.get("timestamp"))
        if ts:
            heartbeat_ts = max(heartbeat_ts, ts)
            if start_ts is None or ts < start_ts:
                start_ts = ts
        if not cwd and obj.get("cwd"):
            cwd = obj.get("cwd")

    # Parse recent messages for output and user input
    for raw in reversed(lines[-80:]):
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue

        role = obj.get("role", "")
        msg_type = obj.get("type", "")

        # Extract assistant's recent output
        if not recent_output:
            if role == "assistant" or msg_type == "assistant":
                content = obj.get("content", [])
                if isinstance(content, str):
                    recent_output = content
                elif isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                            parts.append(item["text"])
                    if parts:
                        recent_output = " ".join(parts)
                # Also check message.content format
                if not recent_output:
                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        mc = msg.get("content", [])
                        if isinstance(mc, str):
                            recent_output = mc
                        elif isinstance(mc, list):
                            parts = []
                            for item in mc:
                                if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                                    parts.append(item["text"])
                            if parts:
                                recent_output = " ".join(parts)

        # Extract user's last message
        if not last_user:
            if role == "user" or msg_type == "user":
                content = obj.get("content", [])
                if isinstance(content, str):
                    last_user = content
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text = item.get("text", "")
                            if not text.startswith("<system-reminder>"):
                                last_user = text
                                break
                if not last_user:
                    msg = obj.get("message", {})
                    if isinstance(msg, dict):
                        mc = msg.get("content", [])
                        if isinstance(mc, str):
                            last_user = mc

    return {
        "session_id": session_id,
        "cwd": cwd,
        "start_ts": start_ts,
        "heartbeat_ts": heartbeat_ts,
        "recent_output": _truncate(recent_output),
        "pending_items": [_truncate(last_user, 180)] if last_user else [],
        "last_user_message": _truncate(last_user, 180),
        "source_file": str(path),
        "git_branch": None,
    }


# ---------------------------------------------------------------------------
# Session-process matching
# ---------------------------------------------------------------------------

def match_session_to_process(
    sessions: list[dict[str, Any]],
    cwd: str,
    start_ts: float,
) -> dict[str, Any] | None:
    """Find the best matching session for a process with the given cwd and start_ts.

    Groups sessions by cwd, then finds the one with closest start_ts.
    """
    if not sessions:
        return None

    # Filter sessions that match cwd
    candidates = []
    for s in sessions:
        s_cwd = s.get("cwd")
        if not s_cwd:
            continue
        # Normalize paths for comparison
        if os.path.normpath(s_cwd) == os.path.normpath(cwd):
            candidates.append(s)

    if not candidates:
        # Fallback: try matching by basename
        cwd_base = os.path.basename(cwd)
        candidates = [s for s in sessions if os.path.basename(s.get("cwd", "")) == cwd_base]

    if not candidates:
        return None

    # Find closest by start_ts
    def _ts_distance(s: dict[str, Any]) -> float:
        s_ts = s.get("start_ts") or s.get("heartbeat_ts") or start_ts
        return abs(s_ts - start_ts)

    return min(candidates, key=_ts_distance)


def parse_and_match_sessions(
    agent_type: str,
    cwd: str,
    start_ts: float,
    project_dir: str | None = None,
) -> dict[str, Any] | None:
    """Discover session files, parse them, and find the best match for a process.

    Returns the matched session dict or None.
    """
    files = discover_session_files(agent_type, project_dir)
    if not files:
        return None

    parser_map: dict[str, Any] = {
        "codex": parse_codex_session,
        "claude": parse_claude_session,
    }
    # Find the right parser
    parser = None
    for key, func in parser_map.items():
        if key in agent_type:
            parser = func
            break
    if parser is None:
        if "kimi" in agent_type:
            parser = parse_kimi_session
        else:
            return None

    sessions: list[dict[str, Any]] = []
    for f in files:
        try:
            parsed = parser(f)
            if parsed:
                sessions.append(parsed)
        except Exception:
            continue

    return match_session_to_process(sessions, cwd, start_ts)
