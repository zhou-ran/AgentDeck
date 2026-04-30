from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from backend.models import DiscoveredSession, ProcessInfo, ProjectNameInfo
from backend.notifications.base import NotificationEvent
from backend.notifications.dispatcher import NotificationDispatcher
from backend.notifications.feishu import FeishuNotifier
from backend.notifications.wecom import WeComNotifier


class TestFeishuNotifier:
    def test_builds_text_payload(self):
        notifier = FeishuNotifier(webhook_url="http://example.com", secret=None)
        event = NotificationEvent(
            session_title="my-session",
            source="tmux",
            source_id="tmux:a:0.0",
            status="needs_input",
            summary="waiting",
            recent_output_snippet="Continue?",
            dashboard_url="http://localhost:9797",
            cpu_percent=1.5,
            elapsed_sec=3661,
        )
        payload = notifier._build_payload(event)
        assert payload["msg_type"] == "text"
        text = payload["content"]["text"]
        assert "my-session" in text
        assert "needs_input" in text
        assert "1h1m" in text
        assert "Continue?" in text

    def test_send_disabled_when_no_url(self):
        notifier = FeishuNotifier(webhook_url="", secret=None)
        assert notifier.send(NotificationEvent()) is False


class TestWeComNotifier:
    def test_builds_markdown_payload(self):
        notifier = WeComNotifier(webhook_url="http://example.com")
        event = NotificationEvent(
            session_title="my-session",
            source="process",
            source_id="process:42",
            status="error_hint",
            summary="failed test",
            recent_output_snippet="Traceback...",
            dashboard_url="http://localhost:9797",
            cpu_percent=0.0,
            elapsed_sec=60,
        )
        payload = notifier._build_payload(event)
        assert payload["msgtype"] == "markdown"
        content = payload["markdown"]["content"]
        assert "my-session" in content
        assert "error_hint" in content
        assert "1m0s" in content


class TestNotificationDispatcher:
    def test_respects_enabled_false(self, monkeypatch):
        dispatcher = NotificationDispatcher()
        monkeypatch.setattr(dispatcher, "_enabled", False)
        dispatcher._notifiers = [MagicMock()]

        session = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source_id="process:1",
            status="needs_input",
        )
        dispatcher.notify_if_needed(session)
        for n in dispatcher._notifiers:
            assert not n.send.called

    def test_throttles_same_source_id_and_status(self, monkeypatch):
        dispatcher = NotificationDispatcher()
        monkeypatch.setattr(dispatcher, "_reload_config", lambda: None)
        monkeypatch.setattr(dispatcher, "_enabled", True)
        monkeypatch.setattr(dispatcher, "_throttle_seconds", 300)
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True
        dispatcher._notifiers = [mock_notifier]

        session = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source_id="process:1",
            status="needs_input",
        )
        dispatcher.notify_if_needed(session)
        assert mock_notifier.send.call_count == 1

        dispatcher.notify_if_needed(session)
        # Second call should be throttled
        assert mock_notifier.send.call_count == 1

    def test_does_not_throttle_different_status(self, monkeypatch):
        dispatcher = NotificationDispatcher()
        monkeypatch.setattr(dispatcher, "_reload_config", lambda: None)
        monkeypatch.setattr(dispatcher, "_enabled", True)
        monkeypatch.setattr(dispatcher, "_throttle_seconds", 300)
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True
        dispatcher._notifiers = [mock_notifier]

        session1 = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source_id="process:1",
            status="needs_input",
        )
        dispatcher.notify_if_needed(session1)
        assert mock_notifier.send.call_count == 1

        session2 = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source_id="process:1",
            status="error_hint",
        )
        dispatcher.notify_if_needed(session2)
        assert mock_notifier.send.call_count == 2

    def test_ignored_sessions_are_skipped(self, monkeypatch):
        dispatcher = NotificationDispatcher()
        monkeypatch.setattr(dispatcher, "_reload_config", lambda: None)
        monkeypatch.setattr(dispatcher, "_enabled", True)
        mock_notifier = MagicMock()
        dispatcher._notifiers = [mock_notifier]

        session = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source_id="process:1",
            status="needs_input",
            is_ignored=True,
        )
        dispatcher.notify_if_needed(session)
        assert not mock_notifier.send.called


class TestWebhookSecurity:
    def test_webhook_url_not_in_discover_response(self, monkeypatch):
        import anyio
        import httpx
        from backend.main import app
        from backend.security import api_rate_limiter
        from backend.models import DiscoveredSession, ProcessInfo

        api_rate_limiter._requests.clear()

        dummy = DiscoveredSession(
            session_id="s1",
            project_key="p1",
            cwd="/tmp",
            root_process=ProcessInfo(pid=1, ppid=0, name="x", cmdline=["x"]),
            source="process",
            source_id="process:1",
            status="idle",
        )
        monkeypatch.setattr("backend.api.processes.scan_agent_sessions", lambda **_: [dummy])

        async def run():
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 50000))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/api/discover?token=test")

        res = anyio.run(run)
        assert res.status_code == 200
        text = res.text
        assert "webhook_url" not in text
        assert "AGENTDECK_FEISHU_WEBHOOK" not in text
