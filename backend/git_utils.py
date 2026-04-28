"""Safe git operations for AgentStatus.

Only allows read-only git commands (status, diff) within a project directory.
No dangerous commands (push, pull, commit, checkout, reset, etc.)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

# Whitelist of allowed git commands
ALLOWED_GIT_COMMANDS = {"status", "diff", "log", "show"}


def is_git_repo(project_dir: str) -> bool:
    """Check if directory is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def run_git_command(
    project_dir: str,
    args: list[str],
    timeout: int = 10,
) -> Optional[str]:
    """Run a safe git command in the project directory.

    Only allows read-only commands from the whitelist.
    Returns stdout on success, None on failure.
    """
    if not args:
        return None

    # Validate command is in whitelist
    cmd = args[0]
    if cmd not in ALLOWED_GIT_COMMANDS:
        return None

    # Validate project_dir exists and is a directory
    dir_path = Path(project_dir)
    if not dir_path.is_dir():
        return None

    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=project_dir,
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
    if not is_git_repo(project_dir):
        return []

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

    # Get modified files from git diff
    diff_output = run_git_command(project_dir, ["diff", "--name-only"])
    if diff_output:
        for line in diff_output.split("\n"):
            line = line.strip()
            if line:
                changed.add(line)

    # Get staged files from git diff --cached
    diff_cached_output = run_git_command(
        project_dir, ["diff", "--cached", "--name-only"]
    )
    # Note: diff --cached is not in whitelist, so this won't work
    # We rely on git status which shows staged files

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
