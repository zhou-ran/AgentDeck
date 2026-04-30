from __future__ import annotations

from backend.session_sources.base import RawSession


class ProcessSessionSource:
    """Discover coding agent processes via psutil."""

    name = "process"

    def discover(self) -> list[RawSession]:
        from backend.process_scanner import discover_agent_processes

        procs = discover_agent_processes()
        sessions: list[RawSession] = []
        for info in procs:
            cmd = " ".join(info.cmdline) if info.cmdline else info.name
            sessions.append(
                RawSession(
                    source="process",
                    source_id=f"process:{info.pid}",
                    title=cmd[:120] or None,
                    cwd=info.cwd or None,
                    root_pid=info.pid,
                    command=cmd,
                    created_at=info.create_time or None,
                )
            )
        return sessions
