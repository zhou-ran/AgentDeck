from __future__ import annotations

from backend.session_sources.base import RawSession


class ScreenSessionSource:
    """Discover screen sessions as terminal sessions (best-effort stub)."""

    name = "screen"

    def discover(self) -> list[RawSession]:
        # TODO: implement screen -ls / screen -Q windows parsing
        return []
