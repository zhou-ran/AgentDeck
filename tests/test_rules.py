from __future__ import annotations

from pathlib import Path

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
