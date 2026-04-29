from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import psutil

from backend.config import get_log_dir, get_tasks_dir
from backend.git_utils import get_changed_files
from backend.log_manager import get_log_mtime, get_log_size, get_log_tail
from backend.models import (
    ProcessInfo,
    ProgressLogEntry,
    Task,
    TaskStatus,
    TaskCreate,
    PlanStep,
    StepStatus,
)
from backend.process_scanner import derive_project_name, get_process_cpu_mem, get_process_tree, is_process_alive
from backend.security import (
    atomic_write,
    is_valid_task_id,
    is_safe_log_path,
    is_safe_project_dir,
    sanitize_note,
)
from backend.state_machine import infer_status, check_error_hint


def _task_path(task_id: str) -> Path:
    return get_tasks_dir() / f"{task_id}.json"


def _log_path(task_id: str) -> Path:
    return get_log_dir() / f"{task_id}.log"


def save_task(task: Task) -> None:
    """Save task atomically — temp file + rename prevents corruption."""
    p = _task_path(task.task_id)
    atomic_write(p, task.model_dump_json(indent=2))


def load_task(task_id: str) -> Optional[Task]:
    if not is_valid_task_id(task_id):
        return None
    p = _task_path(task_id)
    if not p.exists():
        return None
    try:
        return Task.model_validate_json(p.read_text())
    except Exception:
        return None


def delete_task(task_id: str) -> bool:
    if not is_valid_task_id(task_id):
        return False
    p = _task_path(task_id)
    if p.exists():
        p.unlink()
        return True
    return False


def create_task(req: TaskCreate) -> Task:
    # Validate task_id
    if not is_valid_task_id(req.task_id):
        raise ValueError(f"Invalid task_id: {req.task_id!r}")

    # Validate project_dir
    safe, reason = is_safe_project_dir(req.project_dir)
    if not safe:
        raise ValueError(f"Unsafe project_dir: {reason}")

    task = Task(
        task_id=req.task_id,
        name=req.name,
        project_dir=req.project_dir,
        command=req.command,
        goal=req.goal,
        feature=req.feature,
        acceptance_criteria=req.acceptance_criteria,
        tags=req.tags,
        started_at=datetime.now(),
        status=TaskStatus.running,
    )
    save_task(task)
    return task


def enrich_task(task: Task) -> Task:
    """Update task status from live process and log state."""
    project = derive_project_name(task.project_dir)
    task.project_name = project.display_name
    task.short_cwd = project.short_cwd
    if task.goal and not task.user_instruction:
        task.user_instruction = task.goal
        task.instruction_source = "managed task goal"

    if task.pid is None:
        return task

    alive = is_process_alive(task.pid)
    cpu, mem = get_process_cpu_mem(task.pid)
    log_p = _log_path(task.task_id)

    # Update status via state machine
    task.status = infer_status(task, alive, cpu, log_p)
    task.has_error_hint = check_error_hint(log_p)
    task.status_reason = (
        "process is not alive" if not alive else
        "error hint detected in log" if task.has_error_hint else
        "low CPU and stale log" if task.status == TaskStatus.idle else
        "managed task process is alive"
    )
    task.current_activity = (
        "Task failed; error hint detected" if task.status == TaskStatus.failed else
        "No recent activity; possibly waiting or idle" if task.status == TaskStatus.idle else
        "Managed task is running" if alive else
        "Managed task completed"
    )

    # Record ended_at and exit_code if process died
    if not alive and task.ended_at is None:
        task.ended_at = datetime.now()
        # Try to capture exit code (best-effort: only works for zombie processes)
        if task.exit_code is None:
            try:
                proc = psutil.Process(task.pid)
                if proc.status() == psutil.STATUS_ZOMBIE:
                    task.exit_code = proc.wait(timeout=0.1)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired,
                    psutil.AccessDenied, psutil.ZombieProcess, OSError):
                pass

    # Update changed files from git
    task.changed_files = get_changed_files(task.project_dir)

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
    if not is_valid_task_id(task_id):
        return []
    log_p = _log_path(task_id)
    if not is_safe_log_path(log_p):
        return []
    return get_log_tail(log_p, lines)


def get_task_log_metadata(task_id: str) -> dict[str, int | float]:
    """Return safe log metadata for API/SSE responses."""
    metadata: dict[str, int | float] = {"log_size": 0, "log_mtime": 0.0}
    if not is_valid_task_id(task_id):
        return metadata
    log_p = _log_path(task_id)
    if not log_p.exists() or not is_safe_log_path(log_p):
        return metadata
    metadata["log_size"] = get_log_size(log_p)
    metadata["log_mtime"] = get_log_mtime(log_p)
    return metadata


def add_progress_note(task_id: str, note: str, step_id: Optional[str] = None) -> Optional[Task]:
    """Add a structured progress log entry."""
    task = load_task(task_id)
    if not task:
        return None
    entry = ProgressLogEntry(
        message=sanitize_note(note),
        step_id=step_id or task.current_step_id,
    )
    task.progress_log.append(entry)
    save_task(task)
    return task


