from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    running = "running"
    idle = "idle"
    waiting_input = "waiting_input"
    completed = "completed"
    failed = "failed"
    unknown = "unknown"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    blocked = "blocked"


class PlanStep(BaseModel):
    id: str
    title: str
    status: StepStatus = StepStatus.pending
    notes: str = ""


class ProgressLogEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str
    step_id: Optional[str] = None


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

    # Structured task fields
    goal: str = ""
    feature: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    plan: list[PlanStep] = Field(default_factory=list)
    current_step_id: Optional[str] = None
    progress_log: list[ProgressLogEntry] = Field(default_factory=list)
    handoff_notes: str = ""
    changed_files: list[str] = Field(default_factory=list)
    risk_notes: str = ""
    final_summary: str = ""

    # Legacy fields
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
    goal: str = ""
    feature: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PlanImport(BaseModel):
    steps: list[PlanStep]


class StepUpdate(BaseModel):
    status: StepStatus
    notes: str = ""


class NoteAdd(BaseModel):
    note: str


class TaskComplete(BaseModel):
    summary: str


class TaskFail(BaseModel):
    reason: str
