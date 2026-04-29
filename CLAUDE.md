# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AgentStatus — a local coding agent monitoring dashboard + CLI tool. Monitors multiple coding agents (codex, claude, aider, gemini, pytest, npm, git, Rscript, etc.) on a Linux server with a unified web UI.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, psutil, click, uvicorn
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS
- **Communication**: SSE (server-sent events) for real-time updates
- **State storage**: JSON files (no database)

## Commands

```bash
# Install
make install                    # pip install -e . + frontend build
pipx install .                  # Alternative: isolated install

# Development
make dev                        # Backend (--reload) + Frontend (vite dev) concurrently
make test                       # Run pytest
make build-frontend             # Build frontend to backend/static/
make clean                      # Clean build artifacts

# CLI (agent-foreman-local, alias: agentctl)
agent-foreman-local serve [--host 127.0.0.1] [--port 9797]
agent-foreman-local start <name> --dir <dir> -- <command...>
agent-foreman-local init <name> --dir <dir> --goal "..."
agent-foreman-local set-plan <task_id> plan.json
agent-foreman-local note <task_id> "..."
agent-foreman-local step <task_id> <step_id> --status running|done|blocked
agent-foreman-local complete <task_id> --summary "..."
agent-foreman-local fail <task_id> --reason "..."
agent-foreman-local handoff <task_id>
agent-foreman-local list [--all]
agent-foreman-local status <task_id>
agent-foreman-local stop <task_id>
agent-foreman-local tail <task_id> [-f]
agent-foreman-local import-pid <pid> --name <name>
agent-foreman-local discover
agent-foreman-local config
agent-foreman-local install-service [--enable]
agent-foreman-local uninstall-service

# Frontend development
cd frontend
npm run dev          # Vite dev server with proxy to :9797
npm run build        # Build to backend/static/
```

## Architecture

```
backend/
├── models.py          # Pydantic models: Task, TaskStatus, ProcessInfo, PlanStep
├── config.py          # Config loader (~/.agent_foreman_local/config.yaml)
├── task_manager.py    # Task CRUD + enrichment + plan/step management
├── process_scanner.py # psutil-based agent discovery + process tree
├── state_machine.py   # Status inference + error hint detection
├── log_manager.py     # Log tail, last-N-lines, async stream
├── git_utils.py       # Git changed files detection
├── security.py        # Path safety, PID verify, rate limiter, atomic write
├── systemd.py         # systemd user service generation
├── cli.py             # click CLI: all agent-foreman-local commands
├── main.py            # FastAPI app, mounts API routers + static files
└── api/
    ├── tasks.py       # /api/tasks CRUD, stop, notes, log, process-tree
    ├── processes.py   # /api/discover — auto-find agent processes
    ├── sse.py         # /api/events — SSE endpoint, pushes every 2s
    └── auth.py        # Token auth (skipped on localhost)

frontend/src/
├── App.tsx            # Root: useSSE hook → Dashboard
├── hooks/useSSE.ts    # SSE connection with auto-reconnect
├── api/client.ts      # Fetch wrapper for all API calls
├── utils/format.ts    # Shared formatBytes, elapsed helpers
├── components/
│   ├── Dashboard.tsx   # Task card grid with filters + search
│   ├── FilterBar.tsx   # Status filter pills + search input
│   ├── TaskCard.tsx    # Card with status badge, error hint, elapsed
│   ├── TaskDetail.tsx  # Full detail: metadata, tree, logs, plan, progress
│   ├── ProcessTree.tsx # Recursive process tree visualization
│   ├── LogViewer.tsx   # Log tail with error highlighting
│   ├── SparkLine.tsx   # CPU/MEM history chart
│   ├── SystemOverview.tsx # System-wide metrics display
│   ├── DiscoveredCard.tsx # Discovered agent session card
│   └── StatusBadge.tsx # Color-coded status indicator
└── types/index.ts     # TypeScript interfaces

tests/
├── conftest.py           # Shared fixtures (isolated config via tmp_path)
├── test_task_store.py    # Task CRUD, atomic write, plan/step management
├── test_process_scanner.py # PID validation, elapsed formatting
├── test_log_tail.py      # Log reading, tail, size, mtime
├── test_state_machine.py # Status inference, error detection
├── test_security.py      # Path safety, task_id regex, rate limiter
├── test_api_auth.py      # Token auth endpoint tests
├── test_api_tasks.py     # Task API endpoint tests
└── test_config.py        # Config loading tests

scripts/
├── demo_long_task.sh     # Long-running task demo
└── demo_fail_task.sh     # Failing task demo

docs/
├── prompts.md            # Original design prompts
├── XM.md                 # Project review report
└── kimi.md               # Code review report
```

## Key Patterns

- **Task lifecycle**: `agent-foreman-local start` creates a JSON task file + launches subprocess with stdout/stderr redirected to `~/agent_logs/{task_id}.log`
- **State enrichment**: `task_manager.enrich_task()` combines persisted task data with live psutil data on every API call
- **Status inference**: `state_machine.infer_status()` checks process alive/dead, CPU%, log mtime
- **Error detection**: `state_machine.check_error_hint()` regex-matches `Traceback|ERROR|Failed|Exception` in log tail
- **SSE streaming**: `/api/events` pushes full task list JSON every 2 seconds; frontend reconnects automatically
- **Frontend build**: Vite outputs to `backend/static/` which FastAPI serves as static files with HTML5 fallback

## File Locations at Runtime

- Config: `~/.agent_foreman_local/config.yaml`
- Task state: `~/.agent_foreman_local/tasks/{task_id}.json`
- Logs: `~/agent_logs/{task_id}.log`
- systemd service: `~/.config/systemd/user/agent-foreman-local.service`
