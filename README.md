# AgentStatus — Local Coding Agent Supervisor

A unified web dashboard and CLI for monitoring multiple coding agents (codex, claude, aider, gemini, pytest, npm, git, Rscript, etc.) running on a Linux server.

## Install

```bash
pip install -e .
cd frontend && npm install && npx vite build
```

## Quick Start

```bash
# Start a monitored task
agentctl start my-training --dir /data/proj --goal "Train model" -- python train.py --epochs 10

# List tasks
agentctl list

# Launch the dashboard
agentctl serve --host 0.0.0.0

# Open http://<server-ip>:8790 in your browser
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `agentctl start <name> --dir <dir> [--goal G] [--criteria C] -- <cmd...>` | Start a monitored task |
| `agentctl init <name> --dir <dir> --goal G` | Initialize a task without a command |
| `agentctl list [--all]` | List tasks (active only, or all) |
| `agentctl status <task_id>` | Show detailed task status |
| `agentctl stop <task_id>` | Stop a task |
| `agentctl tail <task_id> [-f] [-n 100]` | Tail task log output |
| `agentctl note <task_id> "message"` | Add a progress note |
| `agentctl step <task_id> <step_id> --status done` | Update a plan step |
| `agentctl set-plan <task_id> plan.json` | Import a plan |
| `agentctl complete <task_id> --summary "..."` | Mark task completed |
| `agentctl fail <task_id> --reason "..."` | Mark task failed |
| `agentctl handoff <task_id>` | Generate handoff text |
| `agentctl serve [--host 0.0.0.0] [--port 8790]` | Start the web dashboard |
| `agentctl config` | Show current configuration |

## Task States

| State | Color | Meaning |
|-------|-------|---------|
| `running` | Green | Process active, CPU or log activity detected |
| `idle` | Yellow | Process alive but CPU < 0.5% and log not updated in 5 min |
| `completed` | Blue | Process exited cleanly |
| `failed` | Red | Process exited with error, or log contains error markers |

`has_error_hint=true` is set when the log contains `Traceback`, `ERROR`, `Failed`, or `Exception`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List all tasks |
| GET | `/api/tasks/{id}` | Task detail |
| GET | `/api/tasks/{id}/logs?lines=50` | Last N log lines |
| GET | `/api/tasks/{id}/process-tree` | Process tree |
| POST | `/api/tasks/{id}/stop` | Stop a task |
| GET | `/api/events` | SSE stream (pushes every 2s) |

## File Locations

- **Config**: `~/.agent_foreman_local/config.yaml`
- **Task state**: `~/.agent_foreman_local/tasks/{task_id}.json`
- **Logs**: `~/agent_logs/{task_id}.log`

## Security

By default, the dashboard binds to `localhost` only. For LAN access, a Bearer token is required.

```bash
# Localhost (no auth needed)
agentctl serve

# LAN access (token printed to stdout)
agentctl serve --host 0.0.0.0

# Set token via environment variable
export AGENT_FOREMAN_TOKEN="your-secret"
agentctl serve --host 0.0.0.0
```

**Key protections:**
- Task IDs validated against path traversal (`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$`)
- Symlink detection on project directories
- PID identity verification before sending signals
- Process environment (`/proc/pid/environ`) never read
- XSS-safe rendering (React auto-escaping)
- Rate limiting (120 req/min per IP)
- Atomic file writes to prevent corruption

See [SECURITY.md](SECURITY.md) for the full threat model and details.

## Architecture

```
Backend (Python FastAPI)
├── Process monitoring (psutil) — discovers running agents
├── Task management (JSON files) — structured task state
├── State machine — infers status from process + log signals
├── SSE streaming — real-time updates to frontend
└── REST API — CRUD + log + process tree endpoints

CLI (click)
├── agentctl start/init — launches subprocess with log redirect
├── agentctl list/status/stop/tail/note/step/complete/fail — task lifecycle
├── agentctl set-plan — import plan steps
├── agentctl handoff — generate handoff text for next agent session
└── agentctl serve — starts the web dashboard

Frontend (React + Vite + Tailwind)
├── Dashboard — task card grid with auto-refresh via SSE
├── Task detail — metadata, process tree, log viewer, plan steps
└── Status badges — color-coded task states
```
