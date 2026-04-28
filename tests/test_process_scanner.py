"""Tests for process_scanner — PID validation, process detection."""

from __future__ import annotations

import os
import time

from backend.process_scanner import is_process_alive, _format_elapsed


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
