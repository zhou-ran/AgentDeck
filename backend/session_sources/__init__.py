from __future__ import annotations

from backend.session_sources.base import RawSession, RuntimeTypeResult, SessionSource
from backend.session_sources.process import ProcessSessionSource
from backend.session_sources.screen import ScreenSessionSource
from backend.session_sources.tmux import TmuxSessionSource

__all__ = [
    "RawSession",
    "RuntimeTypeResult",
    "SessionSource",
    "ProcessSessionSource",
    "ScreenSessionSource",
    "TmuxSessionSource",
    "discover_all_sessions",
]


# Priority order: tmux pane > screen window > managed task > raw process
_SOURCES: list[SessionSource] = [
    TmuxSessionSource(),
    ScreenSessionSource(),
    ProcessSessionSource(),
]


def discover_all_sessions() -> list[RawSession]:
    """Discover terminal sessions from all available sources."""
    sessions: list[RawSession] = []
    seen_source_ids: set[str] = set()
    for src in _SOURCES:
        try:
            for session in src.discover():
                if session.source_id and session.source_id in seen_source_ids:
                    continue
                if session.source_id:
                    seen_source_ids.add(session.source_id)
                sessions.append(session)
        except Exception:
            # Individual sources must not crash the whole discovery
            continue
    return sessions
