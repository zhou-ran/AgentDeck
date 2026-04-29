import type { DiscoveredSession, ProcessInfo } from '../types'
import { ProcessTree } from './ProcessTree'

const STATUS_LABELS: Record<string, string> = {
  needs_input: 'needs_input',
  busy: 'busy',
  testing: 'testing',
  editing: 'editing',
  searching: 'searching',
  git_ops: 'git_ops',
  running_script: 'running_script',
  idle: 'idle',
  stale: 'stale',
  error_hint: 'error',
  unknown: 'unknown',
}

const DOT_CLASS: Record<string, string> = {
  red: 'bg-red-400',
  yellow: 'bg-yellow-300',
  green: 'bg-emerald-400',
  gray: 'bg-gray-600',
}

function fmtHeartbeat(ageSec: number | null): string {
  if (ageSec === null || ageSec === undefined) return 'no-log'
  if (ageSec < 60) return `${Math.floor(ageSec)}s`
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m`
  return `${Math.floor(ageSec / 3600)}h`
}

function fmtElapsed(seconds: number | null): string {
  if (!seconds && seconds !== 0) return '-'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h${Math.floor((seconds % 3600) / 60)}m`
}

function commandOf(proc: ProcessInfo): string {
  return proc.cmdline?.join(' ') || proc.name || '-'
}

function dot(color: string) {
  return <span className={`inline-block h-2 w-2 rounded-full ${DOT_CLASS[color] || DOT_CLASS.gray}`} />
}

function agentBadge(session: DiscoveredSession): string {
  const type = (session.agent_type || 'unknown').toUpperCase()
  if (type === 'UNKNOWN') return '[UNKNOWN]'
  if ((session.agent_confidence ?? 0) < 0.8) return `[MAYBE ${type} ${(session.agent_confidence ?? 0).toFixed(2)}]`
  return `[${type}]`
}

function redact(line: string): string {
  return line
    .replace(/\bsk-[A-Za-z0-9_-]{12,}\b/g, 'sk-...[redacted]')
    .replace(/\b(api[_-]?key\s*=\s*)[^\s]+/gi, '$1[redacted]')
    .replace(/\b(authorization\s*:\s*bearer\s+)[^\s]+/gi, '$1[redacted]')
}

function subDots(session: DiscoveredSession) {
  const fg = !session.foreground?.alive
    ? 'gray'
    : session.foreground.waiting_input || ['idle', 'stale'].includes(session.status)
      ? 'yellow'
      : session.status === 'error_hint'
        ? 'red'
        : 'green'
  const bg = session.background_jobs.length === 0
    ? 'gray'
    : session.background_jobs.some(j => j.status.toLowerCase().includes('error') || j.status.toLowerCase().includes('zombie'))
      ? 'red'
      : session.background_jobs.some(j => j.job_type === 'unknown' && j.is_long_running)
        ? 'yellow'
        : 'green'
  const git = session.git_status_detail?.command_failed
    ? 'red'
    : !session.git_status_detail?.is_repo
      ? 'gray'
      : session.git_status_detail.dirty_count > 0
        ? 'yellow'
        : 'green'
  const log = session.error_hints.length > 0
    ? 'red'
    : session.heartbeat_age_sec === null || session.heartbeat_age_sec === undefined
      ? 'gray'
      : session.heartbeat_age_sec > 300
        ? 'yellow'
        : 'green'
  return { fg, bg, git, log }
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <span className="text-gray-600">{label}: </span>
      <span className="break-all font-mono text-gray-400">{value || '-'}</span>
    </div>
  )
}

