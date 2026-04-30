from __future__ import annotations

import logging
import time
from typing import Any

from backend.config import load_config
from backend.models import DiscoveredSession
from backend.notifications.base import NotificationEvent, Notifier
from backend.notifications.feishu import FeishuNotifier
from backend.notifications.wecom import WeComNotifier

logger = logging.getLogger("agentdeck")

# Events that trigger notifications
_DEFAULT_NOTIFY_EVENTS = {
    "needs_input",
    "error_hint",
    "failed",
    "completed",
    "stale",
}


class NotificationDispatcher:
    """Routes session state changes to configured notifiers with throttling."""

    def __init__(self):
        self._notifiers: list[Notifier] = []
        self._throttle_seconds = 300
        self._enabled = False
        self._events: set[str] = set(_DEFAULT_NOTIFY_EVENTS)
        self._dashboard_url = ""
        self._last_notified: dict[tuple[str, str], float] = {}
        self._reload_config()

    def _reload_config(self) -> None:
        cfg = load_config()
        notify_cfg: dict[str, Any] = cfg.get("notifications") or {}
        self._enabled = bool(notify_cfg.get("enabled", False))
        self._throttle_seconds = int(notify_cfg.get("throttle_seconds", 300))
        self._events = set(notify_cfg.get("events", list(_DEFAULT_NOTIFY_EVENTS)))
        self._dashboard_url = notify_cfg.get("dashboard_url", "")

        self._notifiers = []

        feishu_cfg = notify_cfg.get("feishu") or {}
        if feishu_cfg.get("enabled") and feishu_cfg.get("webhook_url"):
            self._notifiers.append(
                FeishuNotifier(
                    webhook_url=str(feishu_cfg["webhook_url"]),
                    secret=feishu_cfg.get("secret") or None,
                )
            )

        wecom_cfg = notify_cfg.get("wecom") or {}
        if wecom_cfg.get("enabled") and wecom_cfg.get("webhook_url"):
            self._notifiers.append(
                WeComNotifier(webhook_url=str(wecom_cfg["webhook_url"]))
            )

    def _is_throttled(self, source_id: str, status: str) -> bool:
        key = (source_id, status)
        last = self._last_notified.get(key)
        if last is None:
            return False
        return time.time() - last < self._throttle_seconds

    def _mark_notified(self, source_id: str, status: str) -> None:
        self._last_notified[(source_id, status)] = time.time()

    def _build_event(self, session: DiscoveredSession) -> NotificationEvent:
        short_cwd = session.short_cwd or session.cwd
        if len(short_cwd) > 60:
            parts = short_cwd.split("/")
            if len(parts) > 3:
                short_cwd = ".../" + "/".join(parts[-3:])

        elapsed = session.elapsed_sec
        if elapsed is None and session.root_process.create_time:
            elapsed = max(0, int(time.time() - session.root_process.create_time))

        return NotificationEvent(
            session_title=session.display_name or session.session_title or session.source_id,
            source=session.source,
            source_id=session.source_id,
            cwd_short=short_cwd,
            status=session.status,
            summary=session.current_activity or session.status_reason or "",
            recent_output_snippet=session.recent_output[:400] if session.recent_output else "",
            dashboard_url=self._dashboard_url,
            cpu_percent=session.cpu_percent,
            elapsed_sec=elapsed,
        )

    def notify_if_needed(self, session: DiscoveredSession) -> None:
        """Send notification if session status warrants it and not throttled."""
        self._reload_config()
        if not self._enabled or not self._notifiers:
            return
        if session.is_ignored:
            return
        if session.status not in self._events:
            return
        if not session.source_id:
            return
        if self._is_throttled(session.source_id, session.status):
            return

        event = self._build_event(session)
        sent = False
        for notifier in self._notifiers:
            try:
                if notifier.send(event):
                    sent = True
            except Exception:
                logger.exception("Notifier %s failed", notifier.name)
        if sent:
            self._mark_notified(session.source_id, session.status)


# Global dispatcher instance
_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
