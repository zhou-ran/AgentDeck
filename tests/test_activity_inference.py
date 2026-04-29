"""Tests for activity inference logic in process_scanner."""
from __future__ import annotations

import time

import pytest

from backend.process_scanner import infer_session_activity
from backend.models import ProcessInfo


def _make_process(
    name: str = "node",
    cmdline: list[str] | None = None,
    cpu_percent: float = 0.0,
    children: list[ProcessInfo] | None = None,
) -> ProcessInfo:
    """Helper to create a ProcessInfo for testing."""
    return ProcessInfo(
        pid=1000,
        ppid=1,
        name=name,
        cmdline=cmdline or [name],
        cpu_percent=cpu_percent,
        children=children or [],
    )


def _make_child(name: str, cmdline: list[str] | None = None) -> ProcessInfo:
    """Helper to create a child ProcessInfo."""
    return ProcessInfo(
        pid=2000,
        ppid=1000,
        name=name,
        cmdline=cmdline or [name],
    )


class TestNeedsInput:
    def test_question_mark(self):
        proc = _make_process()
        activity, reason = infer_session_activity(
            proc, recent_output="Which approach would you prefer?"
        )
        assert activity == "waiting_input"

    def test_please_provide(self):
        proc = _make_process()
        activity, _ = infer_session_activity(
            proc, recent_output="Please provide the database credentials."
        )
        assert activity == "waiting_input"

    def test_chinese_waiting(self):
        proc = _make_process()
        activity, _ = infer_session_activity(
            proc, recent_output="请确认是否需要继续"
        )
        assert activity == "waiting_input"

    def test_let_me_know(self):
        proc = _make_process()
        activity, _ = infer_session_activity(
            proc, recent_output="Let me know when you're ready"
        )
        assert activity == "waiting_input"


class TestTesting:
    def test_pytest_child(self):
        child = _make_child("pytest", ["pytest", "tests/"])
        proc = _make_process(children=[child])
        activity, reason = infer_session_activity(proc)
        assert activity == "testing"
        assert "pytest" in reason.lower() or "test" in reason.lower()

    def test_npm_test_child(self):
        child = _make_child("npm", ["npm", "test"])
        proc = _make_process(children=[child])
        activity, _ = infer_session_activity(proc)
        assert activity == "testing"


class TestGitOps:
    def test_git_child(self):
        child = _make_child("git", ["git", "commit", "-m", "fix"])
        proc = _make_process(children=[child])
        activity, reason = infer_session_activity(proc)
        assert activity == "git_ops"
        assert "git" in reason.lower()


class TestSearching:
    def test_rg_child(self):
        child = _make_child("rg", ["rg", "pattern", "src/"])
        proc = _make_process(children=[child])
        activity, reason = infer_session_activity(proc)
        assert activity == "searching"


class TestRunningScript:
    def test_python_child(self):
        child = _make_child("python3", ["python3", "run.py"])
        proc = _make_process(children=[child])
        activity, reason = infer_session_activity(proc)
        assert activity == "running_script"
        assert "python" in reason.lower() or "run" in reason.lower()


class TestEditing:
    def test_recent_file_modification(self):
        proc = _make_process()
        activity, reason = infer_session_activity(
            proc, recent_files=["src/main.py", "src/utils.py"]
        )
        assert activity == "editing"
        assert "main.py" in reason or "file" in reason.lower()


class TestBusy:
    def test_high_cpu(self):
        proc = _make_process(cpu_percent=5.0)
        activity, reason = infer_session_activity(proc)
        assert activity == "busy"
        assert "cpu" in reason.lower() or "5" in reason

    def test_recent_heartbeat(self):
        proc = _make_process()
        activity, _ = infer_session_activity(
            proc, heartbeat_ts=time.time() - 30
        )
        assert activity == "busy"


class TestIdle:
    def test_no_activity(self):
        proc = _make_process()
        activity, _ = infer_session_activity(proc)
        assert activity == "idle"

    def test_stale_heartbeat(self):
        proc = _make_process()
        activity, reason = infer_session_activity(
            proc, heartbeat_ts=time.time() - 1000
        )
        assert activity == "idle"
        assert "stale" in reason.lower() or "no activity" in reason.lower()


class TestPriorityChain:
    def test_needs_input_over_testing(self):
        """needs_input should take priority over testing."""
        child = _make_child("pytest", ["pytest"])
        proc = _make_process(children=[child])
        activity, _ = infer_session_activity(
            proc,
            recent_output="Which option should I choose?",
        )
        assert activity == "waiting_input"

    def test_testing_over_git(self):
        """testing should take priority over git_ops."""
        test_child = _make_child("pytest", ["pytest"])
        git_child = _make_child("git", ["git", "status"])
        proc = _make_process(children=[test_child, git_child])
        activity, _ = infer_session_activity(proc)
        assert activity == "testing"
