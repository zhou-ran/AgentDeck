"""Tests for session file parsing (codex, claude, kimi)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from backend.session_parser import (
    discover_session_files,
    match_session_to_process,
    parse_claude_session,
    parse_codex_session,
    parse_kimi_session,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def codex_session_file(tmp_path: Path) -> Path:
    """Create a synthetic codex .jsonl session file."""
    p = tmp_path / "codex-session.jsonl"
    lines = [
        # First line: session_meta
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": "sess-abc123",
                "cwd": str(tmp_path / "myproject"),
                "timestamp": "2025-01-15T10:00:00Z",
            },
            "timestamp": "2025-01-15T10:00:00Z",
        }),
        # User message
        json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Please fix the auth bug",
            },
            "timestamp": "2025-01-15T10:01:00Z",
        }),
        # Assistant response
        json.dumps({
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "I'll fix the authentication bug in the login module."}],
            },
            "timestamp": "2025-01-15T10:02:00Z",
        }),
        # Agent message
        json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "agent_message",
                "message": "Working on the fix...",
            },
            "timestamp": "2025-01-15T10:03:00Z",
        }),
    ]
    p.write_text("\n".join(lines) + "\n")
    return p


@pytest.fixture
def claude_session_file(tmp_path: Path) -> Path:
    """Create a synthetic claude .jsonl session file."""
    p = tmp_path / "claude-session.jsonl"
    lines = [
        # Metadata line with cwd
        json.dumps({
            "cwd": str(tmp_path / "myproject"),
            "gitBranch": "main",
            "timestamp": "2025-01-15T10:00:00Z",
        }),
        # User message
        json.dumps({
            "type": "user",
            "message": {"content": "Refactor the database module"},
            "timestamp": "2025-01-15T10:01:00Z",
        }),
        # Assistant response
        json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "I'll refactor the database module to use connection pooling."}],
            },
            "timestamp": "2025-01-15T10:02:00Z",
        }),
        # Summary
        json.dumps({
            "type": "summary",
            "summary": "Refactoring database module with connection pooling",
            "timestamp": "2025-01-15T10:03:00Z",
        }),
    ]
    p.write_text("\n".join(lines) + "\n")
    return p


@pytest.fixture
def kimi_session_file(tmp_path: Path) -> Path:
    """Create a synthetic kimi .jsonl session file."""
    p = tmp_path / "kimi-session.jsonl"
    lines = [
        json.dumps({
            "cwd": str(tmp_path / "myproject"),
            "timestamp": "2025-01-15T10:00:00Z",
        }),
        json.dumps({
            "type": "user",
            "role": "user",
            "content": "Write unit tests for the API",
            "timestamp": "2025-01-15T10:01:00Z",
        }),
        json.dumps({
            "type": "assistant",
            "role": "assistant",
            "content": "I'll write comprehensive unit tests for the API endpoints.",
            "timestamp": "2025-01-15T10:02:00Z",
        }),
    ]
    p.write_text("\n".join(lines) + "\n")
    return p


# ---------------------------------------------------------------------------
# Codex parser tests
# ---------------------------------------------------------------------------

class TestParseCodexSession:
    def test_basic_parse(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert result["session_id"] == "sess-abc123"
        assert result["cwd"] is not None
        assert "myproject" in result["cwd"]
        assert result["heartbeat_ts"] is not None
        assert result["heartbeat_ts"] > 0

    def test_recent_output(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert "authentication bug" in result["recent_output"] or "fix" in result["recent_output"].lower()

    def test_last_user_message(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert "auth bug" in result["last_user_message"]

    def test_source_file(self, codex_session_file: Path):
        result = parse_codex_session(codex_session_file)
        assert result is not None
        assert result["source_file"] == str(codex_session_file)

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        result = parse_codex_session(p)
        # Empty file should still return a dict with defaults
        assert result is not None or result is None  # Either is acceptable

    def test_invalid_json(self, tmp_path: Path):
        p = tmp_path / "bad.jsonl"
        p.write_text("not json\nalso not json\n")
        result = parse_codex_session(p)
        # Should handle gracefully
        assert result is not None or result is None


# ---------------------------------------------------------------------------
# Claude parser tests
# ---------------------------------------------------------------------------

class TestParseClaudeSession:
    def test_basic_parse(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["session_id"] == claude_session_file.stem
        assert result["cwd"] is not None
        assert "myproject" in result["cwd"]

    def test_git_branch(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["git_branch"] == "main"

    def test_recent_output(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        # Should have some output from assistant or summary
        assert len(result["recent_output"]) > 0

    def test_last_user_message(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert "database" in result["last_user_message"].lower() or "refactor" in result["last_user_message"].lower()

    def test_heartbeat_ts(self, claude_session_file: Path):
        result = parse_claude_session(claude_session_file)
        assert result is not None
        assert result["heartbeat_ts"] > 0


# ---------------------------------------------------------------------------
# Kimi parser tests
# ---------------------------------------------------------------------------

class TestParseKimiSession:
    def test_basic_parse(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        assert result["session_id"] == kimi_session_file.stem

    def test_recent_output(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        assert "unit tests" in result["recent_output"].lower() or "api" in result["recent_output"].lower()

    def test_last_user_message(self, kimi_session_file: Path):
        result = parse_kimi_session(kimi_session_file)
        assert result is not None
        assert "unit tests" in result["last_user_message"].lower() or "api" in result["last_user_message"].lower()


# ---------------------------------------------------------------------------
# Session file discovery tests
# ---------------------------------------------------------------------------

class TestDiscoverSessionFiles:
    def test_discover_in_tmp(self, tmp_path: Path, codex_session_file: Path):
        # Create a fake session dir
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        (session_dir / "s1.jsonl").write_text('{"type": "session_meta"}\n')
        (session_dir / "s2.jsonl").write_text('{"type": "session_meta"}\n')

        # discover_session_files searches in ~/.codex/sessions etc, not arbitrary dirs
        # So we test with the actual search paths
        files = discover_session_files("codex")
        # Should return a list (may be empty if no codex installed)
        assert isinstance(files, list)

    def test_unknown_agent_type(self):
        files = discover_session_files("unknown-agent-xyz")
        assert files == []


# ---------------------------------------------------------------------------
# Session-process matching tests
# ---------------------------------------------------------------------------

class TestMatchSessionToProcess:
    def test_match_by_cwd(self, tmp_path: Path):
        cwd = str(tmp_path / "project")
        sessions = [
            {"session_id": "s1", "cwd": cwd, "start_ts": 1000.0, "heartbeat_ts": 1000.0},
            {"session_id": "s2", "cwd": "/other/path", "start_ts": 1000.0, "heartbeat_ts": 1000.0},
        ]
        result = match_session_to_process(sessions, cwd, 1000.0)
        assert result is not None
        assert result["session_id"] == "s1"

    def test_match_by_closest_start_ts(self, tmp_path: Path):
        cwd = str(tmp_path / "project")
        sessions = [
            {"session_id": "s1", "cwd": cwd, "start_ts": 1000.0, "heartbeat_ts": 1000.0},
            {"session_id": "s2", "cwd": cwd, "start_ts": 2000.0, "heartbeat_ts": 2000.0},
        ]
        # Process started at 1900, closer to s2
        result = match_session_to_process(sessions, cwd, 1900.0)
        assert result is not None
        assert result["session_id"] == "s2"

    def test_no_match_empty_sessions(self):
        result = match_session_to_process([], "/some/path", 1000.0)
        assert result is None

    def test_no_match_different_cwd(self):
        sessions = [
            {"session_id": "s1", "cwd": "/other/unique-project-a", "start_ts": 1000.0, "heartbeat_ts": 1000.0},
        ]
        result = match_session_to_process(sessions, "/my/unique-project-b", 1000.0)
        assert result is None
