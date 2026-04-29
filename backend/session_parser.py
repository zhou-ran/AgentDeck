"""Session file parsing for codex, claude, and kimi agents.

Parses .jsonl session files to extract heartbeat_ts, recent_output,
pending_items, and last_user_message. Used to enrich discovered sessions
with data from the agent's own session logs.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# Session file discovery paths
SESSION_PATHS: dict[str, list[str]] = {
    "codex": ["~/.codex/sessions", "~/.codex/logs"],
    "claude": ["~/.claude/projects", "~/.claude/logs"],
    "claude-code": ["~/.claude/projects", "~/.claude/logs"],
    "kimi": ["~/.kimi", "~/agent_logs"],
    "kimi-code": ["~/.kimi-code", "~/.kimi", "~/agent_logs"],
}


def _safe_json_loads(s: str) -> Any:
    """Parse JSON string, returning None on failure."""
    try:
        return json.loads(s)
    except Exception:
        return None


def _parse_iso_ts(value: str | None) -> float | None:
    """Parse ISO 8601 timestamp to epoch float."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _truncate(text: str | None, limit: int = 240) -> str:
    """Collapse whitespace and truncate to limit."""
    if not text:
        return ""
    one = " ".join(str(text).split())
    return one if len(one) <= limit else one[:limit - 1] + "…"


def _expand_path(path: str | None) -> str | None:
    """Expand ~ in paths."""
    if not path:
        return None
    return os.path.expanduser(path)


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
    """Extract pending plan items from codex update_plan payload."""
    if payload.get("type") != "function_call" or payload.get("name") != "update_plan":
        return []
    data = _safe_json_loads(payload.get("arguments", ""))
    if not isinstance(data, dict):
        return []
    pending = []
    for item in data.get("plan", []):
        if item.get("status") != "completed":
            status = item.get("status", "pending")
            step = item.get("step", "")
            pending.append(f"[{status}] {step}".strip())
    return pending


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


def parse_codex_session(path: Path) -> dict[str, Any] | None:
    """Parse a codex .jsonl session file.

    Returns a uniform dict with session_id, cwd, start_ts, heartbeat_ts,
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
                    meta["start_ts"] = (
                        _parse_iso_ts(payload.get("timestamp"))
                        or _parse_iso_ts(obj.get("timestamp"))
                    )
                    meta["heartbeat_ts"] = (
                        _parse_iso_ts(obj.get("timestamp"))
                        or meta["heartbeat_ts"]
                    )
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


def parse_claude_session(path: Path) -> dict[str, Any] | None:
    """Parse a claude .jsonl session file.

    Returns a uniform dict with session_id, cwd, start_ts, heartbeat_ts,
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

    # Try to find pending items from ~/.claude/tasks/
    pending_items: list[str] = []
    tasks_dir = Path.home() / ".claude" / "tasks" / session_id
    if tasks_dir.exists():
        for task_file in sorted(tasks_dir.glob("*.json")):
            data = _safe_json_loads(task_file.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, dict) and data.get("status") != "completed":
                subject = data.get("activeForm") or data.get("subject") or task_file.name
                pending_items.append(f"[{data.get('status', 'pending')}] {subject}")

    if not pending_items and last_user:
        pending_items = [_truncate(last_user, 180)]

    return {
        "session_id": session_id,
        "cwd": cwd,
        "start_ts": start_ts,
        "heartbeat_ts": heartbeat_ts,
        "recent_output": _truncate(recent_output),
        "pending_items": pending_items[:8],
        "last_user_message": _truncate(last_user, 180),
        "git_branch": git_branch,
        "source_file": str(path),
    }


def parse_kimi_session(path: Path) -> dict[str, Any] | None:
    """Parse a kimi/kimi-code session file (.jsonl or .log).

    Returns a uniform dict matching codex/claude format.
    """
    meta: dict[str, Any] = {
        "session_id": path.stem,
        "cwd": None,
        "start_ts": None,
        "heartbeat_ts": path.stat().st_mtime,
        "recent_output": "",
        "pending_items": [],
        "last_user_message": "",
        "source_file": str(path),
        "git_branch": None,
    }

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None
    if not lines:
        return None

    last_ts = meta["heartbeat_ts"]
    recent_text = ""
    last_user = ""

    for raw in lines:
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue
        ts = _parse_iso_ts(obj.get("timestamp"))
        if ts:
            if last_ts is None or ts > last_ts:
                last_ts = ts
            if meta["start_ts"] is None or ts < meta["start_ts"]:
                meta["start_ts"] = ts
        if not meta["cwd"] and obj.get("cwd"):
            meta["cwd"] = obj.get("cwd")

    # Scan last 80 lines for content
    for raw in reversed(lines[-80:]):
        obj = _safe_json_loads(raw)
        if not isinstance(obj, dict):
            continue
        # Kimi uses various message formats
        if not recent_text:
            # Try role-based extraction
            if obj.get("role") == "assistant":
                content = obj.get("content", "")
                if isinstance(content, str) and content:
                    recent_text = content
                elif isinstance(content, list):
                    parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    recent_text = " ".join(parts)
            # Try type-based extraction
            if obj.get("type") in ("assistant", "response"):
                msg = obj.get("message", obj.get("content", ""))
                if isinstance(msg, str):
                    recent_text = msg
        if not last_user:
            if obj.get("role") == "user":
                content = obj.get("content", "")
                if isinstance(content, str):
                    last_user = content
            if obj.get("type") == "user":
                msg = obj.get("message", obj.get("content", ""))
                if isinstance(msg, str):
                    last_user = msg

    meta["recent_output"] = _truncate(recent_text)
    meta["last_user_message"] = _truncate(last_user, 180)
    meta["heartbeat_ts"] = last_ts
    return meta


