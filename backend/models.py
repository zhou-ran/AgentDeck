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
    status_reason: str = ""
    current_activity: str = ""
    agent_type: str = ""
    project_name: str = ""
    short_cwd: str = ""
    user_instruction: Optional[str] = None
    instruction_source: str = ""

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
    rss_mb: float = 0.0          # Resident Set Size in MB
    vms_mb: float = 0.0          # Virtual Memory Size in MB
    child_count: int = 0         # Number of child processes
    open_files: int = 0          # Number of open file descriptors
    read_bytes: float = 0.0      # Total bytes read (from /proc/pid/io)
    write_bytes: float = 0.0     # Total bytes written
    status: str = ""             # process status


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


class ProjectNameInfo(BaseModel):
    """Project name derived from cwd/git root."""
    display_name: str = ""
    base_project: str = ""
    workspace: str = ""
    project_dir: str = ""
    short_cwd: str = ""


class InstructionInfo(BaseModel):
    """User instruction extracted from session files."""
    text: Optional[str] = None
    source_file: str = ""
    source_type: str = ""
    timestamp: Optional[datetime] = None
    confidence: float = 0.0


class ProjectRuntimeStatus(BaseModel):
    """Git and runtime status for a project directory."""
    git_branch: str = ""
    git_dirty_files_count: int = 0
    git_changed_files: list[str] = Field(default_factory=list)
    recent_modified_files: list[str] = Field(default_factory=list)
    test_processes: list[str] = Field(default_factory=list)
    server_processes: list[str] = Field(default_factory=list)
    error_hints: list[str] = Field(default_factory=list)
    last_activity_time: Optional[datetime] = None


class ActivityTimelineItem(BaseModel):
    """A single activity event in the session timeline."""
    timestamp: datetime = Field(default_factory=datetime.now)
    label: str
    source: str = ""


class CpuMemSample(BaseModel):
    """Single CPU/MEM data point for history."""
    ts: float          # timestamp (time.time())
    cpu: float = 0.0
    mem: float = 0.0


class SystemMetrics(BaseModel):
    """System-wide resource overview."""
    cpu_percent: float = 0.0
    mem_total_gb: float = 0.0
    mem_used_gb: float = 0.0
    mem_percent: float = 0.0
    disk_usages: list[dict[str, Any]] = Field(default_factory=list)  # [{path, total_gb, used_gb, percent}]
    net_interfaces: list[dict[str, Any]] = Field(default_factory=list)  # [{name, rx_mbps, tx_mbps}]


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
    """A group of processes under the same cwd, discovered by auto-scan.

    Enriched with session file parsing, project name, activity inference,
    and git status.
    """
    session_id: str  # derived from cwd or PID
    cwd: str
    root_process: ProcessInfo
    all_pids: list[int] = Field(default_factory=list)
    agent_type: str = ""  # e.g. "codex", "claude", "kimi-code"

    # Enriched fields
    root_pid: int = 0
    root_cmd: str = ""
    user: str = ""
    project_name: str = ""
    project: ProjectNameInfo = Field(default_factory=ProjectNameInfo)
    short_cwd: str = ""
    started_at: Optional[datetime] = None
    elapsed: str = ""

    # Status
    status: TaskStatus = TaskStatus.unknown
    status_reason: str = ""
    current_activity: str = ""

    # Session-derived fields
    heartbeat_ts: Optional[float] = None
    heartbeat_age_sec: Optional[float] = None
    user_instruction: Optional[str] = None
    instruction: InstructionInfo = Field(default_factory=InstructionInfo)
    instruction_source: str = ""
    instruction_candidates: list[InstructionInfo] = Field(default_factory=list)

    # Process details
    child_processes: list[ProcessInfo] = Field(default_factory=list)
    active_commands: list[str] = Field(default_factory=list)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0

    # Log and project status
    log_candidates: list[str] = Field(default_factory=list)
    recent_logs: list[str] = Field(default_factory=list)
    project_status: ProjectRuntimeStatus = Field(default_factory=ProjectRuntimeStatus)
    git_status: dict[str, Any] = Field(default_factory=dict)
    recent_changed_files: list[str] = Field(default_factory=list)
    error_hints: list[str] = Field(default_factory=list)
    recent_output: str = ""
    pending_items: list[str] = Field(default_factory=list)
    last_user_message: str = ""

    # Metadata
    confidence: float = 0.0
    timeline: list[ActivityTimelineItem] = Field(default_factory=list)


class ImportPidRequest(BaseModel):
    pid: int
    name: str
