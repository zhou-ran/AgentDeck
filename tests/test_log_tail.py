"""Tests for log_manager — log reading, tail, size."""

from __future__ import annotations

from pathlib import Path

from backend.log_manager import get_log_tail, get_log_size, get_log_mtime


class TestGetLogTail:
    def test_reads_last_n_lines(self, sample_log: Path):
        lines = get_log_tail(sample_log, lines=3)
        assert len(lines) == 3
        assert "Training complete." in lines[-1]

    def test_returns_all_if_fewer_lines(self, sample_log: Path):
        lines = get_log_tail(sample_log, lines=100)
        assert len(lines) == 5

    def test_returns_empty_for_missing(self, tmp_path: Path):
        lines = get_log_tail(tmp_path / "nope.log", lines=50)
        assert lines == []

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.log"
        p.write_text("")
        lines = get_log_tail(p, lines=50)
        assert lines == []


class TestGetLogSize:
    def test_returns_file_size(self, sample_log: Path):
        size = get_log_size(sample_log)
        assert size > 0

    def test_returns_zero_for_missing(self, tmp_path: Path):
        assert get_log_size(tmp_path / "nope.log") == 0


class TestGetLogMtime:
    def test_returns_mtime(self, sample_log: Path):
        mtime = get_log_mtime(sample_log)
        assert mtime > 0

    def test_returns_zero_for_missing(self, tmp_path: Path):
        assert get_log_mtime(tmp_path / "nope.log") == 0.0
