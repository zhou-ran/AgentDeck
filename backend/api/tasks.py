from __future__ import annotations

import os
import signal
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from backend.log_manager import get_log_tail, get_log_size, get_log_mtime
from backend.models import (
    NoteAdd,
    Task,
    TaskCreate,
    TaskStatus,
    PlanImport,
    StepUpdate,
    TaskComplete,
    TaskFail,
)
from backend.security import (
    is_valid_task_id,
    is_safe_log_path,
    is_safe_project_dir,
    sanitize_note,
    verify_pid_for_task,
)
from backend.task_manager import (
    add_progress_note,
    complete_task,
    create_task,
    delete_task,
    fail_task,
    generate_handoff_text,
    get_enriched_task,
    get_task_log,
    get_task_process_tree,
    import_plan,
    list_tasks,
    load_task,
    save_task,
    update_step,
    update_handoff_notes,
)

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[Task])
async def api_list_tasks():
    return list_tasks()


@router.get("/tasks/{task_id}", response_model=Task)
async def api_get_task(task_id: str):
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = get_enriched_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.post("/tasks", response_model=Task, status_code=201)
async def api_create_task(req: TaskCreate):
    if not is_valid_task_id(req.task_id):
        raise HTTPException(400, "Invalid task_id: use alphanumeric, dash, underscore, dot only")
    safe, reason = is_safe_project_dir(req.project_dir)
    if not safe:
        raise HTTPException(400, f"Unsafe project_dir: {reason}")
    existing = load_task(req.task_id)
    if existing:
        raise HTTPException(409, f"Task {req.task_id!r} already exists")
    try:
        task = create_task(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return task


@router.delete("/tasks/{task_id}", status_code=204)
async def api_delete_task(task_id: str):
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    if not delete_task(task_id):
        raise HTTPException(404, f"Task {task_id!r} not found")


@router.post("/tasks/{task_id}/stop", response_model=Task)
async def api_stop_task(task_id: str):
    """Stop a running task. Verifies PID identity before sending signal."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")

    task = load_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    if not task.pid:
        raise HTTPException(400, "Task has no PID")

    # Verify PID is still the same process we started
    safe, reason = verify_pid_for_task(task.pid, task.command, task.project_dir)
    if not safe:
        raise HTTPException(
            409,
            f"PID verification failed: {reason}. "
            "The process may have been replaced. Refusing to kill."
        )

    try:
        os.kill(task.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        raise HTTPException(403, "Permission denied to stop process")

    task.status = TaskStatus.completed
    task.ended_at = datetime.now()
    save_task(task)
    return task


@router.post("/tasks/{task_id}/plan", response_model=Task)
async def api_import_plan(task_id: str, body: PlanImport):
    """Import a plan with steps."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = import_plan(task_id, body.steps)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.put("/tasks/{task_id}/steps/{step_id}", response_model=Task)
async def api_update_step(task_id: str, step_id: str, body: StepUpdate):
    """Update a specific step's status."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    from backend.models import StepStatus
    task = update_step(task_id, step_id, body.status, body.notes)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.post("/tasks/{task_id}/notes", response_model=Task)
async def api_add_note(task_id: str, body: NoteAdd):
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = add_progress_note(task_id, body.note)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.post("/tasks/{task_id}/complete", response_model=Task)
async def api_complete_task(task_id: str, body: TaskComplete):
    """Mark task as completed."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = complete_task(task_id, body.summary)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.post("/tasks/{task_id}/fail", response_model=Task)
async def api_fail_task(task_id: str, body: TaskFail):
    """Mark task as failed."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = fail_task(task_id, body.reason)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return task


@router.put("/tasks/{task_id}/handoff")
async def api_update_handoff(task_id: str, body: NoteAdd):
    """Update handoff notes."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    task = update_handoff_notes(task_id, body.note)
    if not task:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return {"status": "updated"}


@router.get("/tasks/{task_id}/handoff")
async def api_get_handoff(task_id: str):
    """Get handoff text for next agent session."""
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    text = generate_handoff_text(task_id)
    if text is None:
        raise HTTPException(404, f"Task {task_id!r} not found")
    return {"task_id": task_id, "handoff_text": text}


@router.get("/tasks/{task_id}/logs")
async def api_get_log(task_id: str, lines: int = Query(50, ge=1, le=500)):
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")

    from backend.config import get_log_dir
    log_path = get_log_dir() / f"{task_id}.log"

    # Validate log path is safe
    if not is_safe_log_path(log_path):
        raise HTTPException(403, "Log path not allowed")

    return {
        "task_id": task_id,
        "lines": get_log_tail(log_path, lines),
        "size": get_log_size(log_path),
        "last_modified": get_log_mtime(log_path),
    }


@router.get("/tasks/{task_id}/process-tree")
async def api_get_process_tree(task_id: str):
    if not is_valid_task_id(task_id):
        raise HTTPException(400, "Invalid task_id")
    tree = get_task_process_tree(task_id)
    if not tree:
        raise HTTPException(404, "Process tree not found (task may have no PID or process is dead)")
    return tree
