"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time
from collections import namedtuple

from backend.models import ProcessInfo
from backend.process_scanner import (
    AUTO_HIDE_INACTIVE_SECONDS,
    STALE_INACTIVE_SECONDS,
    discover_agent_processes,
    discover_sessions,
    extract_user_instruction,
    get_system_metrics,
    is_process_alive,
    _candidate_log_files,
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


class TestSessionInstructionSources:
    def test_session_data_without_user_message_does_not_fall_back_to_logs(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "session.log").write_text("Instruction: wrong session\n", encoding="utf-8")

        instruction = extract_user_instruction(
            str(tmp_path),
            "codex",
            {"source_file": "/home/user/.codex/sessions/current.jsonl"},
        )

        assert instruction.text == "未找到原始指令"
        assert instruction.source == ""

    def test_global_agent_logs_are_not_project_candidates_by_default(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        global_logs = home / "agent_logs"
        global_logs.mkdir(parents=True)
        global_log = global_logs / "other-session.log"
        global_log.write_text("Instruction: other session\n", encoding="utf-8")
        project = tmp_path / "project"
        project.mkdir()

        monkeypatch.setattr("backend.process_scanner.Path.home", lambda: home)

        assert global_log not in _candidate_log_files(str(project))
        assert global_log in _candidate_log_files(str(project), include_global=True)


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

    def test_heartbeat_older_than_two_hours_is_not_auto_ignored(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_ts = time.time() - STALE_INACTIVE_SECONDS - 1
        session.heartbeat_age_sec = STALE_INACTIVE_SECONDS + 1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == ""

    def test_six_hour_heartbeat_without_visible_activity_is_auto_ignored(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_ts = time.time() - AUTO_HIDE_INACTIVE_SECONDS - 1
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.cpu_percent = 0.1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == "no visible activity for more than 6 hours"

    def test_long_running_without_visible_activity_is_auto_ignored_after_six_hours(self):
        session = _session_for_policy(user="alice")
        session.elapsed_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.cpu_percent = 0.1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == "no visible activity for more than 6 hours"

    def test_recent_work_keeps_long_running_session_visible(self):
        session = _session_for_policy(user="alice")
        session.elapsed_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.cpu_percent = 0.1

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=["backend/main.py"])

        assert reason == ""

    def test_pinned_session_is_never_auto_ignored_for_inactivity(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.is_pinned = True

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == ""

    def test_waiting_session_is_not_auto_ignored_for_inactivity(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.status = "needs_input"

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == ""

    def test_failed_session_is_not_auto_ignored_for_inactivity(self):
        session = _session_for_policy(user="alice")
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.status = "failed"

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

        assert reason == ""

    def test_background_job_session_is_not_auto_ignored_for_inactivity(self):
        from backend.models import BackgroundJob

        session = _session_for_policy(user="alice")
        session.heartbeat_age_sec = AUTO_HIDE_INACTIVE_SECONDS + 1
        session.background_jobs = [BackgroundJob(pid=20, ppid=10, cmd="npm run dev", job_type="dev_server", status="running")]

        reason = _auto_ignore_reason(session, server_user="alice", recent_files=[])

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
