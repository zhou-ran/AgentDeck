"""Tests for SSE payload helpers."""

from __future__ import annotations

from types import SimpleNamespace

from backend.api.sse import _collect_project_dirs
from backend.models import DiscoveredSession, ProcessInfo


def _session(cwd: str, *, project_root: str = "", project: str = "") -> DiscoveredSession:
    return DiscoveredSession(
        session_id="session-1",
        cwd=cwd,
        root_process=ProcessInfo(
            pid=1,
            ppid=0,
            name="codex",
            cmdline=["codex"],
        ),
        project=project,
        project_root=project_root,
    )


def test_collect_project_dirs_accepts_string_session_project(tmp_path):
    task_dir = tmp_path / "task"
    session_dir = tmp_path / "session"
    task_dir.mkdir()
    session_dir.mkdir()

    dirs = _collect_project_dirs(
        [SimpleNamespace(project_dir=str(task_dir))],
        [_session(str(session_dir), project_root=str(session_dir), project="agentdeck")],
    )

    assert dirs == sorted([str(task_dir), str(session_dir)])


def test_collect_project_dirs_falls_back_to_cwd(tmp_path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    assert _collect_project_dirs([], [_session(str(session_dir), project="agentdeck")]) == [str(session_dir)]
