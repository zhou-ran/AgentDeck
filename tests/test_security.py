"""Tests for security — path safety, task_id validation, symlink detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.security import (
    is_valid_task_id,
    is_safe_project_dir,
    is_path_within,
    atomic_write,
    sanitize_note,
    RateLimiter,
)


class TestTaskIdValidation:
    @pytest.mark.parametrize("task_id", [
        "my-task",
        "task_123",
        "training.run1",
        "a",
        "A1",
        "test-task-2025",
    ])
    def test_valid_ids(self, task_id: str):
        assert is_valid_task_id(task_id) is True

    @pytest.mark.parametrize("task_id", [
        "",
        "../etc",
        "task with spaces",
        "task/slash",
        "task\\backslash",
        ".hidden",
        "-start",
        "a" * 129,
    ])
    def test_invalid_ids(self, task_id: str):
        assert is_valid_task_id(task_id) is False


class TestSafeProjectDir:
    def test_valid_directory(self, tmp_path: Path):
        ok, reason = is_safe_project_dir(str(tmp_path))
        assert ok is True

    def test_rejects_relative_path(self):
        ok, reason = is_safe_project_dir("relative/path")
        assert ok is False
        assert "absolute" in reason

    def test_rejects_nonexistent(self):
        ok, reason = is_safe_project_dir("/nonexistent/path/xyz")
        assert ok is False
        assert "does not exist" in reason

    def test_rejects_etc(self):
        ok, reason = is_safe_project_dir("/etc")
        assert ok is False
        assert "sensitive" in reason

    def test_rejects_symlink(self, tmp_path: Path):
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real_dir)
        ok, reason = is_safe_project_dir(str(link))
        assert ok is False
        assert "symlink" in reason

    def test_rejects_dot_dot(self, tmp_path: Path):
        ok, reason = is_safe_project_dir(str(tmp_path / ".." / "etc"))
        assert ok is False


class TestPathWithin:
    def test_child_is_within_parent(self, tmp_path: Path):
        child = tmp_path / "sub" / "dir"
        assert is_path_within(child, tmp_path) is True

    def test_same_path(self, tmp_path: Path):
        assert is_path_within(tmp_path, tmp_path) is True

    def test_outside_parent(self, tmp_path: Path):
        other = Path("/tmp/other")
        assert is_path_within(other, tmp_path) is False


class TestAtomicWrite:
    def test_writes_content(self, tmp_path: Path):
        p = tmp_path / "test.json"
        atomic_write(p, '{"key": "value"}')
        assert p.read_text() == '{"key": "value"}'

    def test_creates_parent_dirs(self, tmp_path: Path):
        p = tmp_path / "deep" / "nested" / "file.txt"
        atomic_write(p, "hello")
        assert p.read_text() == "hello"

    def test_overwrites_existing(self, tmp_path: Path):
        p = tmp_path / "test.txt"
        atomic_write(p, "first")
        atomic_write(p, "second")
        assert p.read_text() == "second"

    def test_no_temp_files_on_success(self, tmp_path: Path):
        p = tmp_path / "test.txt"
        atomic_write(p, "content")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestSanitizeNote:
    def test_strips_null_bytes(self):
        result = sanitize_note("hello\x00world")
        assert "\x00" not in result

    def test_truncates_long_input(self):
        long = "a" * 20000
        result = sanitize_note(long, max_len=10000)
        assert len(result) == 10000

    def test_preserves_normal_text(self):
        result = sanitize_note("Normal note with emojis")
        assert result == "Normal note with emojis"


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client1")
        assert limiter.is_allowed("client1") is False

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.is_allowed("client1")
        assert limiter.is_allowed("client2") is True
