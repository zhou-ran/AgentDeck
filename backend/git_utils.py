"""Safe git operations for AgentStatus.

Only allows the read-only git commands needed by the local monitor.
No dangerous commands (push, pull, commit, checkout, reset, etc.)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

# Exact whitelist from docs/prompts.v3.md.
ALLOWED_GIT_COMMANDS = {
    ("rev-parse", "--show-toplevel"),
    ("branch", "--show-current"),
    ("status", "--short"),
    ("diff", "--name-only"),
}


def is_git_repo(project_dir: str) -> bool:
    """Check if directory is a git repository."""
    return run_git_command(project_dir, ["rev-parse", "--show-toplevel"]) is not None


def _is_within(path: Path, parent: Path) -> bool:
    try:
        resolved = path.resolve()
        parent_resolved = parent.resolve()
        return resolved == parent_resolved or parent_resolved in resolved.parents
    except OSError:
        return False


def run_git_command(
    project_dir: str,
    args: list[str],
    timeout: int = 10,
    cwd: str | None = None,
) -> Optional[str]:
    """Run a safe git command in the project directory.

    Only allows exact read-only commands from the whitelist. The working
    directory must stay inside project_dir.
    Returns stdout on success, None on failure.
    """
    if not args:
        return None

    if tuple(args) not in ALLOWED_GIT_COMMANDS:
        return None

    dir_path = Path(project_dir)
    if not dir_path.is_dir():
        return None
    work_dir = Path(cwd or project_dir)
    if not work_dir.is_dir() or not _is_within(work_dir, dir_path):
        return None

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_changed_files(project_dir: str) -> list[str]:
    """Get list of changed files in git repository.

    Uses git status --short and git diff --name-only.
    Returns list of changed file paths.
    """
    changed = set()

    # Get untracked and staged files from git status
    status_output = run_git_command(project_dir, ["status", "--short"])
    if status_output:
        for line in status_output.split("\n"):
            line = line.strip()
            if line:
                # Format: XY filename (X=index, Y=worktree)
                # Extract filename (everything after the 2-char status)
                if len(line) > 3:
                    filename = line[3:].strip()
                    # Handle renamed files (old -> new)
                    if " -> " in filename:
                        filename = filename.split(" -> ")[1]
                    changed.add(filename)

    diff_output = run_git_command(project_dir, ["diff", "--name-only"])
    if diff_output:
        for line in diff_output.split("\n"):
            line = line.strip()
            if line:
                changed.add(line)

    return sorted(changed)


def get_git_summary(project_dir: str) -> dict[str, str]:
    """Get a summary of git status for display."""
    if not is_git_repo(project_dir):
        return {"is_repo": "false", "changed_files": ""}

    changed = get_changed_files(project_dir)
    return {
        "is_repo": "true",
        "changed_count": str(len(changed)),
        "changed_files": "\n".join(changed) if changed else "(no changes)",
    }


def get_git_root(cwd: str) -> Optional[str]:
    return run_git_command(cwd, ["rev-parse", "--show-toplevel"], timeout=2)


def get_git_branch(project_dir: str) -> str:
    return run_git_command(project_dir, ["branch", "--show-current"], timeout=2) or ""


def get_git_status_short(project_dir: str) -> str:
    return run_git_command(project_dir, ["status", "--short"], timeout=5) or ""
