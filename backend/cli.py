from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click

from backend.config import (
    get_log_dir,
    get_host,
    get_port,
    load_config,
    get_or_create_token,
)
from backend.models import (
    Task,
    TaskStatus,
    TaskCreate,
    PlanStep,
    StepStatus,
    PlanImport,
    StepUpdate,
    TaskComplete,
    TaskFail,
)
from backend.task_manager import (
    complete_task,
    create_task,
    delete_task,
    fail_task,
    generate_handoff_text,
    get_enriched_task,
    import_plan,
    list_tasks,
    load_task,
    save_task,
    add_progress_note,
    update_step,
    update_handoff_notes,
)
from backend.process_scanner import discover_sessions
from backend.security import is_safe_project_dir


@click.group()
def cli():
    """agent-foreman-local — Manage and monitor coding agent tasks."""
    pass


@cli.command()
@click.argument("name")
@click.option("--dir", "project_dir", default=".", help="Working directory for the agent")
@click.option("--goal", default="", help="Task goal description")
@click.option("--feature", default="", help="Current feature being worked on")
@click.option("--criteria", default="", help="Acceptance criteria (comma-separated)")
@click.option("--tag", multiple=True, help="Tags for the task (repeatable)")
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
def start(name: str, project_dir: str, goal: str, feature: str, criteria: str, tag: tuple[str], command: tuple[str]):
    """Start a new agent task.

    Example:
      agent-foreman-local start my-training --dir /data/proj --goal "Train model" -- python train.py --epochs 10
    """
    task_id = name
    project_dir = os.path.abspath(project_dir)

    # Validate project_dir
    safe, reason = is_safe_project_dir(project_dir)
    if not safe:
        click.echo(f"Error: {reason}", err=True)
        sys.exit(1)
    cmd_str = " ".join(command)

    # Ensure log dir exists
    log_dir = get_log_dir()
    log_path = log_dir / f"{task_id}.log"

    # Create task record
    criteria_list = [c.strip() for c in criteria.split(",") if c.strip()] if criteria else []
    req = TaskCreate(
        task_id=task_id,
        name=name,
        project_dir=project_dir,
        command=cmd_str,
        goal=goal,
        feature=feature,
        acceptance_criteria=criteria_list,
        tags=list(tag),
    )
    task = create_task(req)

    # Launch subprocess
    log_file = open(log_path, "w")
    try:
        proc = subprocess.Popen(
            list(command),
            cwd=project_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
        )
    except FileNotFoundError:
        click.echo(f"Error: command not found: {command[0]}", err=True)
        log_file.close()
        delete_task(task_id)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: failed to start process: {e}", err=True)
        log_file.close()
        delete_task(task_id)
        sys.exit(1)

    task.pid = proc.pid
    task.status = TaskStatus.running
    task.started_at = datetime.now()
    save_task(task)

    click.echo(f"Started task '{task_id}' (PID {proc.pid})")
    click.echo(f"  Command: {cmd_str}")
    click.echo(f"  Dir:     {project_dir}")
    click.echo(f"  Goal:    {goal or '(not specified)'}")
    click.echo(f"  Log:     {log_path}")
    click.echo(f"\nUse 'agent-foreman-local tail {task_id}' to watch output")


@cli.command()
@click.argument("name")
@click.option("--dir", "project_dir", required=True, help="Working directory for the agent")
@click.option("--goal", required=True, help="Task goal description")
@click.option("--feature", default="", help="Current feature being worked on")
@click.option("--criteria", multiple=True, help="Acceptance criteria (repeatable)")
@click.option("--tag", multiple=True, help="Tags for the task (repeatable)")
def init(name: str, project_dir: str, goal: str, feature: str, criteria: tuple[str], tag: tuple[str]):
    """Initialize a new task with goal and acceptance criteria (no command yet).

    Example:
      agent-foreman-local init my-task --dir /data/proj --goal "Implement auth" --criteria "Tests pass" --criteria "No lint errors"
    """
    task_id = name
    project_dir = os.path.abspath(project_dir)

    # Validate project_dir
    safe, reason = is_safe_project_dir(project_dir)
    if not safe:
        click.echo(f"Error: {reason}", err=True)
        sys.exit(1)

    req = TaskCreate(
        task_id=task_id,
        name=name,
        project_dir=project_dir,
        command="(not started)",
        goal=goal,
        feature=feature,
        acceptance_criteria=list(criteria),
        tags=list(tag),
    )
    task = create_task(req)

    click.echo(f"Initialized task '{task_id}'")
    click.echo(f"  Dir:     {project_dir}")
    click.echo(f"  Goal:    {goal}")
    if feature:
        click.echo(f"  Feature: {feature}")
    if criteria:
        click.echo(f"  Criteria:")
        for c in criteria:
            click.echo(f"    - {c}")
    click.echo(f"\nUse 'agent-foreman-local set-plan {task_id} plan.md' to import a plan")


