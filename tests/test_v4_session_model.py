from __future__ import annotations

from pathlib import Path

from backend.models import ProcessInfo
from backend.process_scanner import (
    build_background_jobs,
    detect_agent_type,
    derive_project_key,
)


def test_project_key_is_stable_for_same_git_root(tmp_path: Path):
    root = tmp_path / "repo"
    child = root / "src"
    child.mkdir(parents=True)

    assert derive_project_key(str(child), str(root)) == derive_project_key(str(root), str(root))


def test_detect_agent_type_returns_evidence_from_process_cmd():
    proc = ProcessInfo(pid=10, ppid=1, name="node", cmdline=["node", "/usr/bin/codex"])

    result = detect_agent_type(proc, [], "/tmp/project")

    assert result.agent_type == "codex"
    assert result.confidence >= 0.8
    assert result.evidence


def test_detect_agent_type_uses_session_source_when_process_is_generic(tmp_path: Path):
    proc = ProcessInfo(pid=10, ppid=1, name="node", cmdline=["node", "cli.js"])
    source = tmp_path / ".kimi-code" / "session.jsonl"
    source.parent.mkdir()
    source.write_text("{}\n")

    result = detect_agent_type(proc, [str(source)], str(tmp_path))

    assert result.agent_type == "kimi-code"
    assert result.reason == "matched session source dir"


def test_detect_agent_type_uses_log_marker_when_process_is_generic(tmp_path: Path):
    proc = ProcessInfo(pid=10, ppid=1, name="node", cmdline=["node", "cli.js"])
    source = tmp_path / "agent.log"
    source.write_text("starting Kimi Code session\n")

    result = detect_agent_type(proc, [str(source)], str(tmp_path))

    assert result.agent_type == "kimi-code"
    assert result.reason == "matched session/log content"


def test_background_jobs_classify_recursive_children():
    pytest_proc = ProcessInfo(pid=20, ppid=10, name="pytest", cmdline=["pytest", "tests/"])
    vite_proc = ProcessInfo(pid=21, ppid=10, name="node", cmdline=["node", "vite"])
    root = ProcessInfo(pid=10, ppid=1, name="codex", cmdline=["codex"], children=[pytest_proc, vite_proc])

    jobs = build_background_jobs(root)

    assert {job.job_type for job in jobs} == {"test", "dev_server"}
