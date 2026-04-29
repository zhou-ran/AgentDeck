from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    running = "running"
    busy = "busy"
    testing = "testing"
    editing = "editing"
    searching = "searching"
    git_ops = "git_ops"
    running_script = "running_script"
    waiting = "waiting"
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


class ProjectNameInfo(BaseModel):
    """Extracted project name and display info."""
    name: str = ""
    short_cwd: str = ""
    git_root: Optional[str] = None
    git_branch: Optional[str] = None


class InstructionInfo(BaseModel):
    """User instruction extracted from session or logs."""
    text: str = ""
    source: str = ""  # "session_file", "log_file", "process_name"
    source_file: str = ""
    confidence: float = 0.0


class ProjectRuntimeStatus(BaseModel):
    """Runtime status of a project directory."""
    dirty_files: list[str] = Field(default_factory=list)
    has_uncommitted: bool = False
    has_untracked: bool = False
    test_status: str = ""  # "passing", "failing", "unknown"
    last_commit_msg: str = ""


class ActivityTimelineItem(BaseModel):
    """Single entry in the activity timeline."""
    ts: float = 0.0
    event: str = ""
    detail: str = ""


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

    # Enriched fields
    status_reason: str = ""
    current_activity: str = ""
    agent_type: str = ""
    project_name: str = ""
    short_cwd: str = ""
    user_instruction: str = ""
    instruction_source: str = ""

    # Import tracking
    imported: bool = False
    imported_from_pid: Optional[int] = None

    # Legacy fields
    exit_code: Optional[int] = None
    has_error_hint: bool = False
    tags: list[str] = Field(default_factory=list)


class ResourceMetrics(BaseModel):
    """Per-process resource usage snapshot."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    rss_mb: float = 0.0
    vms_mb: float = 0.0
    child_count: int = 0
    open_files: int = 0
    read_bytes: float = 0.0
    write_bytes: float = 0.0
    status: str = ""


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
    resources: Optional[ResourceMetrics] = None


class CpuMemSample(BaseModel):
    """Single CPU/MEM data point for history."""
    ts: float
    cpu: float = 0.0
    mem: float = 0.0


class SystemMetrics(BaseModel):
    """System-wide resource overview."""
    cpu_percent: float = 0.0
    mem_total_gb: float = 0.0
    mem_used_gb: float = 0.0
    mem_percent: float = 0.0
    disk_usages: list[dict[str, Any]] = Field(default_factory=list)
    net_interfaces: list[dict[str, Any]] = Field(default_factory=list)


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


class DiscoveredSession(BaseModel):
    """A group of processes under the same cwd, discovered by auto-scan."""
    session_id: str
    cwd: str
    root_process: ProcessInfo
    all_pids: list[int] = Field(default_factory=list)
    agent_type: str = ""

    # Enriched fields
    project_name: ProjectNameInfo = Field(default_factory=ProjectNameInfo)
    project: str = ""  # display name shortcut
    status: str = "unknown"
    status_reason: str = ""
    current_activity: str = ""
    user_instruction: str = ""
    instruction: InstructionInfo = Field(default_factory=InstructionInfo)
    child_processes: list[ProcessInfo] = Field(default_factory=list)
    active_commands: list[str] = Field(default_factory=list)

    # Heartbeat
    heartbeat_ts: Optional[float] = None
    heartbeat_age_sec: Optional[float] = None

    # Session file data
    recent_output: str = ""
    pending_items: list[str] = Field(default_factory=list)
    last_user_message: str = ""

    # Resource metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0

    # Project status
    project_status: ProjectRuntimeStatus = Field(default_factory=ProjectRuntimeStatus)
    git_status: str = ""
    error_hints: list[str] = Field(default_factory=list)

    # Timeline
    timeline: list[ActivityTimelineItem] = Field(default_factory=list)

    # Log info
    recent_logs: list[str] = Field(default_factory=list)


class ImportPidRequest(BaseModel):
    pid: int
    name: str
