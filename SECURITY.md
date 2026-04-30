# Security — AgentDeck

## Threat Model

AgentDeck runs on a shared Linux server where multiple users may have login access, and coding agents may handle sensitive data (API keys, SSH keys, research data). The primary attack surface is the web dashboard.

### Assets to Protect

| Asset | Risk | Mitigation |
|-------|------|------------|
| API keys / env vars | Exposure via `/proc/pid/environ` | Never read process environment |
| SSH keys / credentials | Path traversal to read arbitrary files | Strict task_id regex, path validation |
| Research data | Symlink following to sensitive dirs | Symlink detection, sensitive-dir blocklist |
| Running processes | Arbitrary process kill via PID spoofing | PID identity verification before SIGTERM |
| Web dashboard | XSS via log output or task names | React auto-escaping, no `dangerouslySetInnerHTML` |
| API endpoints | Brute-force or DoS | Rate limiting (120 req/min) |
| Network | Unauthorized LAN access | Token auth for non-localhost, localhost bypass for dashboard |

### Attacker Scenarios

1. **Malicious task_id with path traversal** (`../../etc/passwd`)
   - Blocked by regex: `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$`

2. **Symlink in project_dir pointing to /etc or /root**
   - `is_safe_project_dir()` resolves symlinks and checks against blocklist

3. **PID reuse attack** (process dies, new process gets same PID, attacker triggers kill)
   - `verify_pid_for_task()` checks command and CWD match before sending signal

4. **Log path traversal** (`../../etc/shadow.log`)
   - `is_safe_log_path()` validates path is under allowed log directory

5. **Environment variable leakage**
   - `process_scanner._proc_to_info()` explicitly uses `as_dict()` with whitelist, never reads `/proc/pid/environ`

6. **Stored XSS via progress notes**
   - `sanitize_note()` strips HTML tags
   - React renders text content with `{variable}` (auto-escaped)

7. **CSRF / unauthorized API access**
   - Token-based auth via `Authorization: Bearer <token>` header
   - Auto-generated on first run, stored in config
   - Skipped for localhost (dashboard in browser)

## Fixed Security Issues

### 1. Default Binding (HIGH)
- **Before**: Default bind to `0.0.0.0`
- **After**: Default bind to `127.0.0.1`; warning printed when binding to non-localhost

### 2. Token Authentication (HIGH)
- **Before**: No authentication
- **After**: Bearer token required for non-localhost access. Token sourced from `AGENTDECK_TOKEN` env var (legacy `AGENT_FOREMAN_TOKEN` also supported), config file, or auto-generated.

### 3. Arbitrary Shell Access (HIGH)
- **Before**: No validation on project_dir or command
- **After**: `is_safe_project_dir()` rejects symlinks, sensitive dirs, path traversal. Command is taken as-is (user controls their own agents) but project_dir is validated.

### 4. Path Traversal in task_id (HIGH)
- **Before**: task_id used directly in file paths
- **After**: Strict regex validation `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$`

### 5. PID Spoofing / Kill (MEDIUM)
- **Before**: `os.kill(pid)` without verification
- **After**: `verify_pid_for_task()` checks process command and CWD match before sending signal. CLI process actions enforce this; the web API does not expose a stop/kill endpoint.

### 6. Environment Variable Leakage (MEDIUM)
- **Before**: Not explicitly addressed
- **After**: `_proc_to_info()` uses `proc.as_dict(attrs=[...])` with explicit whitelist. Comment documents that `proc.environ()` is never read.

### 7. Log Path Traversal (MEDIUM)
- **Before**: No validation on log path construction
- **After**: `is_safe_log_path()` validates log path is under the configured log directory

### 8. XSS in Log Viewer (MEDIUM)
- **Before**: Not explicitly checked
- **After**: Verified — React renders log lines as `{line}` (auto-escaped). No `dangerouslySetInnerHTML` or `innerHTML` usage.

### 9. Symlink Following (MEDIUM)
- **Before**: No symlink checks
- **After**: `is_safe_project_dir()` uses `Path.resolve()` and checks against sensitive directory blocklist

### 10. Race Condition in File Writes (LOW)
- **Before**: Direct `path.write_text()` could corrupt on crash
- **After**: `atomic_write()` uses temp file + `os.replace()` for crash-safe writes

### 11. Rate Limiting (LOW)
- **Before**: No rate limiting
- **After**: Sliding window rate limiter (120 requests/minute per IP)

### 12. CORS Policy (LOW)
- **Before**: `allow_origins=["*"]`
- **After**: Restricted to localhost origins only

### 13. Security Headers (LOW)
- **Before**: No security headers
- **After**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP, Referrer-Policy, Permissions-Policy

### 14. Log Injection via Notes (LOW)
- **Before**: Notes stored as-is
- **After**: `sanitize_note()` strips HTML tags and limits length

## Configuration

### Token

```bash
# Option 1: Environment variable (recommended for scripts)
export AGENTDECK_TOKEN="your-secret-token"
# Legacy name also supported:
# export AGENT_FOREMAN_TOKEN="your-secret-token"

# Option 2: Config file (~/.agentdeck/config.yaml)
token: your-secret-token

# Option 3: Auto-generated (first run)
# Token is printed to stdout and saved to config
```

### Network Binding

```bash
# Localhost only (default, recommended)
agentdeck serve

# LAN access (requires token)
agentdeck serve --host 0.0.0.0 --port 9797
# Token will be printed to stdout
```

## Residual Risks

1. **Token in config file**: Token stored in plaintext in `~/.agentdeck/config.yaml`. Mitigate by setting `AGENTDECK_TOKEN` env var instead.

2. **Localhost auth bypass**: Dashboard access from localhost has no auth. On shared servers, any local user can access the dashboard. Mitigate by binding to a Unix socket with filesystem permissions.

3. **Process cmdline visible**: Process command lines are visible to all users via `ps`. This may leak file paths or arguments. No mitigation available without OS-level changes.

4. **Log files readable**: Log files are stored in `~/agent_logs/` with default permissions. Other users on the system may read them if umask is permissive. Mitigate by setting `chmod 700 ~/agent_logs/`.
