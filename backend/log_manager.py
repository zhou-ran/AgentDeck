from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator


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
            return result
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
                        yield line

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
