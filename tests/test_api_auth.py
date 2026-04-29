"""Tests for API authentication behavior."""

from __future__ import annotations

import anyio
import httpx
from fastapi import FastAPI

from backend.api.auth import require_token


def _auth_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[require_token()])
    async def protected():
        return {"ok": True}

    return app


def _get(path: str, *, headers: dict[str, str] | None = None, client_addr: str = "127.0.0.1"):
    async def run():
        transport = httpx.ASGITransport(app=_auth_app(), client=(client_addr, 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path, headers=headers)

    return anyio.run(run)


class TestAuth:
    def test_localhost_skips_token(self):
        res = _get("/protected")

        assert res.status_code == 200
        assert res.json() == {"ok": True}

    def test_remote_rejects_missing_token(self, monkeypatch):
        monkeypatch.setenv("AGENT_FOREMAN_TOKEN", "secret-token")

        res = _get("/protected", client_addr="10.0.0.12")

        assert res.status_code == 401

    def test_remote_accepts_bearer_token(self, monkeypatch):
        monkeypatch.setenv("AGENT_FOREMAN_TOKEN", "secret-token")

        res = _get(
            "/protected",
            headers={"Authorization": "Bearer secret-token"},
            client_addr="10.0.0.12",
        )

        assert res.status_code == 200

    def test_remote_accepts_query_token_for_sse(self, monkeypatch):
        monkeypatch.setenv("AGENT_FOREMAN_TOKEN", "secret-token")

        res = _get("/protected?token=secret-token", client_addr="10.0.0.12")

        assert res.status_code == 200
