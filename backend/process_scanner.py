from __future__ import annotations

import collections
import hashlib
import os
import re
import time
from pathlib import Path
from typing import Optional

import psutil

from backend.models import (
    ActivityTimelineItem,
    CpuMemSample,
    DiscoveredSession,
    InstructionInfo,
    ProjectNameInfo,
    ProjectRuntimeStatus,
    ProcessInfo,
    ResourceMetrics,
    SystemMetrics,
)
from backend.git_utils import (
    get_changed_files,
    get_git_branch,
    get_git_root,
    get_git_status_short,
)

# ---- Root agent patterns for detecting top-level agents ----
ROOT_AGENT_PATTERNS = [
    re.compile(r"codex\b", re.I),
    re.compile(r"claude[-_]?code\b", re.I),
    re.compile(r"claude\b", re.I),
    re.compile(r"kimi[-_]?code\b", re.I),
    re.compile(r"kimi\b", re.I),
    re.compile(r"aider\b", re.I),
    re.compile(r"gemini\b", re.I),
]

# ---- Needs-input detection patterns ----
WAITING_RE = re.compile(
    r"(?:"
    r"\?$|would you like|shall i|which (?:option|approach)|let me know|"
    r"please provide|please confirm|please choose|please tell me|"
    r"do you want me to|should i continue|is this correct|"
    r"请提供|是否需要|请确认|请选择|请告诉我|你想要|要我继续吗|这样对吗"
    r")",
    re.I,
)

# ---- Error detection patterns ----
ERROR_RE = re.compile(
    r"(?:Traceback|ERROR|Failed|FAILED|Exception|panic:|fatal:|permission denied|quota exceeded)",
    re.I,
)

# ---- Instruction label patterns ----
INSTRUCTION_LABEL_RE = re.compile(
    r"(?:^|\n)(?:user(?:\s+instruction)?|task|goal|指令|任务|目标)\s*[:：]\s*(.+?)(?:\n|$)",
    re.I,
)


def _format_elapsed(start_time: float) -> str:
    secs = int(time.time() - start_time)
    if secs < 60:
        return f"{secs}s"
    mins, s = divmod(secs, 60)
    if mins < 60:
        return f"{mins}m{s}s"
    hours, m = divmod(mins, 60)
    return f"{hours}h{m}m"


