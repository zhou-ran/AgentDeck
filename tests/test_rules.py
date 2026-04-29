from __future__ import annotations

from pathlib import Path

from backend.models import DiscoveredSession, ProcessInfo
from backend import rules


def test_create_delete_and_restore_rules(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(rules, "CONFIG_DIR", tmp_path)

    pin = rules.create_rule("pins", "project_key", "abc123", "重点项目")
    ignored = rules.create_rule("ignored", "project_key", "abc123", "长期忽略")

    assert rules.list_rules("pins")[0].id == pin.id
    assert rules.list_rules("ignored")[0].id == ignored.id

    assert rules.restore_ignored_rule(ignored.id) is True
    assert rules.list_rules("ignored") == []
    assert rules.list_rules("ignored", include_inactive=True)[0].active is False

    assert rules.delete_rule("pins", pin.id) is True
    assert rules.list_rules("pins") == []


def test_session_id_ignore_only_matches_one_session(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(rules, "CONFIG_DIR", tmp_path)

    rules.create_rule("ignored", "session_id", "session-a", "single session")

    shared_root = ProcessInfo(
        pid=10,
        ppid=1,
        name="codex",
        cmdline=["codex"],
        cwd="/tmp/project",
    )
    session_a = DiscoveredSession(
        session_id="session-a",
        project_key="same-project",
        cwd="/tmp/project",
        root_process=shared_root,
    )
    session_b = DiscoveredSession(
        session_id="session-b",
        project_key="same-project",
        cwd="/tmp/project",
        root_process=shared_root,
    )

    assert len(rules.matching_rules("ignored", session_a)) == 1
    assert rules.matching_rules("ignored", session_b) == []