def _project_session_paths(agent_type: str, project_dir: str) -> list[Path]:
    if not project_dir:
        return []

    roots = []
    p = Path(project_dir).expanduser()
    if p.exists():
        roots.append(p)
        try:
            from backend.git_utils import get_git_root
            git_root = get_git_root(str(p))
            if git_root:
                git_path = Path(git_root)
                if git_path not in roots:
                    roots.append(git_path)
        except Exception:
            pass

    names = ["logs"]
    if agent_type == "codex":
        names.append(".codex")
    elif agent_type in ("claude", "claude-code"):
        names.append(".claude")
    elif agent_type in ("kimi", "kimi-code"):
        names.extend([".kimi", ".kimi-code"])
    else:
        names.extend([".codex", ".claude", ".kimi", ".kimi-code"])

    paths: list[Path] = []
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.exists():
                paths.append(candidate)
    return paths


def discover_session_files(agent_type: str, project_dir: str) -> list[Path]:
    """Find candidate session files for a given agent type.

    Searches known session directories and returns files sorted by mtime (newest first).
    """
    paths = list(SESSION_PATHS.get(agent_type, []))
    if not paths:
        # Try all known paths for unknown agent types
        paths = [p for plist in SESSION_PATHS.values() for p in plist]

    candidates: list[Path] = []
    search_roots = [Path(_expand_path(path_str) or path_str) for path_str in paths]
    search_roots.extend(_project_session_paths(agent_type, project_dir))
    seen_roots: set[Path] = set()
    for expanded in search_roots:
        try:
            expanded = expanded.resolve()
        except OSError:
            continue
        if expanded in seen_roots or not expanded.exists():
            continue
        seen_roots.add(expanded)
        try:
            for f in expanded.rglob("*.jsonl"):
                if f.is_file():
                    candidates.append(f)
            # Also check for .log files (kimi)
            for f in expanded.rglob("*.log"):
                if f.is_file():
                    candidates.append(f)
        except PermissionError:
            continue

    # Sort by mtime, newest first
    candidates = list(dict.fromkeys(candidates))
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:120]  # Cap at 120 files


def _norm_path(value: str) -> str:
    return os.path.normpath(os.path.expanduser(value))


def _path_within(child: str, parent: str) -> bool:
    if not child or not parent:
        return False
    try:
        child_n = _norm_path(child)
        parent_n = _norm_path(parent)
        return os.path.commonpath([child_n, parent_n]) == parent_n
    except ValueError:
        return False


def _session_matches_project(session: dict[str, Any], cwd: str) -> bool:
    if not cwd:
        return False
    s_cwd = session.get("cwd") or ""
    if s_cwd:
        if _norm_path(s_cwd) == _norm_path(cwd):
            return True
        if _path_within(cwd, s_cwd) or _path_within(s_cwd, cwd):
            return True
    source_file = session.get("source_file") or ""
    return _path_within(source_file, cwd)


def match_session_to_process(
    sessions: list[dict[str, Any]],
    cwd: str,
    start_ts: float | None = None,
) -> dict[str, Any] | None:
    """Find the best matching session for a process.

    Matching strategy:
    1. Require a cwd/project-local source match.
    2. If multiple matches, pick closest start_ts.
    3. If no trustworthy match exists, return None.
    """
    if not sessions:
        return None

    pool = [s for s in sessions if _session_matches_project(s, cwd)]
    if not pool:
        return None

    if start_ts and len(pool) > 1:
        # Pick closest start_ts
        def _ts_dist(s: dict[str, Any]) -> float:
            s_ts = s.get("start_ts")
            if s_ts is None:
                return float("inf")
            return abs(s_ts - start_ts)

        pool.sort(key=_ts_dist)

    return pool[0] if pool else None


def parse_and_match_sessions(
    agent_type: str,
    project_dir: str,
    process_start_ts: float | None = None,
) -> dict[str, Any] | None:
    """Discover, parse, and match session files to a process.

    High-level entry point: finds session files for the agent type,
    parses each one, and returns the best match for the given project dir.
    """
    files = discover_session_files(agent_type, project_dir)
    if not files:
        return None

    # Parse based on agent type
    parsed: list[dict[str, Any]] = []
    parser = _get_parser(agent_type)
    for f in files[:40]:  # Parse top 40 candidates
        result = parser(f)
        if result:
            parsed.append(result)

    if not parsed:
        return None

    return match_session_to_process(parsed, project_dir, process_start_ts)


def _get_parser(agent_type: str):
    """Get the appropriate parser function for an agent type."""
    if agent_type in ("codex",):
        return parse_codex_session
    if agent_type in ("claude", "claude-code"):
        return parse_claude_session
    if agent_type in ("kimi", "kimi-code"):
        return parse_kimi_session
    # Default: try codex parser (most common format)
    return parse_codex_session
