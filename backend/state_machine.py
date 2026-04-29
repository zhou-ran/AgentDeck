from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from backend.log_manager import get_log_tail
from backend.models import Task, TaskStatus

_ERROR_RE = re.compile(
    r"(Traceback|ERROR|Exception|command not found|permission denied|quota exceeded|API error|rate limit|认证失败)",
    re.IGNORECASE,
)


def _log_tail(path: Path, lines: int = 50) -> str:
    return "\n".join(get_log_tail(path, lines=lines))


def check_error_hint(log_path: Path | None) -> bool:
    if not log_path or not log_path.exists():
        return False
    tail = _log_tail(log_path, lines=50)
    return bool(_ERROR_RE.search(tail))


def infer_status(
    task: Task,
    process_alive: bool,
    cpu_percent: float,
    log_path: Path | None,
) -> TaskStatus:
    # PID not alive → completed or failed
    if not process_alive:
        if task.exit_code is not None:
            return TaskStatus.completed if task.exit_code == 0 else TaskStatus.failed
        # No exit_code recorded yet, check log for error hints
        if check_error_hint(log_path):
            return TaskStatus.failed
        return TaskStatus.completed

    # PID alive → check if idle
    # idle = CPU < 0.5% AND log not updated in 5 minutes
    if cpu_percent < 0.5:
        try:
            if log_path and log_path.exists():
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
                if (datetime.now() - mtime) > timedelta(minutes=5):
                    return TaskStatus.idle
        except OSError:
            pass

    return TaskStatus.running
