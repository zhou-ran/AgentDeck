"""Tests for process/discovery API defaults."""

from __future__ import annotations

import anyio
import httpx

from backend.models import DiscoveredSession, ProcessInfo
from backend import rules
from backend.main import app
from backend.security import api_rate_limiter


def _request(method: str, path: str, **kwargs):
    async def run():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(run)


def test_import_pid_route_is_not_available():
    api_rate_limiter._requests.clear()

    res = _request("POST", "/api/import-pid", json={"pid": 1, "name": "x"})

    assert res.status_code == 404


def test_ignore_session_creates_session_scoped_rule(tmp_path, monkeypatch):
    api_rate_limiter._requests.clear()
    monkeypatch.setattr(rules, "CONFIG_DIR", tmp_path)

    session = DiscoveredSession(
        session_id="session-a",
        project_key="project-a",
        cwd="/tmp/project",
        root_process=ProcessInfo(
            pid=10,
            ppid=1,
            name="codex",
            cmdline=["codex"],
            cwd="/tmp/project",
        ),
        display_name="Current session",
    )
    monkeypatch.setattr("backend.api.processes._find_session", lambda session_id: session)

    res = _request("POST", "/api/sessions/session-a/ignore")

    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "session_id"
    assert data["value"] == "session-a"
