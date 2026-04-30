# AgentDeck — AI Agent Context

> If you are an AI coding agent reading this repo, here is the condensed context you need to work effectively.

## What is AgentDeck?

A **single-machine** web dashboard + CLI for monitoring terminal sessions and long-running jobs (codex, claude, kimi, aider, gemini, pytest, npm, git, tmux panes, etc.). It auto-discovers running sessions from tmux panes, screen windows, and standalone processes, then displays them in a live React UI via SSE.

## Architecture

```
CLI (click) ──► task_manager ──► JSON files (~/.agentdeck/tasks/)
     │
FastAPI app ─────┤
    ├── /api/tasks           (CRUD + plan/step/handoff/logs/process tree)
    ├── /api/discover        (auto-scan live sessions from tmux/screen/process)
    ├── /api/events          (SSE stream, 2s interval)
    ├── /api/pins            (persistent pin rules)
    ├── /api/ignored         (persistent ignore rules)
    ├── /api/sessions/{id}/… (pin/unpin/ignore/unignore discovered sessions)
    ├── /api/system-metrics  (host resource overview)
    └── static/       (Vite build output → backend/static/)

Session discovery pipeline:
    session_sources/ ──► discover_all_sessions()
        ├── tmux.py    (tmux list-panes + capture-pane)
        ├── screen.py  (screen -ls, best-effort)
        └── process.py (psutil agent process scanning)
    
    Enrichment: detect_runtime_type → infer activity → git status → build DiscoveredSession
    
    Notifications (optional):
        notifications/ ──► dispatcher
            ├── feishu.py  (Feishu/Lark custom bot webhook)
            └── wecom.py   (WeCom group bot webhook)
```

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.11+, FastAPI, psutil, click, uvicorn |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Storage | JSON files (no database) |
| Tests | pytest |

## Key Files

| File | Responsibility |
|------|--------------|
| `backend/cli.py` | All CLI commands (click group) |
| `backend/main.py` | FastAPI app, lifespan, security middleware |
| `backend/models.py` | Pydantic models for tasks, sessions, plans |
| `backend/task_manager.py` | Task CRUD, JSON persistence, atomic writes |
| `backend/session_sources/` | Session discovery abstraction (tmux, screen, process) |
| `backend/process_scanner.py` | Auto-discovery, enrichment, and activity inference |
| `backend/session_parser.py` | Session/log parsing for live agent activity |
| `backend/notifications/` | Webhook notifications (Feishu, WeCom) with throttle |
| `backend/rules.py` | Persistent pin/ignore rule storage |
| `backend/config.py` | Config dir, token generation, YAML I/O |
| `backend/security.py` | Path validation, rate limiter, token helpers |
| `backend/api/` | FastAPI routers (tasks, processes, SSE, auth) |
| `frontend/src/App.tsx` | Main React layout |
| `frontend/src/api/client.ts` | HTTP + SSE client |
| `frontend/src/components/Dashboard.tsx` | Terminal-style live session dashboard |
| `frontend/src/components/DiscoveredCard.tsx` | Live session card |

## Development Commands

```bash
make dev          # uvicorn --reload + vite dev server concurrently
make test         # pytest
make build-frontend   # tsc && vite build → backend/static/
```

## Coding Conventions

- Use `from __future__ import annotations` in every Python file.
- Pydantic models live in `backend/models.py`; do not define ad-hoc dicts in API layer.
- All file writes go through `atomic_write()` (see `backend/task_manager.py`).
- Path traversal is blocked by `is_safe_project_dir()` / `is_safe_log_path()`.
- Frontend managed-task state updates via SSE (`/api/events`). The live session dashboard also refreshes `/api/discover?include_ignored=true` and rule endpoints on a bounded interval; do not add unbounded polling loops.
- No `sudo`, `ptrace`, `TIOCSTI`, or arbitrary shell execution endpoints.

## Security Constraints (hard rules)

- Default bind: `127.0.0.1`; LAN requires `--host 0.0.0.0` + Bearer token.
- Never read `/proc/<pid>/environ`.
- Git commands use a whitelist (`status`, `diff`, `log`, `show`) with `shell=False` and timeout.
- Rate limit: 120 req/min per IP.
- If adding new API endpoints, apply `dependencies=[require_token()]` unless explicitly localhost-only.

## Common Modification Points

- **New session source** (tmux/screen/process) → `backend/session_sources/`.
- **New agent type / runtime detection** → `backend/process_scanner.py:detect_runtime_type()`, `backend/session_parser.py`, and `AGENT_KEYWORDS` in `backend/config.py`.
- **Pin/ignore behavior** → `backend/rules.py`, `backend/api/processes.py`, and dashboard/client types.
- **New CLI command** → add to `backend/cli.py`, re-use `backend/task_manager.py` helpers.
- **UI new page/card** → add route in `frontend/src/App.tsx`, component in `frontend/src/components/`.
- **New config field** → add to `backend/config.py` + `config.example.yaml`.
- **Notifications** → `backend/notifications/` (Feishu/WeCom webhooks). Webhook URLs must never be exposed in API responses or logs.
- **Log redaction** → patterns live in `backend/log_manager.py:SECRET_PATTERNS`.
- **Public project docs** → tracked root docs are `README.md`, `AGENTS.md`, `SECURITY.md`, and `PUSH_GUIDE.md`. `CLAUDE.md` and `docs/` are intentionally local/ignored.

## When in Doubt

1. Check this file first. `CLAUDE.md` may exist locally for Claude-specific notes, but it is not tracked.
2. Check `tests/` for existing behavior contracts.
3. Run `make test` before committing.
