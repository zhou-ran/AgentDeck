from __future__ import annotations

import pytest

from backend.session_sources.base import RawSession, RuntimeTypeResult
from backend.session_sources import discover_all_sessions
from backend.session_sources.tmux import TmuxSessionSource
from backend.session_sources.process import ProcessSessionSource
from backend.session_sources.screen import ScreenSessionSource
from backend.models import ProcessInfo


class TestTmuxSessionSource:
    def test_discover_when_tmux_not_installed(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _cmd: None)
        src = TmuxSessionSource()
        assert src.discover() == []

    def test_list_panes_parsing(self, monkeypatch):
        raw_output = (
            "main|0|0|1234|/home/user/proj|zsh|1|my-title\n"
            "main|0|1|5678|/home/user/other|python|0|\n"
        )

        def fake_run(cmd, **kwargs):
            class FakeResult:
                returncode = 0
                stdout = raw_output
            return FakeResult()

        monkeypatch.setattr("subprocess.run", fake_run)
        src = TmuxSessionSource()
        sessions = src.discover()
        assert len(sessions) == 2
        assert sessions[0].source == "tmux"
        assert sessions[0].source_id == "tmux:main:0.0"
        assert sessions[0].root_pid == 1234
        assert sessions[0].cwd == "/home/user/proj"
        assert sessions[0].command == "zsh"
        assert sessions[0].attached is True
        assert sessions[0].title == "my-title"

        assert sessions[1].source_id == "tmux:main:0.1"
        assert sessions[1].attached is False
        assert sessions[1].title == "main:0.1"

    def test_capture_pane_failure_returns_session_without_output(self, monkeypatch):
        raw_output = "main|0|0|1234|/home/user/proj|zsh|1|title"

        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            class FakeResult:
                returncode = 0 if "list-panes" in cmd else 1
                stdout = raw_output if "list-panes" in cmd else ""
            return FakeResult()

        monkeypatch.setattr("subprocess.run", fake_run)
        monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/bin/tmux")
        src = TmuxSessionSource()
        sessions = src.discover()
        assert len(sessions) == 1
        assert sessions[0].source_id == "tmux:main:0.0"
        assert sessions[0].recent_output is None


class TestProcessSessionSource:
    def test_wraps_discover_agent_processes(self, monkeypatch):
        proc = ProcessInfo(
            pid=42,
            ppid=1,
            name="codex",
            cmdline=["codex"],
            cwd="/tmp/proj",
            create_time=1000.0,
        )
        monkeypatch.setattr(
            "backend.process_scanner.discover_agent_processes", lambda: [proc]
        )
        src = ProcessSessionSource()
        sessions = src.discover()
        assert len(sessions) == 1
        assert sessions[0].source == "process"
        assert sessions[0].source_id == "process:42"
        assert sessions[0].root_pid == 42
        assert sessions[0].cwd == "/tmp/proj"


class TestScreenSessionSource:
    def test_stub_returns_empty(self):
        src = ScreenSessionSource()
        assert src.discover() == []


class TestDiscoverAllSessions:
    def test_deduplicates_by_source_id(self, monkeypatch):
        monkeypatch.setattr(
            "backend.session_sources.TmuxSessionSource.discover",
            lambda self: [
                RawSession(source="tmux", source_id="tmux:a:0.0", root_pid=10),
            ],
        )
        monkeypatch.setattr(
            "backend.session_sources.ScreenSessionSource.discover",
            lambda self: [],
        )
        monkeypatch.setattr(
            "backend.session_sources.ProcessSessionSource.discover",
            lambda self: [
                RawSession(source="process", source_id="process:10", root_pid=10),
                RawSession(source="process", source_id="process:20", root_pid=20),
            ],
        )
        sessions = discover_all_sessions()
        ids = [s.source_id for s in sessions]
        assert "tmux:a:0.0" in ids
        # discover_all_sessions deduplicates by source_id, not by PID
        assert "process:10" in ids
        assert "process:20" in ids

    def test_discover_sessions_drops_process_covered_by_tmux(self, monkeypatch):
        from backend.process_scanner import discover_sessions

        monkeypatch.setattr(
            "backend.session_sources.TmuxSessionSource.discover",
            lambda self: [
                RawSession(source="tmux", source_id="tmux:a:0.0", root_pid=10, cwd="/tmp"),
            ],
        )
        monkeypatch.setattr(
            "backend.session_sources.ScreenSessionSource.discover",
            lambda self: [],
        )
        monkeypatch.setattr(
            "backend.session_sources.ProcessSessionSource.discover",
            lambda self: [
                RawSession(source="process", source_id="process:10", root_pid=10, cwd="/tmp"),
                RawSession(source="process", source_id="process:20", root_pid=20, cwd="/tmp"),
            ],
        )
        monkeypatch.setattr("backend.process_scanner.get_process_tree", lambda pid: None)
        sessions = discover_sessions()
        ids = [s.source_id for s in sessions]
        assert "tmux:a:0.0" in ids
        assert "process:10" not in ids  # dropped because PID 10 is covered by tmux
        assert "process:20" in ids


class TestRuntimeTypeDetection:
    def test_detects_agent(self):
        from backend.process_scanner import detect_runtime_type
        r = detect_runtime_type("node /usr/bin/codex")
        assert r.runtime_type == "agent"
        assert r.detected_app == "codex"

    def test_detects_test(self):
        from backend.process_scanner import detect_runtime_type
        r = detect_runtime_type("pytest -xvs")
        assert r.runtime_type == "test"
        assert r.detected_app == "pytest"

    def test_detects_script(self):
        from backend.process_scanner import detect_runtime_type
        r = detect_runtime_type("python train.py")
        assert r.runtime_type == "script"
        assert r.detected_app == "python"

    def test_unknown_for_empty(self):
        from backend.process_scanner import detect_runtime_type
        r = detect_runtime_type("")
        assert r.runtime_type == "unknown"
