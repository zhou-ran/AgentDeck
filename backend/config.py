from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_DIR = Path.home() / ".agent_foreman_local"
DEFAULT_TASKS_DIR = DEFAULT_CONFIG_DIR / "tasks"
DEFAULT_LOGS_DIR = Path.home() / "agent_logs"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

AGENT_KEYWORDS = [
    "codex", "claude", "aider", "gemini",
    "node", "python", "python3", "uv", "npm", "pnpm", "bun",
    "git", "pytest", "Rscript", "cargo", "go",
]

_CONFIG_CACHE: dict[str, Any] | None = None
_CONFIG_CACHE_MTIME: float | None = None
_CONFIG_CACHE_PATH: Path | None = None


def _ensure_dirs() -> None:
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    global _CONFIG_CACHE, _CONFIG_CACHE_MTIME, _CONFIG_CACHE_PATH

    _ensure_dirs()
    config_path = DEFAULT_CONFIG_FILE
    if config_path.exists():
        mtime = config_path.stat().st_mtime
        if (
            _CONFIG_CACHE is not None
            and _CONFIG_CACHE_PATH == config_path
            and _CONFIG_CACHE_MTIME == mtime
        ):
            return dict(_CONFIG_CACHE)
        with open(DEFAULT_CONFIG_FILE) as f:
            cfg = yaml.safe_load(f) or {}
            _CONFIG_CACHE = dict(cfg)
            _CONFIG_CACHE_MTIME = mtime
            _CONFIG_CACHE_PATH = config_path
            return cfg
    _CONFIG_CACHE = {}
    _CONFIG_CACHE_MTIME = None
    _CONFIG_CACHE_PATH = config_path
    return {}


def save_config(cfg: dict) -> None:
    global _CONFIG_CACHE, _CONFIG_CACHE_MTIME, _CONFIG_CACHE_PATH

    _ensure_dirs()
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    _CONFIG_CACHE = dict(cfg)
    _CONFIG_CACHE_MTIME = DEFAULT_CONFIG_FILE.stat().st_mtime
    _CONFIG_CACHE_PATH = DEFAULT_CONFIG_FILE


def get_or_create_token() -> str:
    cfg = load_config()
    token = cfg.get("token")
    if not token:
        token = secrets.token_urlsafe(32)
        cfg["token"] = token
        save_config(cfg)
    return token


def get_log_dir() -> Path:
    cfg = load_config()
    p = cfg.get("log_dir", str(DEFAULT_LOGS_DIR))
    path = Path(p).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_tasks_dir() -> Path:
    cfg = load_config()
    p = cfg.get("tasks_dir", str(DEFAULT_TASKS_DIR))
    path = Path(p).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_host() -> str:
    cfg = load_config()
    return cfg.get("host", "127.0.0.1")


def get_port() -> int:
    cfg = load_config()
    return cfg.get("port", 9797)
