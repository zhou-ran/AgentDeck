from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click

from backend.config import get_log_dir, get_host, get_port, load_config, get_or_create_token
from backend.models import Task, TaskStatus, TaskCreate
from backend.task_manager import (
    create_task,
    delete_task,
    get_enriched_task,
    list_tasks,
    load_task,
    save_task,
)
from backend.process_scanner import is_process_alive


@click.group()
def cli():
    """agentctl — Manage and monitor coding agent tasks."""
    pass


@cli.command()
@click.argument("name")
@click.option("--dir", "project_dir", default=".", help="Working directory for the agent")
@click.option("--criteria", default="", help="Acceptance criteria for the task")
@click.option("--tag", multiple=True, help="Tags for the task (repeatable)")
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
def start(name: str, project_dir: str, criteria: str, tag: tuple[str], command: tuple[str]):
    """Start a new agent task.

    Example:
      agentctl start my-training --dir /data/proj -- python train.py --epochs 10
    """
    task_id = name
    project_dir = os.path.abspath(project_dir)
    cmd_str = " ".join(command)

    # Ensure log dir exists
    log_dir = get_log_dir()
    log_path = log_dir / f"{task_id}.log"

    # Create task record
    req = TaskCreate(
        task_id=task_id,
        name=name,
        project_dir=project_dir,
        command=cmd_str,
        acceptance_criteria=criteria,
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
            preexec_fn=os.setsid,  # new process group for clean stop
        )
    except FileNotFoundError:
        click.echo(f"Error: command not found: {command[0]}", err=True)
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
    click.echo(f"  Log:     {log_path}")
    click.echo(f"\nUse 'agentctl tail {task_id}' to watch output")


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
    if task.acceptance_criteria:
        click.echo(f"Criteria:   {task.acceptance_criteria}")
    if task.tags:
        click.echo(f"Tags:       {', '.join(task.tags)}")
    if task.progress_notes:
        click.echo(f"\nProgress notes:")
        for note in task.progress_notes:
            click.echo(f"  {note}")


@cli.command()
@click.argument("task_id")
@click.option("--signal", "sig", default="TERM", help="Signal to send (TERM, KILL, INT)")
def stop(task_id: str, sig: str):
    """Stop a running agent task."""
    task = load_task(task_id)
    if not task:
        click.echo(f"Task '{task_id}' not found.", err=True)
        sys.exit(1)

    if not task.pid:
        click.echo("Task has no PID.", err=True)
        sys.exit(1)

    if not is_process_alive(task.pid):
        click.echo(f"Process {task.pid} is not running.")
        task.status = TaskStatus.completed
        task.ended_at = datetime.now()
        save_task(task)
        return

    sig_map = {"TERM": signal.SIGTERM, "KILL": signal.SIGKILL, "INT": signal.SIGINT}
    send_signal = sig_map.get(sig.upper(), signal.SIGTERM)

    try:
        os.kill(task.pid, send_signal)
        click.echo(f"Sent SIG{sig.upper()} to PID {task.pid}")
    except ProcessLookupError:
        click.echo(f"Process {task.pid} already gone.")
    except PermissionError:
        click.echo(f"Permission denied to signal PID {task.pid}.", err=True)
        sys.exit(1)

    # Wait briefly for process to die
    for _ in range(10):
        if not is_process_alive(task.pid):
            break
        time.sleep(0.5)

    if not is_process_alive(task.pid):
        task.status = TaskStatus.completed
        task.ended_at = datetime.now()
        save_task(task)
        click.echo("Task stopped.")
    else:
        click.echo(f"Process {task.pid} still alive. Use --signal KILL to force.")


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


if __name__ == "__main__":
    cli()
