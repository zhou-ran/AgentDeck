from __future__ import annotations

import collections
import getpass
import hashlib
import os
import re
import time
from pathlib import Path

import psutil

from backend.git_utils import (
    get_changed_files,
    get_git_branch,
    get_git_root,
    get_git_status_short,
)
from backend.log_manager import redact_sensitive_text
from backend.models import (
    ActivityTimelineItem,
    AgentDetectionResult,
    BackgroundJob,
    ConversationMessage,
    CpuMemSample,
    DiscoveredSession,
    ForegroundAgentInfo,
    GitStatus,
    InstructionInfo,
    ProcessInfo,
    ProjectNameInfo,
    ProjectRuntimeStatus,
    ResourceMetrics,
    ResourceUsage,
    RuntimeTypeResult,
    SystemMetrics,
)
from backend.notifications import get_dispatcher
from backend.session_sources import discover_all_sessions
from backend.session_sources.base import RawSession
from backend.rules import matching_rules

# ---- Root agent patterns for detecting top-level agents ----
ROOT_AGENT_PATTERNS = [
    re.compile(r"codex\b", re.I),
    re.compile(r"claude[-_ ]?code\b", re.I),
    re.compile(r"claude\b", re.I),
    re.compile(r"kimi[-_ ]?code\b", re.I),
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

STALE_INACTIVE_SECONDS = 2 * 60 * 60
AUTO_HIDE_INACTIVE_SECONDS = 6 * 60 * 60


def _current_server_user() -> str:
    """Return the OS user running AgentDeck.

    psutil may report usernames as either "user" or "domain\\user" depending on
    platform, so comparisons should go through _same_user().
    """
    return getpass.getuser()


def _same_user(process_user: str, server_user: str) -> bool:
    if not process_user or not server_user:
        return True
    process_short = process_user.replace("\\", "/").split("/")[-1]
    server_short = server_user.replace("\\", "/").split("/")[-1]
    return process_user == server_user or process_short == server_short


def _auto_ignore_reason(
    session: DiscoveredSession,
    *,
    server_user: str,
    recent_files: list[str],
) -> str:
    """Return a reason when a discovered session should be hidden by policy."""
    if not _same_user(session.user, server_user):
        return f"other user: {session.user or 'unknown'}"

    protected = (
        session.is_pinned
        or session.status in {"needs_input", "waiting", "waiting_input", "error_hint", "failed"}
        or bool(session.error_hints)
        or bool(session.background_jobs)
        or bool(session.child_processes)
        or bool(session.active_commands)
        or bool(recent_files)
    )
    if protected:
        return ""

    inactive_age = session.heartbeat_age_sec
    if inactive_age is None and session.elapsed_sec:
        inactive_age = float(session.elapsed_sec)

    if inactive_age is None or inactive_age <= AUTO_HIDE_INACTIVE_SECONDS:
        return ""

    no_recent_work = (
        session.cpu_percent < 1
        and session.memory_percent < 20
    )
    if no_recent_work:
        return "no visible activity for more than 6 hours"

    return ""


def _format_elapsed(start_time: float) -> str:
    secs = int(time.time() - start_time)
    if secs < 60:
        return f"{secs}s"
    mins, s = divmod(secs, 60)
    if mins < 60:
        return f"{mins}m{s}s"
    hours, m = divmod(mins, 60)
    return f"{hours}h{m}m"


def _proc_to_info(proc: psutil.Process, include_children: bool = True) -> ProcessInfo | None:
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

    try:
        tty = proc.terminal()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        tty = None

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
        tty=tty,
        status=info["status"] or "",
        cpu_percent=info["cpu_percent"] or 0.0,
        memory_percent=info["memory_percent"] or 0.0,
        create_time=info["create_time"] or 0.0,
        elapsed=_format_elapsed(info["create_time"] or time.time()),
        children=children,
    )


