from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.task_manager import list_tasks, _log_path
from backend.process_scanner import (
    discover_sessions,
    get_resource_metrics,
    get_history,
    record_sample,
    cleanup_history,
    get_system_metrics,
)

router = APIRouter(tags=["sse"])


@router.get("/events")
async def api_stream():
    """SSE endpoint: pushes task list + discovered sessions + system metrics every 2 seconds."""

    async def event_generator():
        while True:
            tasks = list_tasks()
            data = []
            active_pids: set[int] = set()

            for t in tasks:
                task_dict = t.model_dump(mode="json")
                # Attach live log metadata
                log_p = _log_path(t.task_id)
                if log_p.exists():
                    task_dict["log_size"] = log_p.stat().st_size
                    task_dict["log_mtime"] = log_p.stat().st_mtime
                else:
                    task_dict["log_size"] = 0
                    task_dict["log_mtime"] = 0

                # Attach resource metrics for running tasks
                if t.pid and t.status in ("running", "idle"):
                    active_pids.add(t.pid)
                    record_sample(t.pid)
                    res = get_resource_metrics(t.pid)
                    task_dict["resources"] = res.model_dump() if res else None
                    task_dict["cpu_mem_history"] = [
                        {"ts": s.ts, "cpu": s.cpu, "mem": s.mem}
                        for s in get_history(t.pid)
                    ]
                else:
                    task_dict["resources"] = None
                    task_dict["cpu_mem_history"] = []

                data.append(task_dict)

            # Cleanup history for dead PIDs
            cleanup_history(active_pids)

            # Discovered sessions
            sessions = discover_sessions()
            sessions_data = [s.model_dump(mode="json") for s in sessions]

            # System metrics
            project_dirs = list({t.project_dir for t in tasks if t.project_dir})
            sys_metrics = get_system_metrics(project_dirs).model_dump()

            yield {
                "event": "update",
                "data": json.dumps({
                    "tasks": data,
                    "discovered": sessions_data,
                    "system": sys_metrics,
                }, default=str),
            }
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