def _proc_to_info(proc: psutil.Process, include_children: bool = True) -> Optional[ProcessInfo]:
    """Convert psutil Process to ProcessInfo.

    SECURITY: We only read specific attrs via as_dict(). We NEVER read
    proc.environ() or /proc/<pid>/environ to avoid leaking API keys,
    secrets, or environment variables.
    """
    try:
        info = proc.as_dict(attrs=[
            "pid", "ppid", "name", "cmdline", "status",
            "cpu_percent", "memory_percent", "create_time",
        ])
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    try:
        cwd = proc.cwd()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        cwd = ""

    try:
        username = proc.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        username = ""

    children = []
    if include_children:
        try:
            for child in proc.children(recursive=False):
                child_info = _proc_to_info(child, include_children=True)
                if child_info:
                    children.append(child_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return ProcessInfo(
        pid=info["pid"],
        ppid=info["ppid"],
        name=info["name"] or "",
        cmdline=info["cmdline"] or [],
        cwd=cwd,
        user=username,
        status=info["status"] or "",
        cpu_percent=info["cpu_percent"] or 0.0,
        memory_percent=info["memory_percent"] or 0.0,
        create_time=info["create_time"] or 0.0,
        elapsed=_format_elapsed(info["create_time"] or time.time()),
        children=children,
    )


def get_process_tree(pid: int) -> Optional[ProcessInfo]:
    """Get full process tree rooted at pid."""
    try:
        proc = psutil.Process(pid)
        return _proc_to_info(proc, include_children=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_process_info(pid: int) -> Optional[ProcessInfo]:
    """Get single process info without children."""
    try:
        proc = psutil.Process(pid)
        return _proc_to_info(proc, include_children=False)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def is_process_alive(pid: int) -> bool:
    return psutil.pid_exists(pid)


def _agent_type_from_text(text: str) -> str:
    text_lower = text.lower()
    for agent_type, pattern in (
        ("claude-code", re.compile(r"claude[-_]?code\b", re.I)),
        ("kimi-code", re.compile(r"kimi[-_]?code\b", re.I)),
        ("codex", re.compile(r"codex\b", re.I)),
        ("claude", re.compile(r"claude\b", re.I)),
        ("kimi", re.compile(r"kimi\b", re.I)),
        ("aider", re.compile(r"aider\b", re.I)),
        ("gemini", re.compile(r"gemini\b", re.I)),
    ):
        if pattern.search(text_lower):
            return agent_type
    return ""


def _proc_text(proc: psutil.Process) -> str:
    try:
        return " ".join([proc.name(), *(proc.cmdline() or [])])
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return ""


def _is_root_agent_process(proc: psutil.Process, text: str) -> bool:
    if not _agent_type_from_text(text):
        return False
    try:
        parent = proc.parent()
        while parent:
            if _agent_type_from_text(_proc_text(parent)):
                return False
            parent = parent.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    return True


def discover_agent_processes() -> list[ProcessInfo]:
    """Scan running processes and find top-level coding agent roots."""
    results = []
    seen_pids: set[int] = set()

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmdline_list = proc.info.get("cmdline") or []
            name = proc.info.get("name") or ""
            text = " ".join([name, *cmdline_list])
            if not _is_root_agent_process(proc, text):
                continue

            pid = proc.info["pid"]
            if pid in seen_pids:
                continue
            seen_pids.add(pid)

            info = _proc_to_info(proc, include_children=True)
            if info:
                results.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return results


def _detect_agent_type(info: ProcessInfo) -> str:
    """Detect the agent type from process name/cmdline."""
    return _agent_type_from_text(" ".join([info.name, *info.cmdline])) or "unknown"


def _detect_agent_type_from_text(text: str) -> str:
    """Detect agent type from arbitrary text (cmdline, session file content)."""
    text_lower = text.lower()
    for kw in ("codex", "claude-code", "claude", "aider", "gemini", "kimi-code", "kimi"):
        if kw in text_lower:
            return kw
    return ""


def _git_root(cwd: str) -> Optional[str]:
    """Find the git root directory for a given cwd."""
    if not cwd or not os.path.isdir(cwd):
        return None
    return get_git_root(cwd)


def derive_project_name(cwd: str) -> ProjectNameInfo:
    """Derive a human-readable project name from the cwd."""
    if not cwd:
        return ProjectNameInfo(name="unknown", short_cwd="unknown")

    git_root = _git_root(cwd)
    git_branch = None
    if git_root:
        git_branch = get_git_branch(git_root) or None

    # Use git root basename if available, otherwise cwd basename
    if git_root:
        name = os.path.basename(git_root)
    else:
        name = os.path.basename(cwd)

    # Short cwd: show last 2-3 components
    parts = cwd.rstrip("/").split("/")
    short_cwd = "/".join(parts[-3:]) if len(parts) > 3 else cwd

    return ProjectNameInfo(
        name=name or "unknown",
        short_cwd=short_cwd or cwd,
        git_root=git_root,
        git_branch=git_branch,
    )


def _recent_modified_files(cwd: str, seconds: int = 60) -> list[str]:
    """Find files modified in the last N seconds under cwd."""
    if not cwd or not os.path.isdir(cwd):
        return []
    cutoff = time.time() - seconds
    modified = []
    try:
        for root, dirs, files in os.walk(cwd):
            # Skip hidden dirs and common non-project dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")]
            for f in files:
                fpath = os.path.join(root, f)
                try:
                    if os.path.getmtime(fpath) >= cutoff:
                        modified.append(os.path.relpath(fpath, cwd))
                except OSError:
                    continue
    except Exception:
        pass
    return modified[:20]  # Cap at 20


def _candidate_log_files(project_dir: str) -> list[Path]:
    """Find candidate log files for a project."""
    candidates = []
    roots: list[Path] = []
    if project_dir:
        p = Path(project_dir)
        roots.extend([p / "logs", p / ".codex", p / ".claude", p / ".kimi", p / ".kimi-code"])
        git_root = get_git_root(project_dir)
        if git_root:
            gp = Path(git_root)
            roots.extend([gp / "logs", gp / ".codex", gp / ".claude", gp / ".kimi", gp / ".kimi-code"])
    roots.append(Path.home() / "agent_logs")

    seen: set[Path] = set()
    for root in roots:
        try:
            root = root.expanduser().resolve()
        except OSError:
            continue
        if root in seen or not root.exists():
            continue
        seen.add(root)
        try:
            for pattern in ("*.log", "*.jsonl"):
                for f in root.rglob(pattern):
                    if f.is_file():
                        candidates.append(f)
        except PermissionError:
            pass
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:20]


def _extract_instruction_from_text(text: str) -> str:
    """Extract user instruction from text using regex patterns."""
    if not text:
        return ""
    # Try labeled patterns
    match = INSTRUCTION_LABEL_RE.search(text)
    if match:
        return match.group(1).strip()[:180]
    # If text is short enough, it might be an instruction itself
    cleaned = " ".join(text.split())
    if len(cleaned) < 180 and not cleaned.startswith(("tool:", "Traceback", "Error")):
        return cleaned
    return ""


def extract_user_instruction(
    project_dir: str,
    agent_type: str,
    session_data: dict | None = None,
) -> InstructionInfo:
    """Extract the user's instruction/intent from available sources.

    Priority: session file last_user_message > log file > process cmdline
    """
    # 1. Session file data (highest confidence)
    if session_data and session_data.get("last_user_message"):
        return InstructionInfo(
            text=session_data["last_user_message"],
            source="session_file",
            source_file=session_data.get("source_file", ""),
            confidence=0.9,
        )

    # 2. Log files
    log_files = _candidate_log_files(project_dir)
    for log_file in log_files[:5]:
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            instruction = _extract_instruction_from_text(content)
            if instruction:
                return InstructionInfo(
                    text=instruction,
                    source="log_file",
                    source_file=str(log_file),
                    confidence=0.6,
                )
        except Exception:
            continue

    return InstructionInfo(text="未找到原始指令", source="", source_file="", confidence=0.0)


def _collect_active_commands(info: ProcessInfo) -> list[str]:
    """Collect active commands from a process tree."""
    commands = []
    if info.cmdline:
        cmd = " ".join(info.cmdline[:5])
        commands.append(cmd[:120])
    for child in info.children:
        if child.cmdline:
            cmd = " ".join(child.cmdline[:5])
            commands.append(cmd[:120])
    return commands[:10]


def get_project_runtime_status(project_dir: str, recent_files: list[str] | None = None) -> ProjectRuntimeStatus:
    """Get runtime status of a project directory."""
    if not project_dir or not os.path.isdir(project_dir):
        return ProjectRuntimeStatus()

    git_root = get_git_root(project_dir) or project_dir
    dirty = get_changed_files(git_root)
    status_short = get_git_status_short(git_root)
    has_uncommitted = bool(status_short)
    has_untracked = any(line.startswith("??") for line in status_short.splitlines())

    test_status = "unknown"

    return ProjectRuntimeStatus(
        dirty_files=dirty[:20],
        has_uncommitted=has_uncommitted,
        has_untracked=has_untracked,
        test_status=test_status,
        branch=get_git_branch(git_root),
        recent_files=(recent_files or [])[:20],
    )


def infer_session_activity(
    info: ProcessInfo,
    recent_output: str = "",
    heartbeat_ts: float | None = None,
    recent_files: list[str] | None = None,
    has_error_hint: bool = False,
) -> tuple[str, str]:
    """Infer what the agent is currently doing.

    Returns (activity, reason) tuple.

    Priority chain:
    1. needs_input (regex on recent_output)
    2. error_hint (recent output contains an error marker)
    3. testing/searching/git_ops/running_script (child process)
    4. editing (file modified in last 60s)
    5. busy (CPU >= 3% or heartbeat <= 120s)
    6. stale (heartbeat >= 900s)
    7. idle (default)
    """
    now = time.time()

    # 1. Needs input detection
    if recent_output and WAITING_RE.search(recent_output):
        return "needs_input", "可能在等待用户确认或补充信息"

    if has_error_hint or (recent_output and ERROR_RE.search(recent_output)):
        return "error_hint", "最近输出出现错误提示"

    # 2-5. Check child processes for specific activities
    child_activity = _check_child_processes(info)
    if child_activity:
        return child_activity

    # 6. Editing detection (recent file modifications)
    if recent_files:
        return "editing", f"正在修改 {', '.join(recent_files[:3])}"

    # 7. Busy detection
    if info.cpu_percent >= 3.0:
        return "busy", f"CPU 活跃：{info.cpu_percent:.1f}%"

    if heartbeat_ts:
        age = now - heartbeat_ts
        if age <= 120:
            return "busy", f"最近 {int(age)} 秒内有新输出"

    # 8. Stale detection
    if heartbeat_ts:
        age = now - heartbeat_ts
        if age >= 900:
            return "stale", f"{int(age // 60)} 分钟无新输出，可能空闲"

    # 9. Default idle
    return "idle", "CPU 很低，且未检测到子进程或新输出"


def _iter_process_tree(info: ProcessInfo) -> list[ProcessInfo]:
    items = []
    for child in info.children:
        items.append(child)
        items.extend(_iter_process_tree(child))
    return items


def _cmd_basename(cmd: str) -> str:
    return os.path.basename(cmd).lower()


def _check_child_processes(info: ProcessInfo) -> tuple[str, str] | None:
    """Check child processes for specific activity patterns."""
    for child in _iter_process_tree(info):
        cmd_lower = " ".join(child.cmdline).lower() if child.cmdline else ""
        name_lower = child.name.lower()
        argv0 = _cmd_basename(child.cmdline[0]) if child.cmdline else name_lower

        # Testing
        if any(kw in cmd_lower for kw in ("pytest", "npm test", "jest", "vitest", "cargo test", "go test")):
            return "testing", f"正在跑测试：{' '.join(child.cmdline[:3]) if child.cmdline else child.name}"

        # Git operations
        if name_lower == "git" or argv0 == "git":
            return "git_ops", f"正在执行 git：{' '.join(child.cmdline[:3]) if child.cmdline else 'git'}"

        # Searching
        if argv0 in {"rg", "grep", "ag", "find", "fd"} or name_lower in {"rg", "grep", "ag", "find", "fd"}:
            return "searching", f"正在搜索代码库：{' '.join(child.cmdline[:3]) if child.cmdline else child.name}"

        # Running scripts
        if argv0 in {"python", "python3", "rscript", "bash", "node", "npm", "pnpm", "bun"} or "npm run" in cmd_lower:
            return "running_script", f"正在运行脚本：{' '.join(child.cmdline[:3]) if child.cmdline else child.name}"

    return None


def discover_sessions() -> list[DiscoveredSession]:
    """Discover agent processes and group them by cwd into sessions.

    Each session represents a project directory with one or more agent processes.
    The process with the lowest PID in each cwd group becomes the root_process.
    """
    procs = discover_agent_processes()
    if not procs:
        return []

    # Group by cwd
    by_cwd: dict[str, list[ProcessInfo]] = {}
    for p in procs:
        cwd = p.cwd or "unknown"
        by_cwd.setdefault(cwd, []).append(p)

    sessions: list[DiscoveredSession] = []
    for cwd, group in by_cwd.items():
        # Sort by PID, pick lowest as root
        group.sort(key=lambda p: p.pid)
        root = group[0]
        all_pids = [p.pid for p in group]

        # Also collect child PIDs recursively
        def _collect_pids(pi: ProcessInfo) -> list[int]:
            pids = [pi.pid]
            for c in pi.children:
                pids.extend(_collect_pids(c))
            return pids

        all_pids_set: set[int] = set()
        for p in group:
            all_pids_set.update(_collect_pids(p))

        # Generate session_id from cwd
        if cwd == "unknown":
            session_id = f"unknown-{root.pid}"
        else:
            h = hashlib.md5(cwd.encode()).hexdigest()[:8]
            session_id = f"discovered-{h}"

        sessions.append(DiscoveredSession(
            session_id=session_id,
            cwd=cwd,
            root_process=root,
            all_pids=sorted(all_pids_set),
            agent_type=_detect_agent_type(root),
        ))

    # Sort by cwd for stable ordering
    sessions.sort(key=lambda s: s.cwd)
    return sessions


def scan_agent_sessions() -> list[DiscoveredSession]:
    """Main enrichment pipeline: discover processes → parse session files → extract info → infer activity.

    This is the primary entry point for the SSE endpoint.
    """
    sessions = discover_sessions()
    if not sessions:
        return []

    enriched: list[DiscoveredSession] = []
    for session in sessions:
        cwd = session.cwd if session.cwd != "unknown" else ""
        agent_type = session.agent_type
        root = session.root_process

        # 1. Derive project name
        project_name = derive_project_name(cwd)
        session.project_name = project_name
        session.project = project_name.name

        # 2. Parse session files (heartbeat, recent_output, pending_items)
        session_data = None
        if agent_type and agent_type != "unknown":
            from backend.session_parser import parse_and_match_sessions
            session_data = parse_and_match_sessions(
                agent_type, cwd, root.create_time
            )
            if session_data:
                session.heartbeat_ts = session_data.get("heartbeat_ts")
                session.recent_output = session_data.get("recent_output", "")
                session.pending_items = session_data.get("pending_items", [])
                session.last_user_message = session_data.get("last_user_message", "")
                if session_data.get("git_branch"):
                    session.project_name.git_branch = session_data["git_branch"]

        # 3. Compute heartbeat age
        if session.heartbeat_ts:
            session.heartbeat_age_sec = time.time() - session.heartbeat_ts

        # 4. Recent file modifications
        recent_files = _recent_modified_files(cwd, seconds=60) if cwd else []

        # 5. Infer activity status
        if session.recent_output:
            error_matches = ERROR_RE.findall(session.recent_output)
            if error_matches:
                session.error_hints = list(dict.fromkeys(error_matches))[:5]

        activity, reason = infer_session_activity(
            root,
            recent_output=session.recent_output,
            heartbeat_ts=session.heartbeat_ts,
            recent_files=recent_files,
            has_error_hint=bool(session.error_hints),
        )
        session.status = activity
        session.status_reason = reason
        session.current_activity = reason

        # 6. Extract user instruction
        instruction = extract_user_instruction(cwd, agent_type, session_data)
        session.instruction = instruction
        session.user_instruction = instruction.text
        session.source_file = instruction.source_file or (session_data or {}).get("source_file", "")
        session.confidence = instruction.confidence

        # 7. Collect active commands and child processes
        session.active_commands = _collect_active_commands(root)
        session.child_processes = root.children

        # 8. Resource metrics
        session.cpu_percent = root.cpu_percent
        session.memory_percent = root.memory_percent

        # 9. Project runtime status
        if cwd:
            session.project_status = get_project_runtime_status(cwd, recent_files)
            session.git_status = "dirty" if session.project_status.has_uncommitted else "clean"
            if session.project_status.branch and not session.project_name.git_branch:
                session.project_name.git_branch = session.project_status.branch
        session.recent_files = recent_files[:20]

        # 11. Build timeline
        timeline: list[ActivityTimelineItem] = []
        if session.heartbeat_ts:
            timeline.append(ActivityTimelineItem(
                ts=session.heartbeat_ts,
                event="heartbeat",
                detail=session.recent_output[:120] if session.recent_output else "",
            ))
        for child in root.children:
            if child.cmdline:
                timeline.append(ActivityTimelineItem(
                    ts=child.create_time,
                    event="child_process",
                    detail=" ".join(child.cmdline[:3])[:120],
                ))
        timeline.sort(key=lambda x: x.ts, reverse=True)
        session.timeline = timeline[:10]

        # 12. Recent logs (last few lines from log files)
        if cwd:
            log_files = _candidate_log_files(cwd)
            if log_files:
                try:
                    content = log_files[0].read_text(encoding="utf-8", errors="ignore")
                    lines = content.strip().split("\n")
                    session.recent_logs = lines[-10:]
                except Exception:
                    pass

        enriched.append(session)

    return enriched


def get_process_cpu_mem(pid: int) -> tuple[float, float]:
    """Get CPU% and MEM% for a process. Returns (0.0, 0.0) if dead."""
    try:
        proc = psutil.Process(pid)
        return proc.cpu_percent(interval=0.1), proc.memory_percent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0, 0.0


def _read_proc_io(pid: int) -> tuple[float, float]:
    """Read /proc/<pid>/io for read_bytes/write_bytes. Returns (0.0, 0.0) on failure."""
    try:
        io_path = f"/proc/{pid}/io"
        if not os.path.exists(io_path):
            return 0.0, 0.0
        with open(io_path) as f:
            read_bytes = 0.0
            write_bytes = 0.0
            for line in f:
                if line.startswith("read_bytes:"):
                    read_bytes = float(line.split(":")[1].strip())
                elif line.startswith("write_bytes:"):
                    write_bytes = float(line.split(":")[1].strip())
            return read_bytes, write_bytes
    except (PermissionError, FileNotFoundError, OSError, ValueError):
        return 0.0, 0.0


def _count_children(pid: int) -> int:
    """Count all descendant processes recursively."""
    try:
        proc = psutil.Process(pid)
        return len(proc.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0


def _count_open_files(pid: int) -> int:
    """Count open file descriptors for a process."""
    try:
        proc = psutil.Process(pid)
        return len(proc.open_files())
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return 0


def get_resource_metrics(pid: int) -> Optional[ResourceMetrics]:
    """Collect full resource metrics for a process."""
    try:
        proc = psutil.Process(pid)
        cpu = proc.cpu_percent(interval=0)
        mem_pct = proc.memory_percent()
        mem_info = proc.memory_info()
        child_count = _count_children(pid)
        open_files = _count_open_files(pid)
        read_bytes, write_bytes = _read_proc_io(pid)

        return ResourceMetrics(
            cpu_percent=cpu,
            memory_percent=mem_pct,
            rss_mb=mem_info.rss / (1024 * 1024),
            vms_mb=mem_info.vms / (1024 * 1024),
            child_count=child_count,
            open_files=open_files,
            read_bytes=read_bytes,
            write_bytes=write_bytes,
            status=proc.status(),
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


# ---- Ring buffer for CPU/MEM history (last 60 seconds) ----

_history: dict[int, collections.deque[CpuMemSample]] = {}
_HISTORY_MAX_SECONDS = 65  # keep slightly more than 60s


def record_sample(pid: int) -> None:
    """Record a CPU/MEM sample for a PID. Call this periodically (every ~2s)."""
    try:
        proc = psutil.Process(pid)
        cpu = proc.cpu_percent(interval=0)
        mem = proc.memory_percent()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    sample = CpuMemSample(ts=time.time(), cpu=cpu, mem=mem)
    if pid not in _history:
        _history[pid] = collections.deque(maxlen=35)  # 35 samples × 2s ≈ 70s
    _history[pid].append(sample)


def get_history(pid: int) -> list[CpuMemSample]:
    """Get CPU/MEM history for a PID (last ~60 seconds)."""
    if pid not in _history:
        return []
    cutoff = time.time() - _HISTORY_MAX_SECONDS
    return [s for s in _history[pid] if s.ts >= cutoff]


def cleanup_history(active_pids: set[int]) -> None:
    """Remove history entries for PIDs that are no longer active."""
    dead = set(_history.keys()) - active_pids
    for pid in dead:
        del _history[pid]


# ---- System-wide metrics ----

_prev_net = None
_prev_net_time = 0.0


def _disk_identity(path: str) -> tuple[str, str]:
    """Return a stable de-duplication key and display mount point for a path."""
    try:
        resolved = os.path.realpath(path)
        partitions = sorted(
            psutil.disk_partitions(all=False),
            key=lambda p: len(p.mountpoint),
            reverse=True,
        )
        for part in partitions:
            mount = os.path.realpath(part.mountpoint)
            try:
                if os.path.commonpath([resolved, mount]) == mount:
                    return part.device or mount, part.mountpoint
            except ValueError:
                continue
    except OSError:
        pass
    return os.path.realpath(path), path


def get_system_metrics(project_dirs: list[str] | None = None) -> SystemMetrics:
    """Collect system-wide resource metrics."""
    global _prev_net, _prev_net_time

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0)

    # Memory
    mem = psutil.virtual_memory()

    # Disk usage for project directories
    disk_usages = []
    seen_mounts: set[str] = set()
    if project_dirs:
        for d in project_dirs:
            try:
                usage = psutil.disk_usage(d)
                disk_key, mount = _disk_identity(d)
                if disk_key not in seen_mounts:
                    seen_mounts.add(disk_key)
                    disk_usages.append({
                        "path": mount,
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_gb": round(usage.used / (1024**3), 1),
                        "percent": usage.percent,
                    })
            except (OSError, FileNotFoundError):
                continue

    # Network: calculate rx/tx per second
    net_interfaces = []
    try:
        counters = psutil.net_io_counters(pernic=True)
        now = time.time()
        elapsed = now - _prev_net_time if _prev_net_time > 0 else 0

        for iface, stats in counters.items():
            if iface == "lo":
                continue
            rx_mbps = 0.0
            tx_mbps = 0.0
            if _prev_net and iface in _prev_net and elapsed > 0:
                rx_mbps = (stats.bytes_recv - _prev_net[iface].bytes_recv) / elapsed / (1024 * 1024)
                tx_mbps = (stats.bytes_sent - _prev_net[iface].bytes_sent) / elapsed / (1024 * 1024)
            net_interfaces.append({
                "name": iface,
                "rx_mbps": round(rx_mbps, 2),
                "tx_mbps": round(tx_mbps, 2),
            })

        _prev_net = counters
        _prev_net_time = now
    except Exception:
        pass

    return SystemMetrics(
        cpu_percent=cpu_percent,
        mem_total_gb=round(mem.total / (1024**3), 1),
        mem_used_gb=round(mem.used / (1024**3), 1),
        mem_percent=mem.percent,
        disk_usages=disk_usages,
        net_interfaces=net_interfaces,
    )
