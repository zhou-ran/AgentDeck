"""Tests for activity inference and status detection."""
from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from backend.models import ProcessInfo, ProjectRuntimeStatus, TaskStatus
from backend.process_scanner import infer_session_activity


def _make_process(pid: int = 1000, name: str = "agent", cmdline: list[str] | None = None, cpu: float = 0.0) -> ProcessInfo:
    return ProcessInfo(
        pid=pid, ppid=1, name=name,
        cmdline=cmdline or [name],
        cwd="/tmp/project", user="test",
        status="S", cpu_percent=cpu, memory_percent=1.0,
        create_time=time.time() - 3600, elapsed="1h0m",
    )


def _make_project_status(
    branch: str = "main",
    dirty: int = 0,
    tests: list[str] | None = None,
    errors: list[str] | None = None,
    last_activity: datetime | None = None,
) -> ProjectRuntimeStatus:
    return ProjectRuntimeStatus(
        git_branch=branch,
        git_dirty_files_count=dirty,
        test_processes=tests or [],
        error_hints=errors or [],
        last_activity_time=last_activity,
    )


class TestNeedsInput:
    def test_question_mark_in_output(self):
        procs = [_make_process()]
        ps = _make_project_status()
        status, reason, activity = infer_session_activity(
            procs, ps, [], 1000,
            recent_output="Which approach would you like to use?",
        )
        assert status == TaskStatus.waiting_input

    def test_please_provide(self):
        procs = [_make_process()]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            recent_output="Please provide the API key",
        )
        assert status == TaskStatus.waiting_input

    def test_chinese_waiting(self):
        procs = [_make_process()]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            recent_output="请确认是否继续",
        )
        assert status == TaskStatus.waiting_input

    def test_let_me_know(self):
        procs = [_make_process()]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            recent_output="Let me know when you're ready",
        )
        assert status == TaskStatus.waiting_input


class TestTesting:
    def test_pytest_child(self):
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="pytest", cmdline=["pytest", "-v"]),
        ]
        ps = _make_project_status()
        status, reason, activity = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.testing
        assert "pytest" in reason

    def test_npm_test_child(self):
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="npm", cmdline=["npm", "test"]),
        ]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.testing


class TestGitOps:
    def test_git_child(self):
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="git", cmdline=["git", "status"]),
        ]
        ps = _make_project_status()
        status, reason, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.git_ops
        assert "git" in reason.lower()


class TestSearching:
    def test_rg_child(self):
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="rg", cmdline=["rg", "TODO"]),
        ]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.searching


class TestRunningScript:
    def test_python_child(self):
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="python", cmdline=["python", "train.py"]),
        ]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.running_script


class TestEditing:
    def test_recent_file_modification(self):
        procs = [_make_process()]
        ps = _make_project_status(last_activity=datetime.now() - timedelta(seconds=30))
        status, reason, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.editing
        assert "60s" in reason or "file" in reason.lower()


class TestBusy:
    def test_high_cpu(self):
        procs = [_make_process(cpu=50.0)]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.busy

    def test_recent_heartbeat(self):
        procs = [_make_process()]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            heartbeat_ts=time.time() - 30,  # 30 seconds ago
        )
        assert status == TaskStatus.busy


class TestIdle:
    def test_no_activity(self):
        procs = [_make_process(cpu=0.0)]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.idle

    def test_stale_heartbeat(self):
        procs = [_make_process(cpu=0.0)]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            heartbeat_ts=time.time() - 1000,  # 1000 seconds ago
        )
        assert status == TaskStatus.idle


class TestPriorityChain:
    def test_needs_input_takes_priority_over_testing(self):
        """needs_input should be detected even if pytest is running."""
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="pytest", cmdline=["pytest"]),
        ]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(
            procs, ps, [], 1000,
            recent_output="Which test should I run?",
        )
        assert status == TaskStatus.waiting_input

    def test_testing_takes_priority_over_git(self):
        """testing should be detected before git_ops."""
        procs = [
            _make_process(pid=1000),
            _make_process(pid=1001, name="pytest", cmdline=["pytest"]),
            _make_process(pid=1002, name="git", cmdline=["git", "status"]),
        ]
        ps = _make_project_status()
        status, _, _ = infer_session_activity(procs, ps, [], 1000)
        assert status == TaskStatus.testing
