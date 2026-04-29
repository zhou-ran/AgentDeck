"""Tests for config loading and caching."""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import backend.config as config


class TestLoadConfigCache:
    def test_reuses_cache_when_file_unchanged(self):
        config.DEFAULT_CONFIG_FILE.write_text("port: 9000\n")
        calls = 0
        original_open = builtins.open

        def counting_open(*args, **kwargs):
            nonlocal calls
            if Path(args[0]) == config.DEFAULT_CONFIG_FILE:
                calls += 1
            return original_open(*args, **kwargs)

        builtins.open = counting_open
        try:
            assert config.load_config()["port"] == 9000
            assert config.load_config()["port"] == 9000
        finally:
            builtins.open = original_open

        assert calls == 1

    def test_invalidates_cache_when_file_changes(self):
        config.DEFAULT_CONFIG_FILE.write_text("port: 9000\n")
        first = config.load_config()

        config.DEFAULT_CONFIG_FILE.write_text("port: 9001\n")
        current = config.DEFAULT_CONFIG_FILE.stat()
        os.utime(config.DEFAULT_CONFIG_FILE, (current.st_atime + 2, current.st_mtime + 2))

        second = config.load_config()

        assert first["port"] == 9000
        assert second["port"] == 9001
