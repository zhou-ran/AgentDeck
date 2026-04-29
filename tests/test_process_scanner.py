"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time
from collections import namedtuple

from backend.models import ProcessInfo
from backend.process_scanner import (
    discover_agent_processes,
    discover_sessions,
    get_system_metrics,
    is_process_alive,
    _format_elapsed,
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
