from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel


class RawSession(BaseModel):
    """Unified representation of a terminal session from any source."""

    source: Literal["tmux", "screen", "process", "managed"]
    source_id: str
    title: str | None = None
    cwd: str | None = None
    root_pid: int | None = None
    command: str | None = None
    recent_output: str | None = None
    attached: bool | None = None
    created_at: float | None = None
    updated_at: float | None = None


class SessionSource(Protocol):
    """Protocol for session discovery sources."""

    name: str

    def discover(self) -> list[RawSession]:
        ...


class RuntimeTypeResult(BaseModel):
    """Structured result for runtime type detection."""

    runtime_type: str = "unknown"
    detected_app: str = ""
    confidence: float = 0.0
    reason: str = ""
