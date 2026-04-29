"""Tests for state_machine — status inference, error detection."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from backend.models import Task, TaskStatus
from backend.state_machine import infer_status, check_error_hint


def _make_task(pid: int = 1234, exit_code: int | None = None) -> Task:
    return Task(
        task_id="test",
        name="test",
        project_dir="/tmp/test",
        command="echo",
        pid=pid,
        status=TaskStatus.running,
        started_at=datetime.now(),
        exit_code=exit_code,
    )


class TestInferStatus:
    def test_running_when_alive_with_cpu(self):
        task = _make_task()
        status = infer_status(task, process_alive=True, cpu_percent=50.0, log_path=None)
        assert status == TaskStatus.running

    def test_completed_when_dead_no_error(self):
        task = _make_task(exit_code=0)
        status = infer_status(task, process_alive=False, cpu_percent=0.0, log_path=None)
        assert status == TaskStatus.completed

    def test_failed_when_dead_with_nonzero_exit(self):
        task = _make_task(exit_code=1)
        status = infer_status(task, process_alive=False, cpu_percent=0.0, log_path=None)
        assert status == TaskStatus.failed

    def test_failed_when_dead_with_error_in_log(self, tmp_path: Path):
        task = _make_task()
        log_path = tmp_path / "test.log"
        log_path.write_text("Everything fine\nTraceback (most recent call last):\n")
        status = infer_status(task, process_alive=False, cpu_percent=0.0, log_path=log_path)
        assert status == TaskStatus.failed

    def test_completed_when_dead_no_exit_no_error(self):
        task = _make_task()
        status = infer_status(task, process_alive=False, cpu_percent=0.0, log_path=None)
        assert status == TaskStatus.completed

    def test_idle_when_low_cpu_and_old_log(self, tmp_path: Path):
        task = _make_task()
        log_path = tmp_path / "test.log"
        log_path.write_text("last output\n")
        old_time = (datetime.now() - timedelta(minutes=10)).timestamp()
        os.utime(log_path, (old_time, old_time))

        status = infer_status(task, process_alive=True, cpu_percent=0.1, log_path=log_path)
        assert status == TaskStatus.idle


class TestCheckErrorHint:
    def test_detects_traceback(self, tmp_path: Path):
        log_path = tmp_path / "error.log"
        log_path.write_text("OK\nOK\nTraceback (most recent call last):\n  File ...")
        assert check_error_hint(log_path) is True

    def test_detects_error(self, tmp_path: Path):
        log_path = tmp_path / "error.log"
        log_path.write_text("INFO starting\nERROR: something broke\n")
        assert check_error_hint(log_path) is True

    def test_no_error_hint(self, tmp_path: Path):
        log_path = tmp_path / "ok.log"
        log_path.write_text("All good\nTraining complete\n")
        assert check_error_hint(log_path) is False

    def test_missing_file(self, tmp_path: Path):
        assert check_error_hint(tmp_path / "nope.log") is False

    def test_none_path(self):
        assert check_error_hint(None) is False

    def test_uses_chunked_log_tail(self, tmp_path: Path, monkeypatch):
        log_path = tmp_path / "large.log"
        log_path.write_text("ignored\n")

        called = {}

        def fake_tail(path: Path, lines: int):
            called["path"] = path
            called["lines"] = lines
            return ["ERROR from tail"]

        monkeypatch.setattr("backend.state_machine.get_log_tail", fake_tail)

        assert check_error_hint(log_path) is True
        assert called == {"path": log_path, "lines": 50}
