from __future__ import annotations

import shutil
import subprocess

from backend.session_sources.base import RawSession


class TmuxSessionSource:
    """Discover tmux panes as terminal sessions."""

    name = "tmux"

    _LIST_FORMAT = (
        "#{session_name}|#{window_index}|#{pane_index}|#{pane_pid}|"
        "#{pane_current_path}|#{pane_current_command}|#{pane_active}|#{pane_title}"
    )

    def discover(self) -> list[RawSession]:
        if not shutil.which("tmux"):
            return []

        panes = self._list_panes()
        sessions: list[RawSession] = []
        for pane in panes:
            recent_output = self._capture_pane(pane["target"])
            title = pane["pane_title"] or f"{pane['session_name']}:{pane['window_index']}.{pane['pane_index']}"
            sessions.append(
                RawSession(
                    source="tmux",
                    source_id=f"tmux:{pane['session_name']}:{pane['window_index']}.{pane['pane_index']}",
                    title=title,
                    cwd=pane["pane_current_path"] or None,
                    root_pid=pane["pane_pid"],
                    command=pane["pane_current_command"] or None,
                    recent_output=recent_output or None,
                    attached=bool(pane.get("pane_active")),
                )
            )
        return sessions

    def _list_panes(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-a", "-F", self._LIST_FORMAT],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        if result.returncode != 0:
            return []

        panes = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 7)
            if len(parts) != 8:
                continue
            try:
                pane_pid = int(parts[3])
            except ValueError:
                pane_pid = None
            panes.append(
                {
                    "session_name": parts[0],
                    "window_index": parts[1],
                    "pane_index": parts[2],
                    "pane_pid": pane_pid,
                    "pane_current_path": parts[4],
                    "pane_current_command": parts[5],
                    "pane_active": parts[6] == "1",
                    "pane_title": parts[7],
                    "target": f"{parts[0]}:{parts[1]}.{parts[2]}",
                }
            )
        return panes

    def _capture_pane(self, target: str, lines: int = 200) -> str | None:
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", target, "-S", f"-{lines}"],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout
