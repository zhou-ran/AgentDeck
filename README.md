<p align="center">
  <img src="logo.png" alt="AgentDeck Logo" width="140">
</p>

<h1 align="center">AgentDeck — Local Coding Agent Supervisor</h1>

<p align="center">
  A local/LAN web dashboard and CLI for monitoring coding agents<br>
  (codex, claude, kimi, aider, gemini, pytest, npm, git, etc.) on one machine.
</p>

## Quick Start

### One-click Install

```bash
git clone <repo>
cd agentdeck
make install
```

Or via pipx:
```bash
pipx install .
```

### Start the Dashboard

```bash
agentdeck serve
# -> http://127.0.0.1:8787
```

### Start a Monitored Task

```bash
agentdeck start my-training \
  --dir /data/project \
  --goal "Train model" \
  -- python train.py --epochs 10
```

### Watch Logs

```bash
agentdeck tail my-training -f
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `agentdeck serve [--host H] [--port P]` | Start the web dashboard |
| `agentdeck start <name> --dir <dir> [--goal G] [--criteria C] -- <cmd...>` | Start a monitored task |
| `agentdeck init <name> --dir <dir> --goal G` | Initialize a task without a command |
| `agentdeck list [--all]` | List tasks |
| `agentdeck status <task_id>` | Show detailed task status |
| `agentdeck tail <task_id> [-f] [-n 100]` | Tail log output |
| `agentdeck note <task_id> "message"` | Add a progress note |
| `agentdeck step <task_id> <step_id> --status done` | Update a plan step |
| `agentdeck set-plan <task_id> plan.json` | Import a plan |
| `agentdeck complete <task_id> --summary "..."` | Mark task completed |
| `agentdeck fail <task_id> --reason "..."` | Mark task failed |
| `agentdeck handoff <task_id>` | Generate handoff text |
| `agentdeck config` | Show current configuration |
| `agentdeck install-service [--enable]` | Install systemd user service |
| `agentdeck uninstall-service` | Remove systemd user service |

> `agentctl` is an alias for `agentdeck` for backward compatibility.

## LAN Access

By default, the dashboard binds to `127.0.0.1` (localhost only).

For LAN access:
```bash
agentdeck serve --host 0.0.0.0 --port 8787
# Token is printed to stdout
# Use: curl -H "Authorization: Bearer <token>" http://<ip>:8787/api/tasks
```

Set a custom token:
```bash
export AGENT_FOREMAN_TOKEN="my-secret"
agentdeck serve --host 0.0.0.0
```

## Token Configuration

1. **Environment variable** (recommended):
   ```bash
   export AGENT_FOREMAN_TOKEN="your-secret"
   ```

2. **Config file** (`~/.agentdeck/config.yaml`):
   ```yaml
   token: your-secret
   ```

3. **Auto-generated** on first `serve` run.

## Auto-start with systemd

```bash
# Install service
agentdeck install-service --enable

# Manage
systemctl --user start agentdeck
systemctl --user stop agentdeck
systemctl --user status agentdeck
journalctl --user -u agentdeck -f

# Uninstall
agentdeck uninstall-service
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
| Config | `~/.agentdeck/config.yaml` |
| Task state | `~/.agentdeck/tasks/{task_id}.json` |
| Logs | `~/agent_logs/{task_id}.log` |
| systemd service | `~/.config/systemd/user/agentdeck.service` |

## Security

- Default bind: `127.0.0.1` (localhost only)
- Token auth for LAN access
- Path traversal prevention
- Process env never read
- No browser command execution, PID import, stop, or kill endpoint
- Rate limiting (120 req/min)
- Atomic file writes

See [SECURITY.md](SECURITY.md) for the full threat model.

---

<details>
<summary>🤖 Agent Context — click to expand if you are an AI assistant</summary>

If you are an AI coding agent working on this repo, please read <a href="AGENTS.md">AGENTS.md</a> first for architecture, tech stack, key files, coding conventions, and security constraints.

</details>
