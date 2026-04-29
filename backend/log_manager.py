from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import AsyncIterator

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)\b(api[_-]?key\s*=\s*)[^\s]+"),
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)[^\s]+"),
)


def redact_sensitive_text(text: str) -> str:
    """Redact common API credentials before log text leaves the backend."""
    redacted = SECRET_PATTERNS[0].sub("sk-...[redacted]", text)
    redacted = SECRET_PATTERNS[1].sub(r"\1[redacted]", redacted)
    redacted = SECRET_PATTERNS[2].sub(r"\1[redacted]", redacted)
    return redacted


def get_log_tail(path: Path, lines: int = 50) -> list[str]:
    """Read the last N lines from a log file efficiently."""
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            # Seek to end, read chunks backwards
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block_size = min(size, 8192)
            data = b""
            pos = size

            while pos > 0 and data.count(b"\n") <= lines:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                chunk = f.read(read_size)
                data = chunk + data

            text = data.decode("utf-8", errors="replace")
            result = text.splitlines()[-lines:]
            return [redact_sensitive_text(line) for line in result]
    except (PermissionError, OSError):
        return []


async def tail_log(path: Path, from_offset: int = 0) -> AsyncIterator[str]:
    """Async generator that yields new log lines as they appear."""
    if not path.exists():
        return

    offset = from_offset
    try:
        while True:
            try:
                size = path.stat().st_size
            except OSError:
                await asyncio.sleep(1)
                continue

            if size > offset:
                with open(path, "rb") as f:
                    f.seek(offset)
                    new_data = f.read(size - offset)
                    offset = size
                    text = new_data.decode("utf-8", errors="replace")
                    for line in text.splitlines():
                        yield redact_sensitive_text(line)

            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        return


def get_log_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def get_log_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
