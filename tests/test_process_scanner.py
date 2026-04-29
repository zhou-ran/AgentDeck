"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time
from collections import namedtuple

from backend.process_scanner import get_system_metrics, is_process_alive, _format_elapsed


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