@cli.command(name="set-plan")
@click.argument("task_id")
@click.argument("plan_file", type=click.Path(exists=True))
def set_plan(task_id: str, plan_file: str):
    """Import a plan from a markdown or JSON file.

    Plan file format (JSON):
    {
      "steps": [
        {"id": "1", "title": "Step 1"},
        {"id": "2", "title": "Step 2"}
      ]
    }

    Or simple text (one step per line):
    1. First step
    2. Second step
    """
    content = Path(plan_file).read_text()

    steps = []
    try:
        # Try JSON first
        data = json.loads(content)
        if "steps" in data:
            for s in data["steps"]:
                steps.append(PlanStep(
                    id=str(s.get("id", len(steps) + 1)),
                    title=s.get("title", s.get("name", "")),
                ))
    except json.JSONDecodeError:
        # Parse as simple text - each line is a step
        for i, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip markdown list markers
            for prefix in ("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ",
                           "6. ", "7. ", "8. ", "9. ", "10. "):
                if line.startswith(prefix):
                    line = line[len(prefix):]
                    break
            if line:
                steps.append(PlanStep(id=str(i), title=line))

    if not steps:
        click.echo("No steps found in plan file.", err=True)
        sys.exit(1)

    task = import_plan(task_id, steps)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Imported {len(steps)} steps for task '{task_id}':")
    for step in steps:
        click.echo(f"  [{step.id}] {step.title}")


@cli.command(name="note")
@click.argument("task_id")
@click.argument("note_text")
@click.option("--step", "step_id", default=None, help="Associate with specific step ID")
def add_note(task_id: str, note_text: str, step_id: str | None):
    """Add a progress note to a task.

    Example:
      agent-foreman-local note my-task "Completed API endpoint implementation"
    """
    task = add_progress_note(task_id, note_text, step_id)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Note added to '{task_id}'")


@cli.command(name="step")
@click.argument("task_id")
@click.argument("step_id")
@click.option("--status", "step_status", type=click.Choice(["running", "done", "blocked", "pending"]),
              required=True, help="New status for the step")
@click.option("--notes", default="", help="Notes for the step")
def update_step_cmd(task_id: str, step_id: str, step_status: str, notes: str):
    """Update the status of a plan step.

    Example:
      agent-foreman-local step my-task 1 --status done --notes "Implemented and tested"
    """
    status_enum = StepStatus(step_status)
    task = update_step(task_id, step_id, status_enum, notes)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Step '{step_id}' updated to '{step_status}'")


@cli.command(name="complete")
@click.argument("task_id")
@click.option("--summary", required=True, help="Final summary of completed work")
def complete_cmd(task_id: str, summary: str):
    """Mark a task as completed with a summary.

    Example:
      agent-foreman-local complete my-task --summary "All tests passing, API implemented"
    """
    task = complete_task(task_id, summary)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Task '{task_id}' marked as completed")
    click.echo(f"  Summary: {summary}")


@cli.command(name="fail")
@click.argument("task_id")
@click.option("--reason", required=True, help="Reason for failure")
def fail_cmd(task_id: str, reason: str):
    """Mark a task as failed with a reason.

    Example:
      agent-foreman-local fail my-task --reason "Database connection timeout"
    """
    task = fail_task(task_id, reason)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Task '{task_id}' marked as failed")
    click.echo(f"  Reason: {reason}")


