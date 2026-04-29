"""Tests for safe git command wrapper."""

from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from backend.git_utils import run_git_command


def test_rejects_unlisted_git_command(tmp_path: Path, monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr("backend.git_utils.subprocess.run", fake_run)

    result = run_git_command(str(tmp_path), ["log", "-1"])

    assert result is None
    assert called is False


def test_allows_exact_readonly_command(tmp_path: Path, monkeypatch):
    def fake_run(*args, **kwargs):
        assert args[0] == ["git", "status", "--short"]
        assert kwargs["cwd"] == str(tmp_path.resolve())
        assert kwargs["timeout"] == 10
        return CompletedProcess(args[0], 0, stdout=" M file.py\n", stderr="")

    monkeypatch.setattr("backend.git_utils.subprocess.run", fake_run)

    result = run_git_command(str(tmp_path), ["status", "--short"])

    assert result == "M file.py"


def test_rejects_cwd_outside_project(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path.parent

    result = run_git_command(str(project), ["status", "--short"], cwd=str(outside))

    assert result is None
