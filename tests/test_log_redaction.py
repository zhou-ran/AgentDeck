from __future__ import annotations

from backend.log_manager import redact_sensitive_text


def test_redact_sensitive_text_masks_common_secrets():
    line = "sk-abcdefghijklmnopqrstuvwxyz api_key=secret Authorization: Bearer token123"

    redacted = redact_sensitive_text(line)

    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "api_key=secret" not in redacted
    assert "token123" not in redacted
    assert "[redacted]" in redacted
