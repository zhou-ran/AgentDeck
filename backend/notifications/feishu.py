from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.request
from typing import Any

from backend.notifications.base import NotificationEvent

logger = logging.getLogger("agentdeck")


class FeishuNotifier:
    """Feishu (Lark) custom bot webhook notifier."""

    name = "feishu"

    def __init__(self, webhook_url: str, secret: str | None = None):
        self.webhook_url = webhook_url
        self.secret = secret
        self.enabled = bool(webhook_url)

    def _sign(self, timestamp: int) -> str | None:
        if not self.secret:
            return None
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _build_payload(self, event: NotificationEvent) -> dict[str, Any]:
        timestamp = int(time.time())
        sign = self._sign(timestamp)

        lines = [
            f"**AgentDeck**: {event.session_title or event.source_id}",
            f"",
            f"**来源**: {event.source} `{event.source_id}`",
            f"**状态**: {event.status}",
            f"**CWD**: {event.cwd_short}",
            f"**CPU**: {event.cpu_percent:.1f}%",
        ]
        if event.elapsed_sec is not None:
            mins, secs = divmod(event.elapsed_sec, 60)
            hours, mins = divmod(mins, 60)
            if hours:
                elapsed = f"{hours}h{mins}m"
            elif mins:
                elapsed = f"{mins}m{secs}s"
            else:
                elapsed = f"{secs}s"
            lines.append(f"**运行时长**: {elapsed}")

        if event.recent_output_snippet:
            snippet = event.recent_output_snippet[:300]
            if len(event.recent_output_snippet) > 300:
                snippet += "…"
            lines.append(f"**最近输出**: {snippet}")

        if event.dashboard_url:
            lines.append(f"**面板**: {event.dashboard_url}")

        content = "\n".join(lines)
        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": content},
        }
        if sign:
            payload["timestamp"] = str(timestamp)
            payload["sign"] = sign
        return payload

    def send(self, event: NotificationEvent) -> bool:
        if not self.enabled or not self.webhook_url:
            return False
        payload = self._build_payload(event)
        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if body.get("code") not in (None, 0, "0"):
                    logger.warning("Feishu webhook error: %s", body)
                    return False
                return True
        except Exception as exc:
            logger.warning("Feishu webhook failed: %s", exc)
            return False
