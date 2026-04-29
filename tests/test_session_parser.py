"""Tests for backend.session_parser module."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from backend.session_parser import (
    discover_session_files,
    match_session_to_process,
    parse_and_match_sessions,
    parse_claude_session,
    parse_codex_session,
    parse_kimi_session,
)


# ---- Fixtures ----

@pytest.fixture
def codex_session_file(tmp_path: Path) -> Path:
    """Create a synthetic codex session .jsonl file."""
    f = tmp_path / "codex-session.jsonl"
    lines = [
        # First line: session_meta
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": "sess-abc123",
                "cwd": str(tmp_path / "my-project"),
                "timestamp": "2026-04-28T10:00:00Z",
            },
            "timestamp": "2026-04-28T10:00:00Z",
        }),
        # Response item with assistant message
        json.dumps({
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "I'll help you fix the bug in main.py"}],
            },
            "timestamp": "2026-04-28T10:01:00Z",
        }),
        # Plan update
        json.dumps({
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "update_plan",
                "arguments": json.dumps({
                    "plan": [
                        {"step": "Read the file", "status": "completed"},
                        {"step": "Fix the bug", "status": "in_progress"},
                        {"step": "Run tests", "status": "pending"},
                    ]
                }),
            },
            "timestamp": "2026-04-28T10:02:00Z",
        }),
        # User message
        json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Please fix the TypeError in main.py line 42",
            },
            "timestamp": "2026-04-28T10:03:00Z",
        }),
    ]
    f.write_text("\n".join(lines) + "\n")
    return f


@pytest.fixture
def claude_session_file(tmp_path: Path) -> Path:
    """Create a synthetic claude session .jsonl file."""
    f = tmp_path / "claude-session.jsonl"
    lines = [
        json.dumps({
            "type": "user",
            "message": {"content": "Help me refactor the auth module"},
            "timestamp": "2026-04-28T10:00:00Z",
            "cwd": str(tmp_path / "auth-project"),
            "gitBranch": "feature/auth-refactor",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "I'll start by examining the current auth module structure."}]
            },
            "timestamp": "2026-04-28T10:01:00Z",
        }),
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Found 3 files to refactor: auth.py, middleware.py, and session.py"}]
            },
            "timestamp": "2026-04-28T10:02:00Z",
        }),
    ]
    f.write_text("\n".join(lines) + "\n")
    return f


@pytest.fixture
def kimi_session_file(tmp_path: Path) -> Path:
    """Create a synthetic kimi session file."""
    f = tmp_path / "kimi-session.jsonl"
    lines = [
        json.dumps({
            "role": "user",
            "content": "帮我优化数据库查询",
            "timestamp": "2026-04-28T10:00:00Z",
            "cwd": str(tmp_path / "db-project"),
        }),
        json.dumps({
            "role": "assistant",
            "content": "我来分析一下查询性能问题",
            "timestamp": "2026-04-28T10:01:00Z",
        }),
    ]
    f.write_text("\n".join(lines) + "\n")
    return f


# ---- Test parse_codex_session ----

class TestParseCodexSession:
    def test_basic_parse(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert result["session_id"] == "sess-abc123"
        assert result["cwd"] is not None

    def test_recent_output(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert "fix the bug" in result["recent_output"].lower()

    def test_last_user_message(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert "TypeError" in result["last_user_message"]

    def test_source_file(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert result["source_file"] == str(codex_session_file)

    def test_pending_items(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        # Should have pending items from the plan update
        assert len(result["pending_items"]) > 0

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = parse_codex_session(f)
        # Empty file should still return a dict with defaults
        assert result is not None
        assert result["recent_output"] == ""

    def test_invalid_json(self, tmp_path: Path):
        f = tmp_path / "bad.jsonl"
        f.write_text("not json\n{bad json\n")
        result = parse_codex_session(f)
        assert result is not None
        assert result["recent_output"] == ""


# ---- Test parse_claude_session ----

class TestParseClaudeSession:
    def test_basic_parse(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["session_id"] == "claude-session"

    def test_git_branch(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["git_branch"] == "feature/auth-refactor"

    def test_recent_output(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert len(result["recent_output"]) > 0

    def test_last_user_message(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert "refactor" in result["last_user_message"].lower()

    def test_heartbeat_ts(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["heartbeat_ts"] > 0

    def test_cwd(self, claude_session_file: Path, tmp_path: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert "auth-project" in (result["cwd"] or "")


# ---- Test parse_kimi_session ----

class TestParseKimiSession:
    def test_basic_parse(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        assert result["session_id"] == "kimi-session"

    def test_recent_output(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        # Kimi uses Chinese content
        assert len(result["recent_output"]) > 0

    def test_last_user_message(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        assert len(result["last_user_message"]) > 0


# ---- Test discover_session_files ----

class TestDiscoverSessionFiles:
    def test_discover_in_tmp(self, tmp_path: Path):
        # Create a fake session directory
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        (session_dir / "session1.jsonl").write_text("{}\n")
        (session_dir / "session2.jsonl").write_text("{}\n")

        files = discover_session_files("codex", str(tmp_path))
        # Should find files (may be empty if paths don't exist, but function shouldn't crash)
        assert isinstance(files, list)

    def test_unknown_agent_type(self, tmp_path: Path):
        files = discover_session_files("unknown-agent", str(tmp_path))
        assert isinstance(files, list)

    def test_project_local_kimi_paths(self, tmp_path: Path):
        session_dir = tmp_path / ".kimi"
        session_dir.mkdir()
        session_file = session_dir / "session.jsonl"
        session_file.write_text("{}\n")

        files = discover_session_files("kimi-code", str(tmp_path))

        assert session_file.resolve() in [f.resolve() for f in files]


# ---- Test match_session_to_process ----

class TestMatchSessionToProcess:
    def test_match_by_cwd(self):
        sessions = [
            {"cwd": "/home/user/project-a", "start_ts": 1000, "session_id": "a"},
            {"cwd": "/home/user/project-b", "start_ts": 2000, "session_id": "b"},
        ]
        result = match_session_to_process(sessions, "/home/user/project-a", 1000)
        assert result is not None
        assert result["session_id"] == "a"

    def test_match_by_closest_start_ts(self):
        sessions = [
            {"cwd": "/home/user/project", "start_ts": 1000, "session_id": "early"},
            {"cwd": "/home/user/project", "start_ts": 5000, "session_id": "late"},
        ]
        result = match_session_to_process(sessions, "/home/user/project", 4900)
        assert result is not None
        assert result["session_id"] == "late"

    def test_no_match_empty_sessions(self):
        result = match_session_to_process([], "/any/path", 0)
        assert result is None

    def test_no_match_different_cwd(self):
        sessions = [
            {"cwd": "/other/unique-project-a", "start_ts": 1000, "session_id": "a"},
        ]
        result = match_session_to_process(sessions, "/my/unique-project-b", 1000)
        # Must not fall back to an unrelated latest session.
        assert result is None

    def test_match_by_project_local_source_file(self):
        sessions = [
            {
                "cwd": None,
                "start_ts": 1000,
                "session_id": "local",
                "source_file": "/home/user/project/.codex/session.jsonl",
            },
        ]
        result = match_session_to_process(sessions, "/home/user/project", 1000)
        assert result is not None
        assert result["session_id"] == "local"