@cli.command()
@click.argument("task_id")
@click.option("--notes", default="", help="Additional handoff notes")
def handoff(task_id: str, notes: str):
    """Generate handoff text for next agent session.

    Example:
      agent-foreman-local handoff my-task --notes "Need to review auth middleware"
    """
    if notes:
        task = update_handoff_notes(task_id, notes)
        if not task:
            click.echo(f"Task '{task_id}' not found.", err=True)
            sys.exit(1)

    text = generate_handoff_text(task_id)
    if not text:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(text)


@cli.command()
def discover():
    """Auto-discover running agent processes."""
    sessions = discover_sessions()
    if not sessions:
        click.echo("No agent processes discovered.")
        return

    click.echo(f"{'SESSION':<24} {'TYPE':<10} {'PIDS':<8} {'CWD':<40}")
    click.echo("-" * 82)
    for s in sessions:
        pid_str = str(len(s.all_pids))
        cwd_display = s.cwd[:38] + ".." if len(s.cwd) > 40 else s.cwd
        click.echo(f"{s.session_id:<24} {s.agent_type:<10} {pid_str:<8} {cwd_display:<40}")


@cli.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include completed/failed tasks")
def list_cmd(show_all: bool):
    """List all agent tasks."""
    tasks = list_tasks()
    if not tasks:
        click.echo("No tasks found.")
        return

    if not show_all:
        tasks = [t for t in tasks if t.status in (TaskStatus.running, TaskStatus.idle, TaskStatus.waiting_input)]

    if not tasks:
        click.echo("No active tasks. Use --all to see completed tasks.")
        return

    # Table header
    click.echo(f"{'TASK ID':<20} {'STATUS':<14} {'PID':<8} {'COMMAND':<40} {'ELAPSED':<10}")
    click.echo("-" * 92)

    for t in tasks:
        pid_str = str(t.pid) if t.pid else "-"
        elapsed = ""
        if t.ended_at and t.started_at:
            delta = t.ended_at - t.started_at
        elif t.started_at:
            delta = datetime.now() - t.started_at
        else:
            delta = None
        if delta:
            secs = int(delta.total_seconds())
            if secs < 60:
                elapsed = f"{secs}s"
            elif secs < 3600:
                elapsed = f"{secs // 60}m{secs % 60}s"
            else:
                elapsed = f"{secs // 3600}h{(secs % 3600) // 60}m"

        cmd_display = t.command[:38] + ".." if len(t.command) > 40 else t.command
        status_icon = {
            "running": "●",
            "idle": "◐",
            "waiting_input": "◑",
            "completed": "✓",
            "failed": "✗",
            "unknown": "?",
        }.get(t.status.value, "?")

        click.echo(f"{t.task_id:<20} {status_icon} {t.status.value:<12} {pid_str:<8} {cmd_display:<40} {elapsed:<10}")


@cli.command()
@click.argument("task_id")
def status(task_id: str):
    """Show detailed status of a task."""
    task = get_enriched_task(task_id)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    click.echo(f"Task:       {task.name}")
    click.echo(f"ID:         {task.task_id}")
    click.echo(f"Status:     {task.status.value}")
    click.echo(f"PID:        {task.pid or '-'}")
    click.echo(f"Command:    {task.command}")
    click.echo(f"Dir:        {task.project_dir}")
    click.echo(f"Started:    {task.started_at}")
    if task.ended_at:
        click.echo(f"Ended:      {task.ended_at}")
    if task.exit_code is not None:
        click.echo(f"Exit code:  {task.exit_code}")
    if task.has_error_hint:
        click.echo(f"Error hint: YES")
    if task.goal:
        click.echo(f"Goal:       {task.goal}")
    if task.feature:
        click.echo(f"Feature:    {task.feature}")
    if task.acceptance_criteria:
        click.echo(f"Criteria:")
        for c in task.acceptance_criteria:
            click.echo(f"  - {c}")
    if task.plan:
        click.echo(f"Plan:")
        for step in task.plan:
            icon = {"pending": "[ ]", "running": "[>]", "done": "[x]", "blocked": "[!]"}.get(step.status.value, "[ ]")
            click.echo(f"  {icon} {step.id}: {step.title}")
            if step.notes:
                click.echo(f"      Note: {step.notes}")
    if task.current_step_id:
        click.echo(f"Current:    {task.current_step_id}")
    if task.changed_files:
        click.echo(f"Changed:    {len(task.changed_files)} files")
    if task.tags:
        click.echo(f"Tags:       {', '.join(task.tags)}")
    if task.progress_log:
        click.echo(f"\nProgress log:")
        for entry in task.progress_log[-10:]:
            ts = entry.timestamp.isoformat(timespec="seconds")
            step_ref = f" [{entry.step_id}]" if entry.step_id else ""
            click.echo(f"  [{ts}]{step_ref} {entry.message}")


