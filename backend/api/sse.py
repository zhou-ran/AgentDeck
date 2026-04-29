from __future__ import annotations

import asyncio
import json
import socket
import time

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.models import DiscoveredSession
from backend.task_manager import get_task_log_metadata, list_tasks
from backend.process_scanner import (
    scan_agent_sessions,
    get_resource_metrics,
    get_history,
    record_sample,
    cleanup_history,
    get_system_metrics,
)

router = APIRouter(tags=["sse"])

_DISCOVERY_TTL_SECONDS = 10
_discovery_cache: list[DiscoveredSession] = []
_discovery_cache_ts = 0.0


def _get_discovered_sessions_cached() -> list[DiscoveredSession]:
    global _discovery_cache, _discovery_cache_ts

    now = time.time()
    if now - _discovery_cache_ts >= _DISCOVERY_TTL_SECONDS:
        _discovery_cache = scan_agent_sessions()
        _discovery_cache_ts = now
    return _discovery_cache


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
                task_dict.update(get_task_log_metadata(t.task_id))

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
            sessions = _get_discovered_sessions_cached()
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
                    "scan": {
                        "hostname": socket.gethostname(),
                        "last_scan_time": _discovery_cache_ts,
                        "scan_interval": 2,
                        "discovery_ttl": _DISCOVERY_TTL_SECONDS,
                        "active_sessions_count": len(sessions),
                    },
                }, default=str),
            }
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@router.get("/system-metrics")
async def api_system_metrics():
    """Get system-wide resource metrics (CPU, memory, disk, network)."""
    tasks = list_tasks()
    project_dirs = list({t.project_dir for t in tasks if t.project_dir})
    return get_system_metrics(project_dirs).model_dump()