export function DiscoveredCard({
  session,
  expanded,
  selected,
  onToggle,
  onAction,
}: {
  session: DiscoveredSession
  expanded: boolean
  selected: boolean
  onToggle: () => void
  onAction: (action: 'pin' | 'ignore') => void
}) {
  const root = session.root_process
  const projectName = session.project_name?.name || session.project || 'unknown'
  const shortCwd = session.short_cwd || session.project_name?.short_cwd || session.cwd
  const instruction = session.user_instruction || session.last_user_message || '未找到原始指令'
  const dots = subDots(session)
  const dirtyCount = session.git_status_detail?.dirty_count ?? session.project_status?.dirty_files?.length ?? 0
  const bgSummary = session.background_jobs.length
    ? Object.entries(session.background_jobs.reduce<Record<string, number>>((acc, job) => {
        acc[job.job_type] = (acc[job.job_type] || 0) + 1
        return acc
      }, {})).map(([kind, count]) => `${kind} x${count}`).join(', ')
    : 'none'

  return (
    <div
      className={`border bg-[#080b10] p-3 font-mono text-xs ${selected ? 'border-cyan-600' : 'border-gray-800'} ${session.is_ignored ? 'opacity-70' : ''}`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {dot(session.status_dot)}
            <span className="truncate text-sm font-semibold text-gray-100">{projectName}</span>
            <span className="text-cyan-300">{agentBadge(session)}</span>
            <span className="text-gray-500">[{STATUS_LABELS[session.status] || session.status}]</span>
            <span className="text-gray-600">{root.elapsed}</span>
            {session.is_pinned && <span className="text-yellow-300">PIN</span>}
            {session.is_ignored && <span className="text-gray-500">IGNORED</span>}
          </div>
          <div className="mt-1 truncate text-[11px] text-gray-600">{shortCwd}</div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            onClick={event => {
              event.stopPropagation()
              onAction('pin')
            }}
            className={`border px-2 py-1 text-[10px] ${session.is_pinned ? 'border-yellow-600 text-yellow-300' : 'border-gray-800 text-gray-500 hover:text-gray-300'}`}
            title={session.is_pinned ? 'unpin' : 'pin'}
          >
            P
          </button>
          <button
            onClick={event => {
              event.stopPropagation()
              onAction('ignore')
            }}
            className={`border px-2 py-1 text-[10px] ${session.is_ignored ? 'border-gray-500 text-gray-300' : 'border-gray-800 text-gray-500 hover:text-gray-300'}`}
            title={session.is_ignored ? 'restore' : '忽略；只隐藏，不 kill 进程，不删除日志或项目文件'}
          >
            {session.is_ignored ? 'RESTORE' : '忽略'}
          </button>
        </div>
      </div>

      <div className="mt-2 grid gap-1 text-gray-400">
        <div><span className="text-gray-600">activity:</span> <span className="text-gray-300">{session.current_activity || session.status_reason || '-'}</span></div>
        <div><span className="text-gray-600">prompt:</span> <span className="text-gray-300">{redact(instruction).slice(0, 180)}</span></div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
          <span>fg:{dot(dots.fg)} {session.foreground?.status || '-'}</span>
          <span>bg:{dot(dots.bg)} {bgSummary}</span>
          <span>git:{dot(dots.git)} dirty {dirtyCount}</span>
          <span>log:{dot(dots.log)} {fmtHeartbeat(session.heartbeat_age_sec)}</span>
          <span>pid {root.pid}</span>
          <span>cpu {session.cpu_percent.toFixed(1)}</span>
          <span>mem {session.memory_percent.toFixed(1)}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3 border-t border-gray-800 pt-3 text-[10px] text-gray-500">
          <div className="grid gap-1 md:grid-cols-2">
            <DetailRow label="cwd" value={session.cwd} />
            <DetailRow label="project_key" value={session.project_key} />
            <DetailRow label="command" value={commandOf(root)} />
            <DetailRow label="pid/ppid/user" value={`${root.pid}/${root.ppid}/${root.user || '-'}`} />
            <DetailRow label="agent reason" value={session.agent_detection_reason} />
            <DetailRow label="session file" value={session.source_file || session.instruction?.source_file || '-'} />
          </div>

          {session.agent_detection_evidence?.length > 0 && (
            <div>
              <div className="mb-1 text-gray-500">Detection evidence</div>
              <div className="space-y-0.5 text-gray-400">
                {session.agent_detection_evidence.map(item => <div key={item}>{item}</div>)}
              </div>
            </div>
          )}

          <div>
            <div className="mb-1 text-gray-500">Foreground Agent</div>
            <div className="grid gap-1 border border-gray-800 p-2 text-gray-400 md:grid-cols-5">
              <span>PID {session.foreground?.pid ?? '-'}</span>
              <span>TTY {session.foreground?.tty || '-'}</span>
              <span>Status {session.foreground?.status || '-'}</span>
              <span>Wait {session.foreground?.waiting_input ? 'yes' : 'no'}</span>
              <span className="truncate">CMD {session.foreground?.cmd || '-'}</span>
            </div>
          </div>

          {session.background_jobs?.length > 0 && (
            <div>
              <div className="mb-1 text-gray-500">Background Jobs</div>
              <div className="overflow-auto border border-gray-800">
                <table className="w-full text-left">
                  <thead className="text-gray-600">
                    <tr>
                      <th className="px-2 py-1">Type</th>
                      <th className="px-2 py-1">PID</th>
                      <th className="px-2 py-1">Elapsed</th>
                      <th className="px-2 py-1">CPU</th>
                      <th className="px-2 py-1">MEM</th>
                      <th className="px-2 py-1">Command</th>
                      <th className="px-2 py-1">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.background_jobs.map(job => (
                      <tr key={job.pid} className="border-t border-gray-900 text-gray-400">
                        <td className="px-2 py-1">{job.job_type}</td>
                        <td className="px-2 py-1">{job.pid}</td>
                        <td className="px-2 py-1">{fmtElapsed(job.elapsed_sec)}</td>
                        <td className="px-2 py-1">{job.cpu.toFixed(1)}</td>
                        <td className="px-2 py-1">{job.mem.toFixed(1)}</td>
                        <td className="px-2 py-1">{job.cmd}</td>
                        <td className="px-2 py-1">{job.status || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {session.project_status?.dirty_files?.length > 0 && (
            <div>
              <div className="mb-1 text-gray-500">Git changed files</div>
              <div className="space-y-0.5 text-gray-400">
                {session.project_status.dirty_files.slice(0, 10).map(file => <div key={file}>{file}</div>)}
              </div>
            </div>
          )}

          <div>
            <div className="mb-1 text-gray-500">Process tree</div>
            <ProcessTree tree={root} />
          </div>

          {session.recent_logs?.length > 0 && (
            <div>
              <div className="mb-1 text-gray-500">Logs tail</div>
              <pre className="max-h-40 overflow-auto border border-gray-800 bg-gray-950 p-2 text-[10px] text-gray-300 whitespace-pre-wrap break-all">
                {session.recent_logs.map(redact).join('\n')}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