def get_process_tree(pid: int) -> ProcessInfo | None:
    """Get full process tree rooted at pid."""
    try:
        proc = psutil.Process(pid)
        return _proc_to_info(proc, include_children=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_process_info(pid: int) -> ProcessInfo | None:
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
        ("claude-code", re.compile(r"claude[-_ ]?code\b", re.I)),
        ("kimi-code", re.compile(r"kimi[-_ ]?code\b", re.I)),
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
    except AttributeError:
        info = getattr(proc, "info", {}) or {}
        return " ".join([info.get("name", ""), *(info.get("cmdline") or [])])
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


def _score_agent_candidate(text: str, source: str, high_confidence: bool = True) -> AgentDetectionResult:
    agent = _agent_type_from_text(text) or "unknown"
    if agent == "unknown":
        return AgentDetectionResult(agent_type="unknown", confidence=0.0, reason="no agent marker found")
    confidence = 0.95 if high_confidence else 0.65
    return AgentDetectionResult(
        agent_type=agent,
        confidence=confidence,
        reason=f"matched {source}",
        evidence=[f"{source}: {text[:180]}"],
    )


def _source_agent_from_path(path: str) -> str:
    lower = path.lower()
    if "/.codex" in lower:
        return "codex"
    if "/.kimi-code" in lower or "/.kimi/" in lower or "/.kimi" in lower:
        return "kimi-code"
    if "/.claude" in lower:
        return "claude-code"
    return ""


def _detect_parent_agent(ppid: int) -> AgentDetectionResult:
    try:
        parent = psutil.Process(ppid)
        while parent:
            text = _proc_text(parent)
            result = _score_agent_candidate(text, "parent process")
            if result.agent_type != "unknown":
                return result
            parent = parent.parent()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    return AgentDetectionResult(agent_type="unknown", confidence=0.0, reason="no parent agent evidence")


def _detect_agent_from_log_file(path: str) -> AgentDetectionResult:
    try:
        sample = Path(path).read_text(encoding="utf-8", errors="ignore")[-12000:]
    except Exception:
        return AgentDetectionResult(agent_type="unknown", confidence=0.0, reason="log unavailable")

    checks = (
        ("codex", re.compile(r"\bCodex CLI\b|\bcodex\b", re.I)),
        ("kimi-code", re.compile(r"\bkimi[-_ ]?code\b|\bKimi\b")),
        ("claude-code", re.compile(r"\bclaude[-_ ]?code\b|\bClaude\b")),
    )
    for agent, pattern in checks:
        match = pattern.search(sample)
        if match:
            return AgentDetectionResult(
                agent_type=agent,
                confidence=0.85,
                reason="matched session/log content",
                evidence=[f"matched log content in {path}: {match.group(0)}"],
            )
    return AgentDetectionResult(agent_type="unknown", confidence=0.0, reason="no log marker found")


def detect_agent_type(
    process: ProcessInfo,
    session_files: list[str] | None = None,
    cwd: str = "",
) -> AgentDetectionResult:
    """Detect agent type from high-confidence process and session-source evidence.

    This avoids project names, usernames, and process environments.
    """
    cmd_text = " ".join([process.name, *process.cmdline])
    basename_text = " ".join(
        [_cmd_basename(process.name), *[_cmd_basename(part) for part in process.cmdline[:2]]]
    )

    result = _score_agent_candidate(basename_text, "executable basename")
    if result.agent_type != "unknown":
        return result

    result = _score_agent_candidate(cmd_text, "process cmd")
    if result.agent_type != "unknown":
        return result

    if (
        (_cmd_basename(process.name) == "node" or (process.cmdline and _cmd_basename(process.cmdline[0]) == "node"))
        and psutil.pid_exists(process.pid)
    ):
        result = _detect_parent_agent(process.ppid)
        if result.agent_type != "unknown":
            return result

    evidence: list[str] = []
    for path in session_files or []:
        agent = _source_agent_from_path(path)
        if agent:
            return AgentDetectionResult(
                agent_type=agent,
                confidence=0.9,
                reason="matched session source dir",
                evidence=[f"session source: {path}"],
            )
        result = _detect_agent_from_log_file(path)
        if result.agent_type != "unknown":
            return result
        evidence.append(f"session file checked: {path}")

    for root in [cwd, get_git_root(cwd) or ""]:
        if not root:
            continue
        for dirname, agent in (
            (".codex", "codex"),
            (".kimi-code", "kimi-code"),
            (".kimi", "kimi-code"),
            (".claude", "claude-code"),
        ):
            marker = os.path.join(root, dirname)
            if os.path.isdir(marker):
                return AgentDetectionResult(
                    agent_type=agent,
                    confidence=0.75,
                    reason="matched project hidden agent dir",
                    evidence=[f"project source dir: {marker}"],
                )

    return AgentDetectionResult(
        agent_type="unknown",
        confidence=0.0,
        reason="no high-confidence agent evidence",
        evidence=evidence,
    )


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
    return detect_agent_type(info, [], info.cwd).agent_type


def _detect_agent_type_from_text(text: str) -> str:
    """Detect agent type from arbitrary text (cmdline, session file content)."""
    text_lower = text.lower()
    for agent_type, pattern in (
        ("claude-code", re.compile(r"claude[-_ ]?code\b", re.I)),
        ("kimi-code", re.compile(r"kimi[-_ ]?code\b", re.I)),
        ("codex", re.compile(r"codex\b", re.I)),
        ("claude", re.compile(r"claude\b", re.I)),
        ("kimi", re.compile(r"kimi\b", re.I)),
        ("aider", re.compile(r"aider\b", re.I)),
        ("gemini", re.compile(r"gemini\b", re.I)),
    ):
        if pattern.search(text_lower):
            return agent_type
    return ""


def _git_root(cwd: str) -> str | None:
    """Find the git root directory for a given cwd."""
    if not cwd or not os.path.isdir(cwd):
        return None
    return get_git_root(cwd)


def derive_project_name(cwd: str) -> ProjectNameInfo:
    """Derive a human-readable project name from the cwd.

    Avoids leaking the OS username when the cwd is the user's home directory
    (e.g. `~` becomes "(no project · ~)" instead of the username). For paths
    inside home but outside any git repo, also collapses the home prefix to `~`.
    """
    if not cwd:
        return ProjectNameInfo(name="unknown", short_cwd="unknown")

    git_root = _git_root(cwd)
    git_branch = get_git_branch(git_root) if git_root else None

    home = str(Path.home())
    home_real = os.path.realpath(home)
    cwd_real = os.path.realpath(cwd)

    # Collapse home prefix so we never expose the OS username on the dashboard
    # ("/Users/wanghao206/foo" -> "~/foo").
    def _tildeify(p: str) -> str:
        try:
            real = os.path.realpath(p)
        except OSError:
            real = p
        if real == home_real:
            return "~"
        if real.startswith(home_real + os.sep):
            return "~/" + real[len(home_real) + 1:]
        return p

    if git_root:
        name = os.path.basename(git_root.rstrip("/")) or "unknown"
    elif cwd_real == home_real or cwd_real == "/":
        # Don't use basename(home) — that would surface the username.
        name = "(no project · ~)" if cwd_real == home_real else "(no project · /)"
    else:
        # cwd basename is fine for non-home, non-root paths.
        name = os.path.basename(cwd.rstrip("/")) or "unknown"

    short_cwd = _tildeify(cwd)
    if len(short_cwd) > 60 and "/" in short_cwd:
        parts = short_cwd.split("/")
        if len(parts) > 3:
            short_cwd = ".../" + "/".join(parts[-3:])

    return ProjectNameInfo(
        name=name,
        short_cwd=short_cwd or cwd,
        git_root=_tildeify(git_root) if git_root else None,
        git_branch=git_branch,
    )


def derive_project_key(cwd: str, git_root: str | None = None) -> str:
    base = git_root or _git_root(cwd) or cwd or "unknown"
    normalized = os.path.normcase(os.path.realpath(os.path.expanduser(base)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _agent_display(agent_type: str) -> str:
    labels = {
        "codex": "Codex",
        "kimi-code": "Kimi Code",
        "kimi": "Kimi",
        "claude-code": "Claude Code",
        "claude": "Claude",
        "aider": "Aider",
        "gemini": "Gemini",
        "unknown": "Unknown",
    }
    return labels.get(agent_type, agent_type or "Unknown")


def make_display_name(session_title: str | None, project_name: str, agent_type: str) -> str:
    if session_title:
        return session_title
    return f"{project_name or 'unknown'} · {_agent_display(agent_type)}"


# Directories that are NEVER project roots — skip them entirely so we don't
# os.walk() into the user's whole home / system on every discover() call.
_NON_PROJECT_DIRS = {
    "/",
    "",
    str(Path.home()),
    "/Applications",
    "/System",
    "/Library",
    "/usr",
    "/private",
    "/tmp",
    "/var",
    "/opt",
}

_RECENT_FILES_SKIP_DIRS = frozenset({
    "node_modules", "__pycache__", "venv", ".venv", "env", ".env",
    "dist", "build", "target", "out",
    ".git", ".hg", ".svn",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    "Library", "Caches", ".Trash", ".cache", ".npm", ".cursor",
    "logs", "log",
})

_RECENT_FILES_MAX_DEPTH = 4
_RECENT_FILES_MAX_VISITED = 5_000
_RECENT_FILES_TIME_BUDGET_SEC = 0.75


def _is_desktop_app_cwd(cwd: str | None) -> bool:
    """Detect macOS desktop apps masquerading as agent processes.

    Things like /Applications/Gemini.app and /Applications/Codex.app run with
    cwd `/` and match our agent name regex but are not coding sessions.
    """
    if not cwd:
        return False
    if cwd == "/":
        return True
    if cwd.startswith("/Applications/") or cwd.startswith("/System/"):
        return True
    return False


def _recent_modified_files(cwd: str, seconds: int = 60) -> list[str]:
    """Find files modified in the last N seconds under cwd.

    Hard-capped on every axis (depth, file count, wall-clock) so a careless
    cwd like `~` or `/` cannot freeze the discover endpoint.
    Returns an empty list for known non-project roots (home, /, /Applications…).
    """
    if not cwd or not os.path.isdir(cwd):
        return []
    if os.path.realpath(cwd) in {os.path.realpath(p) for p in _NON_PROJECT_DIRS if p}:
        return []

    cutoff = time.time() - seconds
    deadline = time.time() + _RECENT_FILES_TIME_BUDGET_SEC
    base_depth = cwd.rstrip(os.sep).count(os.sep)
    visited = 0
    modified: list[str] = []

    try:
        for root, dirs, files in os.walk(cwd, followlinks=False):
            if time.time() > deadline or visited > _RECENT_FILES_MAX_VISITED:
                break
            depth = root.rstrip(os.sep).count(os.sep) - base_depth
            if depth >= _RECENT_FILES_MAX_DEPTH:
                dirs[:] = []
            else:
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in _RECENT_FILES_SKIP_DIRS
                ]
            for f in files:
                visited += 1
                if visited > _RECENT_FILES_MAX_VISITED:
                    break
                fpath = os.path.join(root, f)
                try:
                    if os.path.getmtime(fpath) >= cutoff:
                        modified.append(os.path.relpath(fpath, cwd))
                        if len(modified) >= 20:
                            return modified
                except OSError:
                    continue
    except Exception:
        pass
    return modified[:20]


def _candidate_log_files(project_dir: str, include_global: bool = False) -> list[Path]:
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
    if include_global:
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
                    if f.is_file() and "subagents" not in f.parts:
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
    if session_data:
        return InstructionInfo(text="未找到原始指令", source="", source_file="", confidence=0.0)

    # 2. Project-local log files. Global agent_logs is intentionally not used
    # for discovered sessions because it is not tied to a process/session.
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


def _short_cmd(proc: ProcessInfo, limit: int = 120) -> str:
    text = " ".join(proc.cmdline) if proc.cmdline else proc.name
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _elapsed_seconds(proc: ProcessInfo) -> int | None:
    if not proc.create_time:
        return None
    return max(0, int(time.time() - proc.create_time))


def _classify_job(proc: ProcessInfo) -> str:
    cmd_lower = " ".join(proc.cmdline).lower() if proc.cmdline else proc.name.lower()
    name_lower = proc.name.lower()
    argv0 = _cmd_basename(proc.cmdline[0]) if proc.cmdline else name_lower

    if any(kw in cmd_lower for kw in ("pytest", "npm test", "pnpm test", "yarn test", "vitest", "jest")):
        return "test"
    if any(kw in cmd_lower for kw in (
        "npm run dev", "pnpm dev", "yarn dev", "vite", "uvicorn", "streamlit",
        "jupyter", "rstudio-server", "flask run", "fastapi", "next dev",
    )):
        return "dev_server"
    if any(kw in cmd_lower for kw in ("npm install", "pnpm install", "yarn install", "pip install", "uv pip", "conda install")):
        return "install"
    if argv0 == "git" or name_lower == "git":
        return "git"
    if argv0 in {"rg", "grep", "find", "fd", "ag"} or name_lower in {"rg", "grep", "find", "fd", "ag"}:
        return "search"
    if argv0 in {"python", "python3", "rscript", "bash", "sh", "node", "perl", "npm", "pnpm", "bun"}:
        return "script"
    return "unknown"


def build_background_jobs(root: ProcessInfo) -> list[BackgroundJob]:
    jobs: list[BackgroundJob] = []
    for child in _iter_process_tree(root):
        job_type = _classify_job(child)
        elapsed = _elapsed_seconds(child)
        jobs.append(BackgroundJob(
            pid=child.pid,
            ppid=child.ppid,
            cmd=_short_cmd(child),
            job_type=job_type,
            status=child.status,
            elapsed_sec=elapsed,
            cpu=child.cpu_percent,
            mem=child.memory_percent,
            cwd=child.cwd,
            summary=f"{job_type}: {_short_cmd(child, 80)}",
            is_long_running=bool(elapsed and elapsed > 900),
            detected_from="process_tree",
        ))
    return jobs


def build_foreground_info(
    root: ProcessInfo,
    recent_output: str,
    heartbeat_ts: float | None,
    status: str,
) -> ForegroundAgentInfo:
    waiting = bool(recent_output and WAITING_RE.search(recent_output))
    return ForegroundAgentInfo(
        pid=root.pid,
        cmd=_short_cmd(root, 180),
        tty=root.tty,
        is_interactive=bool(root.tty and root.tty != "?"),
        waiting_input=waiting,
        alive=True,
        last_activity_ts=heartbeat_ts,
        last_tool="",
        last_message_summary=(recent_output or "")[:180],
        status="waiting" if waiting else ("idle" if status in {"idle", "stale"} else "active"),
    )


def summarize_activity(status: str, reason: str, background_jobs: list[BackgroundJob], foreground: ForegroundAgentInfo) -> str:
    priority = ["test", "dev_server", "install", "git", "search", "script", "unknown"]
    labels = {
        "test": "正在跑测试",
        "dev_server": "后台服务运行中",
        "install": "正在安装依赖",
        "git": "正在执行 Git 操作",
        "search": "正在搜索代码库",
        "script": "正在运行脚本",
        "unknown": "后台任务运行中",
    }
    for kind in priority:
        job = next((item for item in background_jobs if item.job_type == kind), None)
        if job:
            return f"{labels[kind]}：{job.cmd}"
    if foreground.waiting_input:
        return "等待用户输入/授权"
    return reason


def status_group_for(status: str, ignored: bool = False) -> str:
    if ignored:
        return "ignored"
    if status in {"error_hint", "failed"}:
        return "error"
    if status in {"needs_input", "waiting", "waiting_input"}:
        return "needs_input"
    if status in {"idle", "stale", "unknown"}:
        return "idle"
    return "working"


def status_dot_for(status: str, group: str, has_error: bool = False) -> str:
    if has_error or group == "error":
        return "red"
    if group in {"needs_input", "idle"} or status in {"stale", "unknown"}:
        return "yellow"
    if group == "ignored":
        return "gray"
    if group == "working":
        return "green"
    return "gray"


def _build_git_status(project_status: ProjectRuntimeStatus, status_short: str, is_repo: bool) -> GitStatus:
    staged = unstaged = untracked = 0
    for line in status_short.splitlines():
        if line.startswith("??"):
            untracked += 1
            continue
        if len(line) >= 2:
            if line[0] != " ":
                staged += 1
            if line[1] != " ":
                unstaged += 1
    return GitStatus(
        branch=project_status.branch,
        dirty_count=len(project_status.dirty_files),
        changed_files=project_status.dirty_files[:20],
        staged_count=staged,
        unstaged_count=unstaged,
        untracked_count=untracked,
        is_repo=is_repo,
        command_failed=False,
    )


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


_RUNTIME_PATTERNS = [
    ("agent", "claude-code", re.compile(r"claude[-_ ]?code\b", re.I)),
    ("agent", "kimi-code", re.compile(r"kimi[-_ ]?code\b", re.I)),
    ("agent", "codex", re.compile(r"codex\b", re.I)),
    ("agent", "claude", re.compile(r"claude\b", re.I)),
    ("agent", "kimi", re.compile(r"kimi\b", re.I)),
    ("agent", "aider", re.compile(r"aider\b", re.I)),
    ("agent", "gemini", re.compile(r"gemini\b", re.I)),
    ("test", "pytest", re.compile(r"pytest\b", re.I)),
    ("test", "vitest", re.compile(r"vitest\b", re.I)),
    ("test", "jest", re.compile(r"jest\b", re.I)),
    ("dev_server", "vite", re.compile(r"\bvite\b", re.I)),
    ("dev_server", "uvicorn", re.compile(r"\buvicorn\b", re.I)),
    ("dev_server", "streamlit", re.compile(r"\bstreamlit\b", re.I)),
    ("dev_server", "rstudio-server", re.compile(r"\brstudio-server\b", re.I)),
    ("dev_server", "next", re.compile(r"\bnext\s+dev\b", re.I)),
    ("script", "python", re.compile(r"\bpython[23]?\b", re.I)),
    ("script", "rscript", re.compile(r"\brscript\b", re.I)),
    ("script", "node", re.compile(r"\bnode\b", re.I)),
    ("script", "npm", re.compile(r"\bnpm\b", re.I)),
    ("script", "pnpm", re.compile(r"\bpnpm\b", re.I)),
    ("script", "bun", re.compile(r"\bbun\b", re.I)),
    ("script", "bash", re.compile(r"\bbash\b", re.I)),
    ("script", "sh", re.compile(r"\bsh\b", re.I)),
    ("git_ops", "git", re.compile(r"\bgit\b", re.I)),
]


def detect_runtime_type(command: str) -> RuntimeTypeResult:
    """Detect runtime type and detected app from a command string."""
    if not command:
        return RuntimeTypeResult(runtime_type="unknown", reason="empty command")
    text_lower = command.lower()
    for runtime_type, app, pattern in _RUNTIME_PATTERNS:
        if pattern.search(text_lower):
            return RuntimeTypeResult(
                runtime_type=runtime_type,
                detected_app=app,
                confidence=0.85,
                reason=f"matched pattern for {app}",
            )
    return RuntimeTypeResult(runtime_type="unknown", detected_app="", confidence=0.0, reason="no match")


def _raw_session_to_discovered(raw: RawSession) -> DiscoveredSession:
    """Convert a RawSession into a DiscoveredSession with basic fields."""
    cwd = raw.cwd or "unknown"

    # Build ProcessInfo for the root PID if available
    root_process: ProcessInfo | None = None
    if raw.root_pid:
        root_process = get_process_tree(raw.root_pid)

    if root_process is None:
        # Fallback minimal ProcessInfo for sessions where psutil cannot read the tree
        root_process = ProcessInfo(
            pid=raw.root_pid or 0,
            ppid=0,
            name=raw.command or "unknown",
            cmdline=raw.command.split() if raw.command else [],
            cwd=raw.cwd or "",
        )

    def _collect_pids(pi: ProcessInfo) -> list[int]:
        pids = [pi.pid]
        for c in pi.children:
            pids.extend(_collect_pids(c))
        return pids

    all_pids_set = set(_collect_pids(root_process))

    # Generate stable session_id
    if cwd == "unknown":
        session_id = f"{raw.source}-{raw.root_pid or 'unknown'}"
    else:
        seed = f"{cwd}|{raw.source_id}|{raw.root_pid or 0}"
        h = hashlib.md5(seed.encode()).hexdigest()[:8]
        session_id = f"{raw.source}-{h}"

    # Backward-compatible agent detection
    agent_result = detect_agent_type(root_process, [], raw.cwd or "")
    runtime_result = detect_runtime_type(raw.command or "")

    return DiscoveredSession(
        session_id=session_id,
        cwd=cwd,
        root_process=root_process,
        all_pids=sorted(all_pids_set),
        agent_type=agent_result.agent_type,
        agent_confidence=agent_result.confidence,
        agent_detection_reason=agent_result.reason,
        agent_detection_evidence=agent_result.evidence,
        source=raw.source,
        source_id=raw.source_id,
        runtime_type=runtime_result.runtime_type,
        detected_app=runtime_result.detected_app,
        recent_output=raw.recent_output or "",
    )


def discover_sessions() -> list[DiscoveredSession]:
    """Discover terminal sessions from all sources.

    Priority: tmux pane > screen window > raw process.  Processes whose PID
    already belongs to a tmux pane are dropped so we don't show duplicates.
    """
    raw_sessions = discover_all_sessions()
    if not raw_sessions:
        return []

    # Collect PIDs already covered by tmux/screen
    covered_pids: set[int] = set()
    for raw in raw_sessions:
        if raw.source in ("tmux", "screen") and raw.root_pid:
            covered_pids.add(raw.root_pid)

    sessions: list[DiscoveredSession] = []
    for raw in raw_sessions:
        # Skip raw-process sessions whose PID is already inside a tmux/screen pane
        if raw.source == "process" and raw.root_pid in covered_pids:
            continue

        session = _raw_session_to_discovered(raw)

        # Drop desktop-app masquerading sessions (Mac .app bundles with cwd /)
        if _is_desktop_app_cwd(session.cwd):
            continue

        sessions.append(session)

    # Sort by cwd for stable ordering
    sessions.sort(key=lambda s: s.cwd)
    return sessions


def scan_agent_sessions(include_ignored: bool = False) -> list[DiscoveredSession]:
    """Main enrichment pipeline: discover processes → parse session files → extract info → infer activity.

    This is the primary entry point for the SSE endpoint.
    """
    sessions = discover_sessions()
    if not sessions:
        return []

    server_user = _current_server_user()
    enriched: list[DiscoveredSession] = []
    for session in sessions:
        cwd = session.cwd if session.cwd != "unknown" else ""
        root = session.root_process
        session.task_id = session.session_id
        session.root_pid = root.pid
        session.root_cmd = " ".join(root.cmdline) if root.cmdline else root.name
        session.user = root.user
        session.tty = root.tty
        session.is_interactive = bool(root.tty and root.tty != "?")
        session.started_at = None
        if root.create_time:
            from datetime import datetime
            session.started_at = datetime.fromtimestamp(root.create_time)
            session.elapsed_sec = _elapsed_seconds(root)

        # 1. Derive project name
        project_name = derive_project_name(cwd)
        session.project_name = project_name
        session.project = project_name.name
        session.project_root = project_name.git_root or cwd
        session.short_cwd = project_name.short_cwd
        session.project_key = derive_project_key(cwd, project_name.git_root)

        # 1b. Detect agent type with process/session-source evidence.
        from backend.session_parser import discover_session_files, parse_and_match_sessions
        candidate_files = [str(path) for path in discover_session_files(session.agent_type or "unknown", cwd)[:8]]
        detection = detect_agent_type(root, candidate_files, cwd)
        session.agent_type = detection.agent_type
        session.agent_confidence = detection.confidence
        session.agent_detection_reason = detection.reason
        session.agent_detection_evidence = detection.evidence
        agent_type = session.agent_type
        session.display_name = make_display_name(session.session_title, project_name.name, agent_type)

        # 2. Parse session files (heartbeat, recent_output, pending_items)
        session_data = None
        if agent_type and agent_type != "unknown":
            session_data = parse_and_match_sessions(
                agent_type, cwd, root.create_time
            )
            if session_data:
                parsed_session_id = session_data.get("session_id")
                if parsed_session_id:
                    session.task_id = str(parsed_session_id)
                session.heartbeat_ts = session_data.get("heartbeat_ts")
                # For tmux/screen sessions, preserve capture-pane output unless session file provides content
                if session.source in ("tmux", "screen") and session.recent_output:
                    pass
                else:
                    session.recent_output = redact_sensitive_text(session_data.get("recent_output", ""))
                session.pending_items = session_data.get("pending_items", [])
                session.last_user_message = redact_sensitive_text(session_data.get("last_user_message", ""))
                session.conversation = [
                    ConversationMessage(
                        role=str(item.get("role", "unknown")),
                        text=redact_sensitive_text(str(item.get("text", ""))),
                        ts=item.get("ts"),
                        source=str(item.get("source", "session_file")),
                    )
                    for item in session_data.get("conversation", [])[:10]
                    if isinstance(item, dict) and item.get("text")
                ]
                session.session_title = session.last_user_message[:80] or None
                session.display_name = make_display_name(session.session_title, project_name.name, agent_type)
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

        # 6. Extract user instruction
        instruction = extract_user_instruction(cwd, agent_type, session_data)
        session.instruction = instruction
        session.user_instruction = redact_sensitive_text(instruction.text)
        session.instruction_source = instruction.source
        session.instruction_confidence = instruction.confidence
        session.source_file = (session_data or {}).get("source_file", "")
        session.confidence = instruction.confidence

        # 7. Collect active commands and child processes
        session.active_commands = _collect_active_commands(root)
        session.child_processes = root.children
        session.background_jobs = build_background_jobs(root)
        session.foreground = build_foreground_info(root, session.recent_output, session.heartbeat_ts, session.status)
        session.current_activity = summarize_activity(session.status, reason, session.background_jobs, session.foreground)

        # 8. Resource metrics
        session.cpu_percent = root.cpu_percent
        session.memory_percent = root.memory_percent
        session.resource_usage = ResourceUsage(
            cpu_percent=root.cpu_percent,
            memory_percent=root.memory_percent,
            rss_mb=(root.resources.rss_mb if root.resources else 0.0),
            children_count=len(session.background_jobs),
        )

        # 9. Project runtime status
        if cwd:
            session.project_status = get_project_runtime_status(cwd, recent_files)
            session.git_status = "dirty" if session.project_status.has_uncommitted else "clean"
            status_short = get_git_status_short(get_git_root(cwd) or cwd)
            session.git_status_detail = _build_git_status(
                session.project_status,
                status_short,
                bool(get_git_root(cwd)),
            )
            if session.project_status.branch and not session.project_name.git_branch:
                session.project_name.git_branch = session.project_status.branch
        session.recent_files = recent_files[:20]

        pin_rules = matching_rules("pins", session)
        ignore_rules = matching_rules("ignored", session)
        session.is_pinned = bool(pin_rules)
        session.is_ignored = bool(ignore_rules)
        session.tags = []
        if session.is_pinned:
            session.tags.append("pinned")
        auto_ignore_reason = _auto_ignore_reason(session, server_user=server_user, recent_files=recent_files)
        if auto_ignore_reason:
            session.is_ignored = True
            session.tags.append("auto_ignored")
            session.status_reason = f"{session.status_reason} ({auto_ignore_reason})" if session.status_reason else auto_ignore_reason
        if session.is_ignored:
            session.tags.append("ignored")
        session.status_group = status_group_for(session.status, ignored=session.is_ignored)
        session.status_dot = status_dot_for(session.status, session.status_group, has_error=bool(session.error_hints))
        if (
            not session.is_ignored
            and session.heartbeat_age_sec is not None
            and session.heartbeat_age_sec > STALE_INACTIVE_SECONDS
            and session.status_group == "idle"
        ):
            minutes = int(session.heartbeat_age_sec // 60)
            session.status_reason = f"No visible activity for {minutes} minutes"
        if session.is_ignored and not include_ignored:
            continue

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
                    session.recent_logs = [redact_sensitive_text(line) for line in lines[-10:]]
                except Exception:
                    pass

        # 13. Notification trigger
        try:
            dispatcher = get_dispatcher()
            dispatcher.notify_if_needed(session)
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


def get_resource_metrics(pid: int) -> ResourceMetrics | None:
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
