"""Tests for task REST API endpoints."""

from __future__ import annotations

import anyio
import httpx
from pathlib import Path

from backend.main import app
from backend.security import api_rate_limiter


def _request(method: str, path: str, **kwargs):
    async def run():
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(run)


class TestTaskApi:
    def test_create_and_get_task(self, project_dir: Path):
        api_rate_limiter._requests.clear()
        payload = {
            "task_id": "api-task",
            "name": "api-task",
            "project_dir": str(project_dir),
            "command": "echo hello",
            "goal": "exercise API",
        }

        created = _request("POST", "/api/tasks", json=payload)
        fetched = _request("GET", "/api/tasks/api-task")

        assert created.status_code == 201
        assert created.json()["task_id"] == "api-task"
        assert fetched.status_code == 200
        assert fetched.json()["goal"] == "exercise API"

    def test_log_endpoint_returns_tail(self, sample_task_json: Path, sample_log: Path):
        api_rate_limiter._requests.clear()

        res = _request("GET", "/api/tasks/test-task-1/logs?lines=2")

        assert res.status_code == 200
        data = res.json()
        assert data["task_id"] == "test-task-1"
        assert len(data["lines"]) == 2
        assert data["size"] == sample_log.stat().st_size

    def test_invalid_task_id_rejected(self):
        api_rate_limiter._requests.clear()

        res = _request("GET", "/api/tasks/.hidden")

        assert res.status_code == 400

    def test_stop_route_is_not_available(self):
        api_rate_limiter._requests.clear()

        res = _request("POST", "/api/tasks/anything/stop")

        assert res.status_code == 404
