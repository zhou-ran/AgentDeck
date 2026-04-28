# AgentStatus — Local Coding Agent Supervisor

A unified web dashboard and CLI for monitoring coding agents
(codex, claude, aider, gemini, pytest, npm, git, etc.) on a Linux server.

## Quick Start

### One-click Install

```bash
git clone <repo>
cd agentstatus
make install
```

Or via pipx:
```bash
pipx install .
```

### Start the Dashboard

```bash
agent-foreman-local serve
# -> http://127.0.0.1:8787
```

### Start a Monitored Task

```bash
agent-foreman-local start my-training \
  --dir /data/project \
  --goal "Train model" \
  -- python train.py --epochs 10
```

### Watch Logs

```bash
agent-foreman-local tail my-training -f
```

### Stop a Task

```bash
agent-foreman-local stop my-training
```

### Import an Existing Process

```bash
agent-foreman-local import-pid 12345 --name my-codex-session
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `agent-foreman-local serve [--host H] [--port P]` | Start the web dashboard |
| `agent-foreman-local start <name> --dir <dir> [--goal G] [--criteria C] -- <cmd...>` | Start a monitored task |
| `agent-foreman-local init <name> --dir <dir> --goal G` | Initialize a task without a command |
| `agent-foreman-local list [--all]` | List tasks |
| `agent-foreman-local status <task_id>` | Show detailed task status |
| `agent-foreman-local stop <task_id> [--signal KILL]` | Stop a task |
| `agent-foreman-local tail <task_id> [-f] [-n 100]` | Tail log output |
| `agent-foreman-local note <task_id> "message"` | Add a progress note |
| `agent-foreman-local step <task_id> <step_id> --status done` | Update a plan step |
| `agent-foreman-local set-plan <task_id> plan.json` | Import a plan |
| `agent-foreman-local complete <task_id> --summary "..."` | Mark task completed |
| `agent-foreman-local fail <task_id> --reason "..."` | Mark task failed |
| `agent-foreman-local handoff <task_id>` | Generate handoff text |
| `agent-foreman-local config` | Show current configuration |
| `agent-foreman-local install-service [--enable]` | Install systemd user service |
| `agent-foreman-local uninstall-service` | Remove systemd user service |

> `agentctl` is an alias for `agent-foreman-local` for backward compatibility.

## LAN Access

By default, the dashboard binds to `127.0.0.1` (localhost only).

For LAN access:
```bash
agent-foreman-local serve --host 0.0.0.0 --port 8787
# Token is printed to stdout
# Use: curl -H "Authorization: Bearer <token>" http://<ip>:8787/api/tasks
```

Set a custom token:
```bash
export AGENT_FOREMAN_TOKEN="my-secret"
agent-foreman-local serve --host 0.0.0.0
```

## Token Configuration

1. **Environment variable** (recommended):
   ```bash
   export AGENT_FOREMAN_TOKEN="your-secret"
   ```

2. **Config file** (`~/.agent_foreman_local/config.yaml`):
   ```yaml
   token: your-secret
   ```

3. **Auto-generated** on first `serve` run.

## Auto-start with systemd

```bash
# Install service
agent-foreman-local install-service --enable

# Manage
systemctl --user start agent-foreman-local
systemctl --user stop agent-foreman-local
systemctl --user status agent-foreman-local
journalctl --user -u agent-foreman-local -f

# Uninstall
agent-foreman-local uninstall-service
```

## Development

```bash
make dev       # Backend (--reload) + Frontend (vite dev) concurrently
make test      # Run pytest
make build-frontend  # Build frontend
make clean     # Clean build artifacts
```

## Task States

| State | Color | Meaning |
|-------|-------|---------|
| `running` | Green | Process active, CPU or log activity |
| `idle` | Yellow | Process alive, CPU < 0.5%, log stale 5 min |
| `waiting_input` | Orange | Process waiting for user input |
| `completed` | Blue | Process exited cleanly |
| `failed` | Red | Process exited with error or error in log |

## File Locations

| What | Path |
|------|------|
| Config | `~/.agent_foreman_local/config.yaml` |
| Task state | `~/.agent_foreman_local/tasks/{task_id}.json` |
| Logs | `~/agent_logs/{task_id}.log` |
| systemd service | `~/.config/systemd/user/agent-foreman-local.service` |

## Security

- Default bind: `127.0.0.1` (localhost only)
- Token auth for LAN access
- Path traversal prevention
- PID verification before kill
- Process env never read
- Rate limiting (120 req/min)
- Atomic file writes

See [SECURITY.md](SECURITY.md) for the full threat model.

## Architecture

```
Backend (Python 3.11+ / FastAPI)
+-- CLI (click) -- agent-foreman-local commands
+-- Task Manager -- JSON file CRUD + enrichment
+-- Process Scanner -- psutil agent discovery
+-- State Machine -- status inference
+-- Log Manager -- efficient tail + async stream
+-- SSE -- real-time push to frontend
+-- Security -- auth, path safety, rate limiting

Frontend (React 19 / TypeScript / Vite / Tailwind)
+-- Dashboard -- task grid with filters + search
+-- Task Detail -- metadata, logs, process tree, plan
+-- System Overview -- CPU, memory, disk, network
+-- SSE Hook -- auto-reconnecting event stream
```
