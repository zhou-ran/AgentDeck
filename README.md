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

### Watch Live Agent Sessions

AgentDeck also auto-discovers interactive and background agent sessions that were not started by `agentdeck start`. The web UI groups them by current status, foreground/background work, git state, recent logs, and project directory. Use pin/ignore actions to keep important sessions visible and hide noisy long-running processes.

## CLI Reference

| Command | Description |
|---------|-------------|
| `agentdeck serve [--host H] [--port P]` | Start the web dashboard |
| `agentdeck start <name> --dir <dir> [--goal G] [--criteria C] -- <cmd...>` | Start a monitored task |
| `agentdeck init <name> --dir <dir> --goal G` | Initialize a task without a command |
| `agentdeck list [--all]` | List tasks |
| `agentdeck status <task_id>` | Show detailed task status |
| `agentdeck tail <task_id> [-f] [-n 100]` | Tail log output |
| `agentdeck discover` | Print auto-discovered live agent sessions |
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
make dev       # Backend on :9797 + Frontend on :5173 concurrently
make test      # Run pytest
make build-frontend  # Build frontend
make clean     # Clean build artifacts
```

## Status Model

Managed tasks started by `agentdeck start` use persisted task states:

| State | Color | Meaning |
|-------|-------|---------|
| `running` | Green | Process active, CPU or log activity |
| `busy` / `editing` / `searching` / `testing` / `git_ops` / `running_script` | Green/Blue | Current inferred activity |
| `needs_input` / `waiting_input` | Orange | Agent likely needs user input |
| `waiting` / `idle` / `stale` | Yellow/Gray | Process alive but quiet or old |
| `error_hint` | Red | Log or session output contains an error signal |
| `completed` | Blue | Process exited cleanly |
| `failed` | Red | Process exited with error or error in log |
| `unknown` | Gray | Status cannot be inferred |

Auto-discovered live sessions use the same activity vocabulary plus session-specific fields such as foreground agent status, background jobs, heartbeat age, git details, pin state, and ignore state.

## API Reference

| Endpoint | Purpose |
|----------|---------|
| `/api/tasks` | Managed task CRUD, plans, steps, notes, handoff, logs, process tree |
| `/api/discover` | Auto-scan live agent sessions |
| `/api/events` | SSE stream, refreshed every 2 seconds |
| `/api/pins` | List/create/delete pin rules |
| `/api/ignored` | List/create/delete/restore ignore rules |
| `/api/sessions/{session_id}/pin` | Pin a discovered session |
| `/api/sessions/{session_id}/ignore` | Ignore a discovered session |
| `/api/system-metrics` | System CPU, memory, disk, and network overview |

## File Locations

| What | Path |
|------|------|
| Config | `~/.agentdeck/config.yaml` |
| Task state | `~/.agentdeck/tasks/{task_id}.json` |
| Pin rules | `~/.agentdeck/pins.json` |
| Ignore rules | `~/.agentdeck/ignored.json` |
| Logs | `~/agent_logs/{task_id}.log` |
| systemd service | `~/.config/systemd/user/agentdeck.service` |

## Security

- Default bind: `127.0.0.1` (localhost only)
- Token auth for LAN access
- Path traversal prevention
- Process env never read
- No browser command execution endpoint
- No stop/kill API endpoint; CLI process actions verify task/PID identity first
- Rate limiting (120 req/min)
- Atomic file writes

See [SECURITY.md](SECURITY.md) for the full threat model.

## Acknowledgements

AgentDeck is inspired by and built upon ideas from [agent-foreman](https://github.com/operoncao123/agent-foreman) by [operoncao123](https://github.com/operoncao123). Thank you for the original concept and foundation.

---

<details>
<summary>🤖 Agent Context — click to expand if you are an AI assistant</summary>

If you are an AI coding agent working on this repo, please read <a href="AGENTS.md">AGENTS.md</a> first for architecture, tech stack, key files, coding conventions, and security constraints.

</details>
