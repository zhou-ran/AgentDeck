from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from backend.models import Rule

RuleKind = Literal["pins", "ignored"]

CONFIG_DIR = Path.home() / ".agentdeck"
RULE_FILES: dict[RuleKind, str] = {
    "pins": "pins.json",
    "ignored": "ignored.json",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rule_path(kind: RuleKind) -> Path:
    return CONFIG_DIR / RULE_FILES[kind]


def _prefix(kind: RuleKind) -> str:
    return "pin" if kind == "pins" else "ignore"


def _load_payload(kind: RuleKind) -> dict:
    path = _rule_path(kind)
    if not path.exists():
        return {"version": 1, "rules": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("rules"), list):
            raise ValueError("invalid rule file shape")
        return {"version": int(payload.get("version", 1)), "rules": payload["rules"]}
    except Exception:
        broken = path.with_name(f"{path.name}.broken.{int(time.time())}")
        try:
            path.replace(broken)
        except OSError:
            pass
        return {"version": 1, "rules": []}


def _save_payload(kind: RuleKind, payload: dict) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = _rule_path(kind)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def list_rules(kind: RuleKind, include_inactive: bool = False) -> list[Rule]:
    payload = _load_payload(kind)
    rules = [Rule(**item) for item in payload.get("rules", []) if isinstance(item, dict)]
    if kind == "ignored" and not include_inactive:
        rules = [rule for rule in rules if rule.active]
    return rules


def create_rule(kind: RuleKind, rule_type: str, value: str, note: str = "") -> Rule:
    payload = _load_payload(kind)
    rule = Rule(
        id=f"{_prefix(kind)}_{uuid.uuid4().hex[:12]}",
        type=rule_type,
        value=value,
        created_at=_now_iso(),
        note=note,
        active=True,
    )
    payload["rules"] = [*payload.get("rules", []), rule.model_dump()]
    _save_payload(kind, payload)
    return rule


def delete_rule(kind: RuleKind, rule_id: str) -> bool:
    payload = _load_payload(kind)
    original = payload.get("rules", [])
    rules = [item for item in original if item.get("id") != rule_id]
    if len(rules) == len(original):
        return False
    payload["rules"] = rules
    _save_payload(kind, payload)
    return True


def restore_ignored_rule(rule_id: str) -> bool:
    payload = _load_payload("ignored")
    changed = False
    rules = []
    for item in payload.get("rules", []):
        if item.get("id") == rule_id:
            item = {**item, "active": False}
            changed = True
        rules.append(item)
    if changed:
        payload["rules"] = rules
        _save_payload("ignored", payload)
    return changed


def rule_matches(rule: Rule, session) -> bool:
    value = rule.value
    if rule.type == "session_id":
        return session.session_id == value
    if rule.type == "project_key":
        return session.project_key == value
    if rule.type == "cwd":
        return session.cwd == value or session.project_root == value
    if rule.type == "agent_type":
        return session.agent_type == value
    if rule.type == "command_pattern":
        cmd = " ".join(session.root_process.cmdline) if session.root_process else ""
        return value.lower() in cmd.lower()
    return False


def matching_rules(kind: RuleKind, session) -> list[Rule]:
    return [rule for rule in list_rules(kind) if rule_matches(rule, session)]
