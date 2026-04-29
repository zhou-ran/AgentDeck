"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time
from collections import namedtuple

from backend.models import ProcessInfo
from backend.process_scanner import (
    AUTO_HIDE_INACTIVE_SECONDS,
    discover_agent_processes,
    discover_sessions,
    get_system_metrics,
    is_process_alive,
    _auto_ignore_reason,
    _format_elapsed,
    _same_user,
)


class TestIsProcessAlive:
    def test_current_process_is_alive(self):
        assert is_process_alive(os.getpid()) is True

    def test_nonexistent_pid_is_not_alive(self):
        assert is_process_alive(999999) is False


class TestFormatElapsed:
    def test_seconds(self):
        result = _format_elapsed(time.time() - 30)
        assert result == "30s"

    def test_minutes(self):
        result = _format_elapsed(time.time() - 150)
        assert "2m" in result

    def test_hours(self):
        result = _format_elapsed(time.time() - 7200)
        assert "2h" in result


class TestSystemMetrics:
    def test_disk_usage_deduplicates_same_mount(self, monkeypatch):
        Partition = namedtuple("Partition", "device mountpoint")
        Usage = namedtuple("Usage", "total used free percent")

        monkeypatch.setattr(
            "backend.process_scanner.psutil.disk_partitions",
            lambda all=False: [Partition("/dev/test", "/data")],
        )
        monkeypatch.setattr(
            "backend.process_scanner.psutil.disk_usage",
            lambda path: Usage(100, 50, 50, 50.0),
        )
        monkeypatch.setattr("backend.process_scanner.psutil.cpu_percent", lambda interval=0: 0.0)
        monkeypatch.setattr(
            "backend.process_scanner.psutil.virtual_memory",
            lambda: namedtuple("Mem", "total used percent")(100, 20, 20.0),
        )
        monkeypatch.setattr(
            "backend.process_scanner.psutil.net_io_counters",
            lambda pernic=True: {},
        )

        metrics = get_system_metrics(["/data/project-a", "/data/project-b"])

        assert len(metrics.disk_usages) == 1
        assert metrics.disk_usages[0]["path"] == "/data"


class TestDiscoverAgentProcesses:
    def test_only_root_agent_processes_are_returned(self, monkeypatch):
        class FakeProc:
            def __init__(self, pid, name, cmdline, parent=None):
                self.info = {"pid": pid, "name": name, "cmdline": cmdline}
                self._parent = parent

            def parent(self):
                return self._parent

        root = FakeProc(10, "node", ["node", "/usr/bin/codex"])
        child = FakeProc(11, "git", ["git", "status"], parent=root)
        python = FakeProc(12, "python", ["python", "script.py"])

        def fake_proc_to_info(proc, include_children=True):
            return ProcessInfo(
                pid=proc.info["pid"],
                ppid=1,
                name=proc.info["name"],
                cmdline=proc.info["cmdline"],
            )

        monkeypatch.setattr("backend.process_scanner.psutil.process_iter", lambda attrs=None: [root, child, python])
        monkeypatch.setattr("backend.process_scanner._proc_to_info", fake_proc_to_info)

        results = discover_agent_processes()

        assert [p.pid for p in results] == [10]

    def test_same_cwd_agents_are_separate_sessions(self, tmp_path, monkeypatch):
        cwd = str(tmp_path)
        codex = ProcessInfo(
            pid=10,
            ppid=1,
            name="node",
            cmdline=["node", "/usr/bin/codex"],
            cwd=cwd,
            create_time=1000,
        )
        kimi = ProcessInfo(
            pid=20,
            ppid=1,
            name="Kimi Code",
            cmdline=["Kimi Code", ""],
            cwd=cwd,
            create_time=1001,
        )

        monkeypatch.setattr("backend.process_scanner.discover_agent_processes", lambda: [codex, kimi])

        sessions = discover_sessions()

        assert len(sessions) == 2
        assert {s.agent_type for s in sessions} == {"codex", "kimi-code"}
        assert len({s.session_id for s in sessions}) == 2


class TestAutoIgnorePolicy:
    def test_same_user_accepts_domain_qualified_names(self):
        assert _same_user("domain\\alice", "alice") is True
        assert _same_user("alice", "alice") is True
        assert _same_user("bob", "alice") is False

    def test_other_user_is_auto_ignored(self):
        session = _session_for_policy(user="bob")

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == "other user: bob"

    def test_heartbeat_older_than_two_hours_is_auto_ignored(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_ts = time.time() - AUTO_HIDE_INACTIVE_SECONDS - 1
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == "inactive for more than 2 hours"

    def test_long_running_without_visible_activity_is_auto_ignored(self):
        session = _session_for_policy(user="alice")
        session.elapsed_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.cpu_percent = 0.1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == "no visible activity for more than 2 hours"

    def test_recent_work_keeps_long_running_session_visible(self):
        session = _session_for_policy(user="alice")
        session.elapsed_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.cpu_percent = 0.1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=["backend/main.py"])

        assert reason == ""


def _session_for_policy(user: str):
    from backend.models import DiscoveredSession

    root = ProcessInfo(
        pid=10,
        ppid=1,
        name="codex",
        cmdline=["codex"],
        cwd="/tmp/project",
        user=user,
        create_time=time.time() - 60,
    )
    session = DiscoveredSession(
        session_id="policy-test",
        cwd="/tmp/project",
        root_process=root,
        agent_type="codex",
        user=user,
    )
    session.elapsed_sec = 60
    session.cpu_percent = 0.0
    return session
