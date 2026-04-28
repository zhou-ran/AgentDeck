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
pip install -e .
cd frontend && npm install && npx vite build

# CLI
agentctl start <name> --dir <dir> -- <command...>
agentctl list [--all]
agentctl status <task_id>
agentctl stop <task_id>
agentctl tail <task_id> [-f]
agentctl note <task_id> "message"
agentctl step <task_id> <step_id> --status done
agentctl set-plan <task_id> plan.json
agentctl complete <task_id> --summary "..."
agentctl fail <task_id> --reason "..."
agentctl handoff <task_id>
agentctl serve [--host 0.0.0.0] [--port 8790]

# Frontend development
cd frontend
npm run dev          # Vite dev server with proxy to :8790
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
├── cli.py             # click CLI: all agentctl commands
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
├── components/
│   ├── Dashboard.tsx   # Task card grid, active/finished sections
│   ├── TaskCard.tsx    # Card with status badge, error hint, elapsed
│   ├── TaskDetail.tsx  # Full detail: metadata, tree, logs, plan, progress
│   ├── ProcessTree.tsx # Recursive process tree visualization
│   ├── LogViewer.tsx   # Log tail with error highlighting
│   └── StatusBadge.tsx # Color-coded status indicator
└── types/index.ts     # TypeScript interfaces
```

## Key Patterns

- **Task lifecycle**: `agentctl start` creates a JSON task file + launches subprocess with stdout/stderr redirected to `~/agent_logs/{task_id}.log`
- **State enrichment**: `task_manager.enrich_task()` combines persisted task data with live psutil data on every API call
- **Status inference**: `state_machine.infer_status()` checks process alive/dead, CPU%, log mtime
- **Error detection**: `state_machine.check_error_hint()` regex-matches `Traceback|ERROR|Failed|Exception` in log tail
- **SSE streaming**: `/api/events` pushes full task list JSON every 2 seconds; frontend reconnects automatically
- **Frontend build**: Vite outputs to `backend/static/` which FastAPI serves as static files with HTML5 fallback

## File Locations at Runtime

- Config: `~/.agent_foreman_local/config.yaml`
- Task state: `~/.agent_foreman_local/tasks/{task_id}.json`
- Logs: `~/agent_logs/{task_id}.log`