@cli.command()
@click.argument("task_id")
@click.option("-n", "--lines", default=50, help="Number of lines to show")
@click.option("-f", "--follow", is_flag=True, help="Follow log output (like tail -f)")
def tail(task_id: str, lines: int, follow: bool):
    """Show log output for a task."""
    log_path = get_log_dir() / f"{task_id}.log"
    if not log_path.exists():
        click.echo(f"No log file found for task '{task_id}'.", err=True)
        sys.exit(1)

    if follow:
        # Simple follow implementation
        with open(log_path) as f:
            # Seek to near end
            f.seek(0, os.SEEK_END)
            size = f.tell()
            # Go back enough for N lines
            read_size = min(size, lines * 200)
            f.seek(max(0, size - read_size))
            content = f.read()
            for line in content.splitlines()[-lines:]:
                click.echo(line)

            # Follow
            try:
                while True:
                    line = f.readline()
                    if line:
                        click.echo(line, nl=False)
                    else:
                        time.sleep(0.3)
            except KeyboardInterrupt:
                pass
    else:
        from backend.log_manager import get_log_tail
        for line in get_log_tail(log_path, lines):
            click.echo(line)


@cli.command()
@click.option("--host", default=None, help="Bind host (default: 127.0.0.1)")
@click.option("--port", default=None, type=int, help="Bind port (default: 8790)")
def serve(host: str | None, port: int | None):
    """Start the web dashboard server."""
    from backend.main import run_server

    token = get_or_create_token()
    h = host or get_host()
    p = port or get_port()

    click.echo(f"AgentStatus dashboard starting on http://{h}:{p}")
    if h not in ("127.0.0.1", "localhost"):
        click.echo(f"Token: {token}")
    run_server(host=h, port=p)


@cli.command(name="config")
def show_config():
    """Show current configuration."""
    cfg = load_config()
    token = get_or_create_token()
    click.echo(f"Config file: {Path.home() / '.agent_foreman_local' / 'config.yaml'}")
    click.echo(f"Token:       {token}")
    click.echo(f"Host:        {get_host()}")
    click.echo(f"Port:        {get_port()}")
    click.echo(f"Log dir:     {get_log_dir()}")
    click.echo(f"Tasks dir:   {Path.home() / '.agent_foreman_local' / 'tasks'}")


@cli.command(name="install-service")
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", default=8787, type=int, help="Bind port")
@click.option("--enable", is_flag=True, help="Enable service to start on login")
def install_service_cmd(host: str, port: int, enable: bool):
    """Install systemd user service for auto-start.

    Generates ~/.config/systemd/user/agent-foreman-local.service

    After install:
      systemctl --user start agent-foreman-local
      systemctl --user status agent-foreman-local
      journalctl --user -u agent-foreman-local -f
    """
    from backend.systemd import install_service

    ok, msg = install_service(host=host, port=port, enable=enable)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        sys.exit(1)

    click.echo(f"Service installed: {msg}")
    click.echo(f"  Host: {host}")
    click.echo(f"  Port: {port}")
    click.echo(f"\nStart the service:")
    click.echo(f"  systemctl --user start agent-foreman-local")
    click.echo(f"\nView logs:")
    click.echo(f"  journalctl --user -u agent-foreman-local -f")
    if enable:
        click.echo(f"\nAuto-start on login: ENABLED")
    else:
        click.echo(f"\nTo enable auto-start on login:")
        click.echo(f"  systemctl --user enable agent-foreman-local")


@cli.command(name="uninstall-service")
def uninstall_service_cmd():
    """Remove systemd user service."""
    from backend.systemd import uninstall_service

    ok, msg = uninstall_service()
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        sys.exit(1)
    click.echo(msg)


if __name__ == "__main__":
    cli()
