"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

from backend.models import DiscoveredSession, ProcessInfo, ProjectRuntimeStatus, TaskStatus
from backend.process_scanner import (
    derive_project_name,
    extract_user_instruction,
    get_system_metrics,
    infer_session_activity,
    is_process_alive,
    _format_elapsed,
    _is_sensitive_log_candidate,
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


class TestProjectName:
    def test_projects_path_takes_first_project_segment(self):
        info = derive_project_name("/data/zhouran/agents/projects/01.PreCancerAtlas_A/src/module")

        assert info.display_name == "01.PreCancerAtlas_A"
        assert info.base_project == "PreCancerAtlas"
        assert info.workspace == "A"
        assert info.short_cwd == ".../projects/01.PreCancerAtlas_A"


class TestActivityInference:
    def _proc(self, pid: int, cmd: list[str], cpu: float = 0.0) -> ProcessInfo:
        return ProcessInfo(pid=pid, ppid=1, name=cmd[0], cmdline=cmd, cpu_percent=cpu, memory_percent=0.1)

    def test_testing_has_priority(self):
        result = infer_session_activity([self._proc(1, ["codex"]), self._proc(2, ["pytest", "-q"])], ProjectRuntimeStatus(), [], root_pid=1)

        assert result[0] == TaskStatus.testing

    def test_recent_file_activity_is_editing(self):
        status = ProjectRuntimeStatus(recent_modified_files=["src/api.py"], last_activity_time=datetime.now() - timedelta(seconds=10))
        result = infer_session_activity([self._proc(1, ["codex"])], status, [], root_pid=1)

        assert result[0] == TaskStatus.editing

    def test_waiting_from_log_prompt(self):
        result = infer_session_activity([self._proc(1, ["codex"])], ProjectRuntimeStatus(), ["Approve? continue?"], root_pid=1)

        assert result[0] == TaskStatus.waiting_input


class TestInstructionExtraction:
    def test_rejects_sensitive_log_candidates(self):
        assert _is_sensitive_log_candidate(Path("/home/me/.kimi/credentials/kimi-code.json")) is True
        assert _is_sensitive_log_candidate(Path("/home/me/.codex/models_cache.json")) is True
        assert _is_sensitive_log_candidate(Path("/home/me/.codex/sessions/session.jsonl")) is False

    def test_extracts_jsonl_user_instruction(self, tmp_path: Path, monkeypatch):
        log = tmp_path / "session.jsonl"
        log.write_text('{"role": "user", "content": "Fix the scanner"}\n')
        root = ProcessInfo(pid=10, ppid=1, name="codex", cmdline=["codex"], cwd=str(tmp_path))
        session = DiscoveredSession(session_id="agent-test", cwd=str(tmp_path), root_process=root, root_pid=10, root_cmd="codex", agent_type="codex", started_at=datetime.now())
        session.project.project_dir = str(tmp_path)
        monkeypatch.setattr("backend.process_scanner._candidate_log_files", lambda project_dir, agent_type: [log])

        info = extract_user_instruction(session)

        assert info.text == "Fix the scanner"
        assert info.source_file == str(log)
