# AgentStatus — Local Coding Agent Supervisor

A unified web dashboard and CLI for monitoring multiple coding agents (codex, claude, aider, gemini, pytest, npm, git, Rscript, etc.) running on a Linux server.

## Quick Start

```bash
# Install
pip install -e .

# Start a monitored task
agentctl start my-training --dir /data/proj -- python train.py --epochs 10

# List tasks
agentctl list

# Launch the dashboard
agentctl serve --host 0.0.0.0 --port 8790

# Open http://<server-ip>:8790 in your browser
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `agentctl start <name> --dir <dir> -- <cmd...>` | Start a monitored task |
| `agentctl list [--all]` | List tasks (active only, or all) |
| `agentctl status <task_id>` | Show detailed task status |
| `agentctl stop <task_id> [--signal KILL]` | Stop a task |
| `agentctl tail <task_id> [-f] [-n 100]` | Tail task log output |
| `agentctl serve [--host 0.0.0.0] [--port 8790]` | Start the web dashboard |
| `agentctl config` | Show current configuration |

## Task States

| State | Color | Meaning |
|-------|-------|---------|
| `running` | Green | Process active, CPU or log activity detected |
| `idle` | Yellow | Process alive but low CPU, no recent log activity |
| `waiting_input` | Orange | Process waiting for user input |
| `completed` | Blue | Process exited cleanly (exit code 0) |
| `failed` | Red | Process exited with error or log contains error markers |
| `unknown` | Gray | Cannot determine state |

## Architecture

```
Backend (Python FastAPI)
├── Process monitoring (psutil) — discovers running agents
├── Task management (JSON files) — structured task state
├── State machine — infers status from process + log signals
├── SSE streaming — real-time updates to frontend
└── REST API — CRUD + log + process tree endpoints

CLI (click)
├── agentctl start — launches subprocess with log redirect
├── agentctl list/status/stop/tail — task lifecycle management
└── agentctl serve — starts the web dashboard

Frontend (React + Vite + Tailwind)
├── Dashboard — task card grid with auto-refresh via SSE
├── Task detail — metadata, process tree, log viewer, notes
└── Status badges — color-coded task states
```

## File Locations

- **Config**: `~/.agent_foreman_local/config.yaml`
- **Task state**: `~/.agent_foreman_local/tasks/{task_id}.json`
- **Logs**: `~/agent_logs/{task_id}.log`

## Security

- Default bind: `127.0.0.1` (localhost only)
- Use `--host 0.0.0.0` for LAN access (requires token auth)
- Token auto-generated on first run, stored in config file
- No arbitrary shell execution via API
- Log reads restricted to configured log directory
