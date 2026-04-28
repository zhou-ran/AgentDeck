from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import get_log_dir, get_tasks_dir
from backend.log_manager import get_log_tail
from backend.models import ProcessInfo, Task, TaskStatus, TaskCreate
from backend.process_scanner import get_process_cpu_mem, get_process_tree, is_process_alive
from backend.state_machine import infer_status, check_error_hint


def _task_path(task_id: str) -> Path:
    return get_tasks_dir() / f"{task_id}.json"


def _log_path(task_id: str) -> Path:
    return get_log_dir() / f"{task_id}.log"


def save_task(task: Task) -> None:
    p = _task_path(task.task_id)
    p.write_text(task.model_dump_json(indent=2))


def load_task(task_id: str) -> Optional[Task]:
    p = _task_path(task_id)
    if not p.exists():
        return None
    try:
        return Task.model_validate_json(p.read_text())
    except Exception:
        return None


def delete_task(task_id: str) -> bool:
    p = _task_path(task_id)
    if p.exists():
        p.unlink()
        return True
    return False


def create_task(req: TaskCreate) -> Task:
    task = Task(
        task_id=req.task_id,
        name=req.name,
        project_dir=req.project_dir,
        command=req.command,
        acceptance_criteria=req.acceptance_criteria,
        tags=req.tags,
        started_at=datetime.now(),
        status=TaskStatus.running,
    )
    save_task(task)
    return task


def enrich_task(task: Task) -> Task:
    """Update task status from live process and log state."""
    if task.pid is None:
        return task

    alive = is_process_alive(task.pid)
    cpu, mem = get_process_cpu_mem(task.pid)
    log_p = _log_path(task.task_id)

    # Update status via state machine
    task.status = infer_status(task, alive, cpu, log_p)
    task.has_error_hint = check_error_hint(log_p)

    # Record ended_at if process died
    if not alive and task.ended_at is None:
        task.ended_at = datetime.now()

    return task


def get_enriched_task(task_id: str) -> Optional[Task]:
    task = load_task(task_id)
    if not task:
        return None
    return enrich_task(task)


def list_tasks() -> list[Task]:
    tasks_dir = get_tasks_dir()
    tasks = []
    for p in sorted(tasks_dir.glob("*.json")):
        try:
            task = Task.model_validate_json(p.read_text())
            task = enrich_task(task)
            tasks.append(task)
        except Exception:
            continue
    return tasks


def get_task_process_tree(task_id: str) -> Optional[ProcessInfo]:
    task = load_task(task_id)
    if not task or not task.pid:
        return None
    return get_process_tree(task.pid)


def get_task_log(task_id: str, lines: int = 50) -> list[str]:
    log_p = _log_path(task_id)
    return get_log_tail(log_p, lines)


def add_progress_note(task_id: str, note: str) -> Optional[Task]:
    task = load_task(task_id)
    if not task:
        return None
    ts = datetime.now().isoformat(timespec="seconds")
    task.progress_notes.append(f"[{ts}] {note}")
    save_task(task)
    return task
