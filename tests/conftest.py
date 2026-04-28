"""Shared fixtures for AgentStatus tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from backend.models import Task, TaskStatus


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect all config dirs to tmp_path for test isolation."""
    config_dir = tmp_path / "config"
    tasks_dir = config_dir / "tasks"
    logs_dir = tmp_path / "logs"
    config_dir.mkdir()
    tasks_dir.mkdir()
    logs_dir.mkdir()

    monkeypatch.setattr("backend.config.DEFAULT_CONFIG_DIR", config_dir)
    monkeypatch.setattr("backend.config.DEFAULT_TASKS_DIR", tasks_dir)
    monkeypatch.setattr("backend.config.DEFAULT_LOGS_DIR", logs_dir)
    monkeypatch.setattr("backend.config.DEFAULT_CONFIG_FILE", config_dir / "config.yaml")

    from backend.security import ALLOWED_LOG_DIRS
    ALLOWED_LOG_DIRS.clear()
    ALLOWED_LOG_DIRS.append(logs_dir.resolve())
    ALLOWED_LOG_DIRS.append(tasks_dir.resolve())

    return tmp_path


@pytest.fixture
def tasks_dir(isolated_config: Path) -> Path:
    return isolated_config / "config" / "tasks"


@pytest.fixture
def logs_dir(isolated_config: Path) -> Path:
    return isolated_config / "logs"


@pytest.fixture
def project_dir(isolated_config: Path) -> Path:
    d = isolated_config / "project"
    d.mkdir()
    return d


@pytest.fixture
def sample_task_data(project_dir: Path) -> dict:
    return {
        "task_id": "test-task-1",
        "name": "test-task-1",
        "project_dir": str(project_dir),
        "command": "python train.py",
        "goal": "Train the model",
        "feature": "auth",
        "acceptance_criteria": ["Tests pass", "No lint errors"],
        "tags": ["ml", "training"],
    }


@pytest.fixture
def sample_task(sample_task_data: dict) -> Task:
    return Task(
        **sample_task_data,
        pid=12345,
        status=TaskStatus.running,
        started_at=datetime(2025, 1, 15, 10, 0, 0),
    )


@pytest.fixture
def sample_task_json(tasks_dir: Path, sample_task: Task) -> Path:
    p = tasks_dir / f"{sample_task.task_id}.json"
    p.write_text(sample_task.model_dump_json(indent=2))
    return p


@pytest.fixture
def sample_log(logs_dir: Path) -> Path:
    p = logs_dir / "test-task-1.log"
    lines = [
        "2025-01-15 10:00:00 Starting training...",
        "2025-01-15 10:00:01 Loading data...",
        "2025-01-15 10:00:02 Epoch 1/10 loss=0.5",
        "2025-01-15 10:00:03 Epoch 2/10 loss=0.3",
        "2025-01-15 10:00:04 Training complete.",
    ]
    p.write_text("\n".join(lines) + "\n")
    return p
