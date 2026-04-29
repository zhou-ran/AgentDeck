"""Tests for process/discovery API defaults."""

from __future__ import annotations

import anyio
import httpx

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
