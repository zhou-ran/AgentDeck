from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class NotificationEvent(BaseModel):
    """A summary event to be sent via webhook."""

    session_title: str = ""
    source: str = ""
    source_id: str = ""
    cwd_short: str = ""
    status: str = ""
    summary: str = ""
    recent_output_snippet: str = ""
    dashboard_url: str = ""
    cpu_percent: float = 0.0
    elapsed_sec: int | None = None


class Notifier(Protocol):
    """Protocol for notification backends."""

    name: str
    enabled: bool

    def send(self, event: NotificationEvent) -> bool:
        ...
