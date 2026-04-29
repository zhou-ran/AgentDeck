# AgentStatus

A local dashboard for monitoring coding agents on your Linux server.

If you run multiple agents (Codex, Claude, Aider, Gemini, pytest, npm, git, Rscript, ...) on the same machine and keep switching terminal tabs to check on them — this tool gives you a single web page to see what's happening.

---

## Get Started

### Install

```bash
git clone <repo-url>
cd agentstatus
make install
```

Or with [pipx](https://pipx.pypa.io/) (isolated environment):

```bash
pipx install .
```

### First Run

```bash
agent-foreman-local serve
```

Open http://127.0.0.1:9797 in your browser. That's it.

---

## Everyday Usage

### Start monitoring a task

```bash
agent-foreman-local start my-training \
  --dir /data/project \
  -- python train.py --epochs 10
```

This creates a task entry, launches the process, and captures its output to a log file. The dashboard will show it immediately.

### Check what's running

```bash
agent-foreman-local list
```

Or just look at the dashboard — it updates every 2 seconds.

### Watch a task's output

```bash
agent-foreman-local tail my-training -f
```

### Stop a task

```bash
agent-foreman-local stop my-training
```

### Import a process that's already running

Started something outside of AgentStatus? Bring it in:

```bash
agent-foreman-local import-pid 12345 --name my-codex-session
```

### Add notes or update progress

```bash
# Jot a note
agent-foreman-local note my-training "Epoch 3 done, loss=0.042"

# Update a plan step
agent-foreman-local step my-training step-1 --status done

# Mark the whole task done
agent-foreman-local complete my-training --summary "Model converged at 96.2% accuracy"
```

---

## Task States

| State | What it means |
|-------|---------------|
| **running** (green) | Process is alive and doing work |
| **idle** (yellow) | Process is alive but quiet (low CPU, no log updates for 5 min) |
| **waiting_input** (orange) | Process is waiting for user input |
| **completed** (blue) | Exited cleanly |
| **failed** (red) | Exited with an error, or the log contains error patterns |

---

## LAN Access

By default, the dashboard only listens on `127.0.0.1`. To access it from another machine on your network:

```bash
agent-foreman-local serve --host 0.0.0.0
```

A token will be printed to the terminal. Use it to authenticate:

```bash
curl -H "Authorization: Bearer <token>" http://<your-ip>:9797/api/tasks
```

To set a fixed token:

```bash
export AGENT_FOREMAN_TOKEN="my-secret"
agent-foreman-local serve --host 0.0.0.0
```

---

## Configuration

The config file lives at `~/.agent_foreman_local/config.yaml`. A minimal example:

```yaml
host: "127.0.0.1"    # Use "0.0.0.0" for LAN access
port: 9797
# token: "your-secret-token"   # Auto-generated if not set
log_dir: "~/agent_logs"
tasks_dir: "~/.agent_foreman_local/tasks"
```

See [config.example.yaml](config.example.yaml) for the full template.

---

## Run as a systemd Service

To have the dashboard start automatically on boot:

```bash
# Install and enable
agent-foreman-local install-service --enable

# Manage
systemctl --user start agent-foreman-local
systemctl --user status agent-foreman-local
journalctl --user -u agent-foreman-local -f

# Remove
agent-foreman-local uninstall-service
```

---

## Development

```bash
make dev              # Run backend + frontend dev servers concurrently
make test             # Run the test suite
make build-frontend   # Rebuild the frontend
make clean            # Remove build artifacts
```

The dev mode starts:
- Backend at http://localhost:9797 (with hot-reload)
- Frontend at http://localhost:5173 (Vite dev server, proxies API to backend)

---

## Security

- Binds to `127.0.0.1` by default — no network exposure unless you opt in
- Token authentication for LAN access
- Path traversal prevention, PID verification, rate limiting (120 req/min)
- Process environment is never read

See [SECURITY.md](SECURITY.md) for the full threat model.

---

## CLI Reference

`agent-foreman-local` is the main command. `agentctl` is a shorthand alias.

| Command | Description |
|---------|-------------|
| `serve [--host H] [--port P]` | Start the web dashboard |
| `start <name> --dir <dir> -- <cmd...>` | Launch and monitor a process |
| `init <name> --dir <dir> --goal "..."` | Create a task entry without starting a process |
| `list [--all]` | List tasks (active only, or all) |
| `status <task_id>` | Show detailed status of a task |
| `tail <task_id> [-f]` | Stream or print task log output |
| `stop <task_id>` | Stop a running task |
| `note <task_id> "..."` | Add a note to a task |
| `step <task_id> <step_id> --status done` | Update a plan step's status |
| `set-plan <task_id> plan.json` | Import a plan from a JSON file |
| `complete <task_id> --summary "..."` | Mark a task as completed |
| `fail <task_id> --reason "..."` | Mark a task as failed |
| `handoff <task_id>` | Generate handoff summary text |
| `import-pid <pid> --name <name>` | Import an existing process |
| `discover` | Auto-detect running agent processes |
| `config` | Print current configuration |
| `install-service [--enable]` | Install systemd user service |
| `uninstall-service` | Remove systemd user service |

---

## Project Structure

```
backend/           Python + FastAPI server
  api/             REST endpoints, SSE stream, auth
  cli.py           Click-based CLI
  task_manager.py  Task CRUD + state enrichment
  process_scanner.py  psutil-based process discovery
  state_machine.py    Status inference logic
  main.py          FastAPI app entry point

frontend/          React 19 + TypeScript + Vite
  src/components/  Dashboard, TaskCard, LogViewer, etc.
  src/hooks/       SSE connection with auto-reconnect

tests/             pytest test suite
scripts/           Demo scripts
docs/              Design prompts, review reports
```

---

## License

MIT
