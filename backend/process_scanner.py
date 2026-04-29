from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import psutil

from backend.config import get_log_dir
from backend.log_manager import get_log_tail
from backend.models import (
    ActivityTimelineItem,
    CpuMemSample,
    DiscoveredSession,
    InstructionInfo,
    ProcessInfo,
    ProjectNameInfo,
    ProjectRuntimeStatus,
    ResourceMetrics,
    SystemMetrics,
    TaskStatus,
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


ROOT_AGENT_PATTERNS = ("codex", "kimi-code", "kimi", "claude-code", "claude", "aider", "gemini")
WAITING_RE = re.compile(
    r"(waiting for input|approve\?|continue\?|confirm|permission|please provide|let me know|"
    r"which .+\?|需要确认|是否继续|请确认|y/n)",
    re.I,
)
ERROR_RE = re.compile(r"(Traceback|ERROR|Exception|command not found|permission denied|quota exceeded|API error|rate limit|认证失败)", re.I)
INSTRUCTION_LABEL_RE = re.compile(r"^\s*(?:User|Human|Prompt|Task|Instruction|用户|用户指令|目标)\s*[:：]\s*(.+)\s*$", re.I)


def _cmd_text(info: ProcessInfo) -> str:
    return " ".join(info.cmdline).strip() or info.name


def _detect_agent_type_from_text(text: str) -> str:
    low = text.lower()
    if "kimi-code" in low or "kimi" in low:
        return "kimi-code"
    if "claude-code" in low or "claude" in low:
        return "claude"
    for kw in ("codex", "aider", "gemini"):
        if kw in low:
            return kw
    return "unknown"


def _detect_agent_type(info: ProcessInfo) -> str:
    return _detect_agent_type_from_text(f"{info.name} {_cmd_text(info)}")


def _is_root_agent_proc(proc: psutil.Process) -> bool:
    try:
        text = f"{proc.name()} {' '.join(proc.cmdline())}"
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    return _detect_agent_type_from_text(text) != "unknown"


def _flatten_processes(root: ProcessInfo) -> list[ProcessInfo]:
    result: list[ProcessInfo] = []
    def walk(p: ProcessInfo) -> None:
        result.append(p)
        for child in p.children:
            walk(child)
    walk(root)
    return result


def _short_command(command: str, max_len: int = 96) -> str:
    command = " ".join(command.split())
    return command if len(command) <= max_len else command[: max_len - 3] + "..."


def _git_root(cwd: str) -> str:
    if not cwd or cwd == "unknown":
        return cwd
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return cwd


def _short_path(path: str) -> str:
    home = str(Path.home())
    if path.startswith(home + os.sep):
        return "~" + path[len(home):]
    marker = f"{os.sep}projects{os.sep}"
    if marker in path:
        first = path.split(marker, 1)[1].split(os.sep, 1)[0]
        return f".../projects/{first}"
    parts = Path(path).parts
    return os.path.join("...", *parts[-3:]) if len(parts) > 4 else path


def derive_project_name(cwd: str) -> ProjectNameInfo:
    if not cwd or cwd == "unknown":
        return ProjectNameInfo(display_name="unknown", project_dir=cwd or "", short_cwd="unknown")
    project_dir = _git_root(cwd)
    marker = f"{os.sep}projects{os.sep}"
    if marker in project_dir:
        head, tail = project_dir.split(marker, 1)
        project_dir = f"{head}{marker}{tail.split(os.sep, 1)[0]}"
    display = Path(project_dir).name or project_dir
    base, workspace = display, ""
    match = re.match(r"^\d+\.(?P<project>.+)_(?P<workspace>[A-Za-z0-9-]+)$", display)
    if match:
        base, workspace = match.group("project"), match.group("workspace")
    return ProjectNameInfo(display_name=display, base_project=base, workspace=workspace, project_dir=project_dir, short_cwd=_short_path(project_dir))


def _run_git(project_dir: str, args: list[str]) -> str:
    try:
        result = subprocess.run(["git"] + args, cwd=project_dir, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _git_changed_files(project_dir: str) -> list[str]:
    changed: set[str] = set()
    for line in _run_git(project_dir, ["status", "--short"]).splitlines():
        if len(line) > 2:
            name = line[2:].strip()
            changed.add(name.split(" -> ", 1)[-1])
    changed.update(line.strip() for line in _run_git(project_dir, ["diff", "--name-only"]).splitlines() if line.strip())
    return sorted(changed)


def _recent_modified_files(project_dir: str, limit: int = 10) -> list[str]:
    root = Path(project_dir)
    if not root.is_dir():
        return []
    ignored = {".git", "node_modules", "__pycache__", ".venv", "logs", ".pytest_cache", "dist", "build"}
    found: list[tuple[float, str]] = []
    scanned = 0
    try:
        for path in root.rglob("*"):
            scanned += 1
            if scanned > 5000:
                break
            if not path.is_file() or any(part in ignored for part in path.parts):
                continue
            st = path.stat()
            found.append((st.st_mtime, str(path.relative_to(root))))
    except OSError:
        return []
    found.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in found[:limit]]


def _is_sensitive_log_candidate(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & {"credentials", "credential", "secrets", "secret", "tokens", "token", "auth"}:
        return True
    name = path.name.lower()
    return any(x in name for x in ("credential", "token", "secret", "auth", "models_cache", "config"))


def _candidate_log_files(project_dir: str, agent_type: str) -> list[Path]:
    project = Path(project_dir) if project_dir and project_dir != "unknown" else None
    home = Path.home()
    bases: list[Path] = []
    if project:
        bases += [project / ".codex", project / ".claude", project / ".kimi", project / ".kimi-code", project / ".agent", project / ".agent_foreman", project / "logs", project / "AGENT_LOG.md", project / "progress.md"]
    bases += [home / ".codex" / "sessions", home / ".codex" / "logs", home / ".codex" / "log", home / ".codex" / "history.jsonl", home / ".claude" / "projects", home / ".claude" / "logs", home / ".kimi" / "logs", home / ".kimi" / "user-history", home / ".kimi-code" / "logs", home / ".kimi-code" / "user-history", get_log_dir()]
    suffixes = {".log", ".jsonl", ".json", ".md", ".txt"}
    candidates: list[Path] = []
    for base in bases:
        try:
            if _is_sensitive_log_candidate(base):
                continue
            if base.is_file() and base.suffix.lower() in suffixes:
                candidates.append(base)
            elif base.is_dir():
                for path in base.rglob("*"):
                    if len(candidates) >= 80:
                        break
                    if path.is_file() and path.suffix.lower() in suffixes and not _is_sensitive_log_candidate(path):
                        candidates.append(path)
        except OSError:
            continue
    with_mtime = []
    for path in candidates:
        try:
            with_mtime.append((path.stat().st_mtime, path))
        except OSError:
            pass
    with_mtime.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in with_mtime[:40]]


def _read_tail_text(path: Path, max_bytes: int = 262_144) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            return f.read(max_bytes).decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_instruction_from_text(text: str, source: Path, mtime: float) -> list[InstructionInfo]:
    items: list[InstructionInfo] = []
    for raw in text.splitlines():
        line = raw.strip()
        parsed = None
        if line.startswith("{") and '"role"' in line:
            try:
                obj = json.loads(line)
                if str(obj.get("role", "")).lower() == "user":
                    content = obj.get("content")
                    parsed = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        if parsed is None:
            match = INSTRUCTION_LABEL_RE.match(line)
            if match:
                parsed = match.group(1).strip()
        if parsed:
            items.append(InstructionInfo(text=parsed[:2000], source_file=str(source), source_type="agent transcript", timestamp=datetime.fromtimestamp(mtime), confidence=0.8))
    return items


def extract_user_instruction(session: DiscoveredSession) -> InstructionInfo:
    candidates: list[InstructionInfo] = []
    for path in _candidate_log_files(session.project.project_dir or session.cwd, session.agent_type):
        try:
            candidates += _extract_instruction_from_text(_read_tail_text(path), path, path.stat().st_mtime)
        except OSError:
            continue
        if len(candidates) >= 20:
            break
    candidates.sort(key=lambda c: c.timestamp or datetime.min, reverse=True)
    session.instruction_candidates = candidates[:5]
    return candidates[0] if candidates else InstructionInfo()


def _collect_active_commands(processes: list[ProcessInfo], root_pid: int) -> list[str]:
    active = []
    needles = ("pytest", "npm", "pnpm", "yarn", "git", "python", "rscript", "bash", "node", "rg", "grep", "find", "fd", "uv")
    for proc in processes:
        if proc.pid == root_pid:
            continue
        text = _cmd_text(proc)
        if any(n in text.lower() for n in needles):
            active.append(text)
    return active[:8]


def get_project_runtime_status(project_dir: str, processes: list[ProcessInfo], recent_logs: list[str]) -> ProjectRuntimeStatus:
    changed = _git_changed_files(project_dir) if project_dir and Path(project_dir).is_dir() else []
    branch = _run_git(project_dir, ["branch", "--show-current"]) if project_dir and Path(project_dir).is_dir() else ""
    recent = _recent_modified_files(project_dir)
    tests, servers = [], []
    for proc in processes:
        cmd = _cmd_text(proc)
        low = cmd.lower()
        if "pytest" in low or "npm test" in low or "pnpm test" in low or "yarn test" in low:
            tests.append(_short_command(cmd))
        if any(x in low for x in ("vite", "uvicorn", "streamlit", "jupyter", "rstudio-server")):
            servers.append(_short_command(cmd))
    errors = [line[-300:] for line in recent_logs if ERROR_RE.search(line)][-5:]
    last = None
    if recent:
        try:
            last = datetime.fromtimestamp((Path(project_dir) / recent[0]).stat().st_mtime)
        except OSError:
            pass
    return ProjectRuntimeStatus(git_branch=branch, git_dirty_files_count=len(changed), git_changed_files=changed[:30], recent_modified_files=recent, test_processes=tests[:5], server_processes=servers[:5], error_hints=errors, last_activity_time=last)


def infer_session_activity(
    processes: list[ProcessInfo],
    project_status: ProjectRuntimeStatus,
    recent_logs: list[str],
    root_pid: int,
    heartbeat_ts: float | None = None,
    recent_output: str = "",
) -> tuple[TaskStatus, str, str]:
    active = _collect_active_commands(processes, root_pid)
    blob = "\n".join(active).lower()
    log_blob = "\n".join(recent_logs[-30:] + ([recent_output] if recent_output else []))
    if WAITING_RE.search(log_blob):
        return TaskStatus.waiting_input, "waiting prompt detected in output", "Possibly waiting for user input"
    if "pytest" in blob:
        return TaskStatus.testing, "pytest child process detected", f"Running tests: {_short_command(active[0])}"
    if any(x in blob for x in ("npm test", "pnpm test", "yarn test")):
        return TaskStatus.testing, "frontend test child process detected", "Running frontend tests"
    if "git" in blob:
        return TaskStatus.git_ops, "git child process detected", f"Inspecting or modifying git state: {_short_command(active[0])}"
    if any(x in blob for x in ("rg", "grep", "find", "fd")):
        return TaskStatus.searching, "search child process detected", "Searching codebase"
    if any(x in blob for x in ("python", "rscript", "bash", "node", "uv")):
        return TaskStatus.running_script, "script child process detected", f"Running script: {_short_command(active[0])}"
    if project_status.last_activity_time and datetime.now() - project_status.last_activity_time <= timedelta(seconds=60):
        return TaskStatus.editing, "project file modified within 60s", "Editing files: " + ", ".join(project_status.recent_modified_files[:3])
    cpu = sum(p.cpu_percent for p in processes)
    if heartbeat_ts and time.time() - heartbeat_ts <= 60:
        return TaskStatus.busy, "heartbeat updated within 60s", "Agent is active"
    if cpu > 3:
        return TaskStatus.busy, "CPU above 3%", "Agent is active"
    return TaskStatus.idle, "no CPU/child/file activity detected", "No recent activity; possibly waiting or idle"


def discover_agent_processes() -> list[ProcessInfo]:
    """Scan all running processes and find coding agent root processes."""
    results = []
    seen_pids: set[int] = set()

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            if not _is_root_agent_proc(proc):
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


def scan_agent_sessions() -> list[DiscoveredSession]:
    roots = discover_agent_processes()
    sessions: list[DiscoveredSession] = []
    for root in roots:
        cwd = root.cwd or "unknown"
        project = derive_project_name(cwd)
        processes = _flatten_processes(root)
        h = hashlib.md5(f"{project.project_dir}:{root.pid}:{root.create_time}".encode()).hexdigest()[:10]
        session = DiscoveredSession(
            session_id=f"agent-{h}",
            cwd=cwd,
            root_process=root,
            all_pids=sorted({p.pid for p in processes}),
            agent_type=_detect_agent_type(root),
            root_pid=root.pid,
            root_cmd=_cmd_text(root),
            user=root.user,
            project_name=project.display_name,
            project=project,
            short_cwd=project.short_cwd,
            started_at=datetime.fromtimestamp(root.create_time) if root.create_time else None,
            elapsed=root.elapsed,
            child_processes=[p for p in processes if p.pid != root.pid],
            active_commands=_collect_active_commands(processes, root.pid),
            cpu_percent=sum(p.cpu_percent for p in processes),
            memory_percent=sum(p.memory_percent for p in processes),
            confidence=0.9,
        )
        session.log_candidates = [str(p) for p in _candidate_log_files(project.project_dir or cwd, session.agent_type)[:8]]
        for log_path in session.log_candidates[:3]:
            session.recent_logs.extend(get_log_tail(Path(log_path), lines=20))
        session.recent_logs = session.recent_logs[-60:]
        session.project_status = get_project_runtime_status(project.project_dir or cwd, processes, session.recent_logs)
        session.git_status = {"branch": session.project_status.git_branch, "dirty_files": session.project_status.git_dirty_files_count, "changed_files": session.project_status.git_changed_files}
        session.recent_changed_files = session.project_status.recent_modified_files
        session.error_hints = session.project_status.error_hints
        status, reason, activity = infer_session_activity(processes, session.project_status, session.recent_logs, root.pid)
        session.status, session.status_reason, session.current_activity = status, reason, activity
        instruction = extract_user_instruction(session)
        session.instruction = instruction
        session.user_instruction = instruction.text
        session.instruction_source = instruction.source_file
        session.timeline = [ActivityTimelineItem(timestamp=session.started_at or datetime.now(), label=f"started {session.agent_type}", source="process")]
        if session.project_status.last_activity_time:
            session.timeline.append(ActivityTimelineItem(timestamp=session.project_status.last_activity_time, label=session.current_activity, source="project"))
        sessions.append(session)
    sessions.sort(key=lambda s: (s.project_name.lower(), s.root_pid))
    return sessions


def discover_sessions() -> list[DiscoveredSession]:
    return scan_agent_sessions()


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
