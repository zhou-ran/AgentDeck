from __future__ import annotations

import collections
import hashlib
import os
import time
from typing import Optional

import psutil

from backend.config import AGENT_KEYWORDS
from backend.models import CpuMemSample, DiscoveredSession, ProcessInfo, ResourceMetrics, SystemMetrics


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


def discover_agent_processes() -> list[ProcessInfo]:
    """Scan all running processes and find ones matching agent keywords."""
    results = []
    seen_pids: set[int] = set()

    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmdline_list = proc.info.get("cmdline") or []
            name = proc.info.get("name") or ""
            cmdline_str = " ".join(cmdline_list).lower()
            name_lower = name.lower()

            is_agent = False
            for kw in AGENT_KEYWORDS:
                if kw in name_lower or kw in cmdline_str:
                    is_agent = True
                    break

            if not is_agent:
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
    name_lower = info.name.lower()
    cmdline_lower = " ".join(info.cmdline).lower()
    for kw in ("codex", "claude", "aider", "gemini"):
        if kw in name_lower or kw in cmdline_lower:
            return kw
    for kw in ("pytest", "Rscript", "cargo", "go"):
        if kw in name_lower or kw in cmdline_lower:
            return kw
    # Generic runners
    for kw in ("node", "python", "python3", "uv", "npm", "pnpm", "bun"):
        if kw in name_lower or kw in cmdline_lower:
            return kw
    return "unknown"


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
                mount = d
                if mount not in seen_mounts:
                    seen_mounts.add(mount)
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
