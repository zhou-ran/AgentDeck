from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    running = "running"
    idle = "idle"
    waiting_input = "waiting_input"
    completed = "completed"
    failed = "failed"
    unknown = "unknown"


class Task(BaseModel):
    task_id: str
    name: str
    project_dir: str
    command: str
    pid: Optional[int] = None
    status: TaskStatus = TaskStatus.unknown
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    last_log_update: Optional[datetime] = None
    acceptance_criteria: str = ""
    current_step: str = ""
    progress_notes: list[str] = Field(default_factory=list)
    exit_code: Optional[int] = None
    has_error_hint: bool = False
    tags: list[str] = Field(default_factory=list)


class ProcessInfo(BaseModel):
    pid: int
    ppid: int
    name: str
    cmdline: list[str]
    cwd: str = ""
    user: str = ""
    status: str = ""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    create_time: float = 0.0
    elapsed: str = ""
    children: list[ProcessInfo] = Field(default_factory=list)


class TaskCreate(BaseModel):
    task_id: str
    name: str
    project_dir: str
    command: str
    acceptance_criteria: str = ""
    tags: list[str] = Field(default_factory=list)


class NoteAdd(BaseModel):
    note: str