def import_plan(task_id: str, steps: list[PlanStep]) -> Optional[Task]:
    """Import a plan with steps."""
    task = load_task(task_id)
    if not task:
        return None
    task.plan = steps
    # Set first step as current if not set
    if steps and not task.current_step_id:
        task.current_step_id = steps[0].id
    save_task(task)
    return task


def update_step(task_id: str, step_id: str, status: StepStatus, notes: str = "") -> Optional[Task]:
    """Update a specific step's status and notes."""
    task = load_task(task_id)
    if not task:
        return None
    for step in task.plan:
        if step.id == step_id:
            step.status = status
            if notes:
                step.notes = notes
            # If marking as done, advance to next pending step
            if status == StepStatus.done and task.current_step_id == step_id:
                for next_step in task.plan:
                    if next_step.status == StepStatus.pending:
                        task.current_step_id = next_step.id
                        break
            break
    save_task(task)
    return task


def set_current_step(task_id: str, step_id: str) -> Optional[Task]:
    """Set the current active step."""
    task = load_task(task_id)
    if not task:
        return None
    # Validate step_id exists
    for step in task.plan:
        if step.id == step_id:
            task.current_step_id = step_id
            break
    save_task(task)
    return task


def complete_task(task_id: str, summary: str) -> Optional[Task]:
    """Mark task as completed with final summary."""
    task = load_task(task_id)
    if not task:
        return None
    task.status = TaskStatus.completed
    task.final_summary = summary
    task.ended_at = datetime.now()
    save_task(task)
    return task


def fail_task(task_id: str, reason: str) -> Optional[Task]:
    """Mark task as failed with reason."""
    task = load_task(task_id)
    if not task:
        return None
    task.status = TaskStatus.failed
    task.risk_notes = reason
    task.ended_at = datetime.now()
    save_task(task)
    return task


def update_handoff_notes(task_id: str, notes: str) -> Optional[Task]:
    """Update handoff notes for task."""
    task = load_task(task_id)
    if not task:
        return None
    task.handoff_notes = notes
    save_task(task)
    return task


def generate_handoff_text(task_id: str) -> Optional[str]:
    """Generate handoff text for next agent session."""
    task = load_task(task_id)
    if not task:
        return None

    lines = [
        f"# Task Handoff: {task.name}",
        f"",
        f"## Goal",
        task.goal or "(not specified)",
        f"",
        f"## Feature",
        task.feature or "(not specified)",
        f"",
        f"## Status: {task.status.value}",
        f"",
    ]

    # Acceptance criteria
    if task.acceptance_criteria:
        lines.append("## Acceptance Criteria")
        for i, ac in enumerate(task.acceptance_criteria, 1):
            lines.append(f"{i}. {ac}")
        lines.append("")

    # Current plan progress
    if task.plan:
        lines.append("## Plan Progress")
        for step in task.plan:
            status_icon = {
                StepStatus.pending: "[ ]",
                StepStatus.running: "[>]",
                StepStatus.done: "[x]",
                StepStatus.blocked: "[!]",
            }.get(step.status, "[ ]")
            lines.append(f"- {status_icon} {step.id}: {step.title}")
            if step.notes:
                lines.append(f"  Note: {step.notes}")
        lines.append("")

    # Current step
    if task.current_step_id:
        lines.append(f"## Current Step: {task.current_step_id}")
        lines.append("")

    # Recent progress log
    if task.progress_log:
        lines.append("## Recent Progress (last 5)")
        for entry in task.progress_log[-5:]:
            ts = entry.timestamp.strftime("%H:%M:%S")
            step_ref = f" [{entry.step_id}]" if entry.step_id else ""
            lines.append(f"- [{ts}]{step_ref} {entry.message}")
        lines.append("")

    # Changed files
    if task.changed_files:
        lines.append("## Changed Files")
        for f in task.changed_files:
            lines.append(f"- {f}")
        lines.append("")

    # Risk notes
    if task.risk_notes:
        lines.append("## Risks / Blockers")
        lines.append(task.risk_notes)
        lines.append("")

    # Handoff notes
    if task.handoff_notes:
        lines.append("## Handoff Notes")
        lines.append(task.handoff_notes)
        lines.append("")

    # Final summary
    if task.final_summary:
        lines.append("## Final Summary")
        lines.append(task.final_summary)
        lines.append("")

    return "\n".join(lines)


def import_pid(pid: int, name: str) -> Optional[Task]:
    """Import an existing PID as a managed task.

    Creates a Task record pointing at the existing process.
    Marked as imported=True so the UI can distinguish it.
    """
    from backend.process_scanner import get_process_info

    info = get_process_info(pid)
    if not info:
        return None

    task_id = name
    # Check if task_id already exists
    existing = load_task(task_id)
    if existing:
        return None

    cmd_str = " ".join(info.cmdline) if info.cmdline else f"(pid {pid})"
    cwd = info.cwd or "."

    task = Task(
        task_id=task_id,
        name=name,
        project_dir=cwd,
        command=cmd_str,
        pid=pid,
        status=TaskStatus.running,
        started_at=datetime.fromtimestamp(info.create_time) if info.create_time else datetime.now(),
        imported=True,
        imported_from_pid=pid,
    )
    save_task(task)
    return task
