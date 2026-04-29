"""Security helpers for AgentDeck.

Provides:
- Path traversal prevention
- Symlink detection for project directories
- Atomic file writes
- Input sanitization for task IDs
- Token management with env var support
- Simple rate limiter
"""

from __future__ import annotations

import os
import re
import secrets
import tempfile
import time
from pathlib import Path

# --- Constants ---

# Allowed characters for task_id: alphanumeric, dash, underscore, dot
_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")

# Directories where logs are allowed to be read
ALLOWED_LOG_DIRS: list[Path] = []


def init_allowed_dirs() -> None:
    """Initialize allowed log directories from config. Call once at startup."""
    from backend.config import get_log_dir, get_tasks_dir
    ALLOWED_LOG_DIRS.clear()
    ALLOWED_LOG_DIRS.append(get_log_dir().resolve())
    ALLOWED_LOG_DIRS.append(get_tasks_dir().resolve())


# --- Task ID Sanitization ---

def is_valid_task_id(task_id: str) -> bool:
    """Check task_id contains only safe characters (no path traversal)."""
    return bool(_TASK_ID_RE.match(task_id))


# --- Path Traversal Prevention ---

def is_path_within(path: Path, parent: Path) -> bool:
    """Check that resolved path is within parent directory."""
    try:
        resolved = path.resolve()
        parent_resolved = parent.resolve()
        return resolved == parent_resolved or str(resolved).startswith(str(parent_resolved) + os.sep)
    except (OSError, ValueError):
        return False


def is_safe_log_path(log_path: Path) -> bool:
    """Verify log path is within allowed directories and not a symlink."""
    if not ALLOWED_LOG_DIRS:
        init_allowed_dirs()
    resolved = log_path.resolve()
    # Must be under an allowed directory
    if not any(is_path_within(resolved, d) for d in ALLOWED_LOG_DIRS):
        return False
    # Reject if the file itself is a symlink
    try:
        if log_path.is_symlink():
            return False
    except OSError:
        return False
    return True


# --- Project Directory Validation ---

def is_safe_project_dir(project_dir: str) -> tuple[bool, str]:
    """Validate project_dir is a real directory, not a symlink to sensitive paths.

    Returns (is_safe, error_message).
    """
    p = Path(project_dir)

    # Must be absolute
    if not p.is_absolute():
        return False, "project_dir must be an absolute path"

    # Must exist and be a directory
    if not p.exists():
        return False, f"project_dir does not exist: {project_dir}"
    if not p.is_dir():
        return False, f"project_dir is not a directory: {project_dir}"

    # Reject symlinks
    try:
        if p.is_symlink():
            return False, f"project_dir is a symlink: {project_dir}"
    except OSError:
        return False, f"Cannot check project_dir: {project_dir}"

    # Reject sensitive directories
    sensitive = ["/etc", "/proc", "/sys", "/dev", "/boot", "/root"]
    resolved = str(p.resolve())
    for s in sensitive:
        if resolved == s or resolved.startswith(s + os.sep):
            return False, f"project_dir is in a sensitive directory: {s}"

    # Reject if path contains ..
    if ".." in project_dir:
        return False, "project_dir must not contain '..'"

    return True, ""


# --- Atomic File Write ---

def atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using temp file + rename.

    This prevents partial writes from corrupting the file.
    """
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# --- Token Management ---

def get_token() -> str:
    """Get authentication token. Priority:
    1. AGENT_FOREMAN_TOKEN env var
    2. config.yaml
    3. Auto-generate and save
    """
    # Env var takes priority
    env_token = os.environ.get("AGENT_FOREMAN_TOKEN")
    if env_token:
        return env_token

    # Fall back to config
    from backend.config import get_or_create_token
    return get_or_create_token()


# --- Input Sanitization ---

def sanitize_note(note: str, max_len: int = 10000) -> str:
    """Sanitize user-supplied note text."""
    # Truncate
    note = note[:max_len]
    # Remove null bytes
    note = note.replace("\x00", "")
    return note


# --- Rate Limiter ---

class RateLimiter:
    """Simple in-memory rate limiter using sliding window."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if request from key is allowed."""
        now = time.time()
        cutoff = now - self.window

        if key not in self._requests:
            self._requests[key] = []

        # Prune old entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        if len(self._requests[key]) >= self.max_requests:
            return False

        self._requests[key].append(now)
        return True

    def cleanup(self) -> None:
        """Remove stale entries."""
        now = time.time()
        cutoff = now - self.window
        stale = [k for k, v in self._requests.items() if not v or v[-1] < cutoff]
        for k in stale:
            del self._requests[k]


# Global rate limiter instance
api_rate_limiter = RateLimiter(max_requests=120, window_seconds=60)
