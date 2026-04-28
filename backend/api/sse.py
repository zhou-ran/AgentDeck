from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from backend.task_manager import list_tasks, _log_path
from backend.log_manager import get_log_mtime

router = APIRouter(tags=["sse"])


@router.get("/events")
async def api_stream():
    """SSE endpoint: pushes task list updates every 2 seconds."""

    async def event_generator():
        while True:
            tasks = list_tasks()
            data = []
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
                data.append(task_dict)

            yield {
                "event": "update",
                "data": json.dumps(data, default=str),
            }
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
