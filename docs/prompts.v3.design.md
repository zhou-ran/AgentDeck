# prompts.v3 implementation design

## 1. Borrowed from agent-foreman

- Card-based dashboard layout with summary counters and per-session cards.
- Status lanes for `Needs Input`, `Working`, `Errors`, and `Slacking`.
- Session-file parsing concepts for Codex and Claude JSONL logs.
- Heartbeat-driven activity inference from session/log modification time.
- Prominent display of recent output, pending items, and the latest user message.
- Silent SSE refresh that updates state without replacing the whole page.

## 2. Removed or not implemented

- Remote SSH host management.
- SSH credential/key/password storage.
- `credentials.enc.json` and master-password flows.
- Browser-to-terminal command or chat injection.
- `ptrace`, `TIOCSTI`, and any `ptrace_scope` guidance.
- macOS remote-login support.
- PID import, stop, kill, and arbitrary-command API endpoints.

## 3. Data model

- `DiscoveredSession`: one live local agent session grouped by cwd/project.
- `ProcessInfo`: PID, PPID, user, cwd, command, resource usage, elapsed time, and child tree.
- `ProjectNameInfo`: display project name, short cwd, git root, and branch.
- `InstructionInfo`: extracted user instruction, source file, source type, and confidence.
- `ProjectRuntimeStatus`: read-only git status, dirty files, recent files, and test status placeholder.
- `ActivityTimelineItem`: heartbeat and child-process events for detail views.

## 4. API design

- `GET /api/discover`: read-only list of current local agent sessions.
- `GET /api/discover/{session_id}`: read-only details for one discovered session.
- `GET /api/events`: SSE stream containing managed tasks, discovered sessions, and system metrics.
- `GET /api/system-metrics`: read-only system metrics.
- Existing task/plan/log endpoints remain for locally started monitored tasks.
- No API endpoint imports a PID, stops a process, kills a process, injects input, or executes arbitrary shell.

## 5. UI structure

- Header: `本地牛马监工台 / Local Agent Foreman`.
- Summary cards: all agents, needs input, working, testing, idle/slacking, errors.
- Search and filters by project, agent type, status, cwd, instruction, and recent output.
- Live Agent Sessions as the default page content.
- Sessions grouped by lane and rendered as project-first cards.
- Expandable details show cwd, command, process tree, session file, source/confidence, git files, recent files, active commands, and log tail.

## 6. Implementation steps

1. Keep the product local/LAN only and remove old remote/control surface from the user-facing API and CLI.
2. Implement local process discovery for Codex, Claude, Kimi, Aider, and Gemini root processes.
3. Add session parsers and session matching for Codex, Claude, and Kimi-style logs.
4. Add read-only project/git enrichment with a strict command whitelist and subprocess timeout.
5. Add activity inference with explicit `status_reason` and human-readable `current_activity`.
6. Rework the dashboard into a Chinese card-based Live Agent Sessions view.
7. Verify with backend tests and frontend production build.
