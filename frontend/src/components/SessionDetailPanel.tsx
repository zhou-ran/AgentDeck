import { useLayoutEffect, useRef } from 'react'
import type { DiscoveredSession } from '../types'
import { AgentBadge } from './AgentBadge'
import { HandoffPanel, type HandoffData } from './HandoffPanel'
import { HealthIndicator } from './HealthIndicator'
import { LogViewer } from './LogViewer'
import { ProcessTree } from './ProcessTree'
import { RiskHints } from './RiskHints'
import { StatusDot, statusLabel } from './StatusDot'
import { TaskTimeline, buildSessionTimeline } from './TaskTimeline'
import { getProjectName } from '../utils/agentIdentity'
import { getSessionHealth } from '../utils/health'
import { getSessionRiskHints } from '../utils/risks'

function redact(line: string): string {
  return line
    .replace(/\bsk-[A-Za-z0-9_-]{12,}\b/g, 'sk-...[redacted]')
    .replace(/\b(api[_-]?key\s*=\s*)[^\s]+/gi, '$1[redacted]')
    .replace(/\b(authorization\s*:\s*bearer\s+)[^\s]+/gi, '$1[redacted]')
}

function fmtElapsed(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 60) return `${Math.floor(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

export function SessionDetailPanel({
  session,
  onClose,
  onAction,
}: {
  session: DiscoveredSession | null
  onClose: () => void
  onAction: (session: DiscoveredSession, action: 'pin' | 'ignore') => void
}) {
  const panelRef = useRef<HTMLElement>(null)

  useLayoutEffect(() => {
    panelRef.current?.scrollTo({ top: 0 })
  }, [session?.session_id])

  if (!session) {
    return (
      <aside className="glass-panel-strong hidden min-h-[560px] rounded-[22px] p-5 xl:block">
        <div className="text-sm font-semibold text-app">Session Detail</div>
        <div className="mt-2 text-sm text-muted">Select a live session to inspect instruction, project state, logs, and process tree.</div>
      </aside>
    )
  }

  const projectName = getProjectName(session)
  const instruction = redact(session.user_instruction || session.last_user_message || '未找到原始指令')
  const dirtyFiles = session.project_status?.dirty_files || session.git_status_detail?.changed_files || []
  const recentFiles = session.recent_files || session.project_status?.recent_files || []
  const errors = session.error_hints || []
  const health = getSessionHealth(session)
  const risks = getSessionRiskHints(session)
  const timeline = buildSessionTimeline(session)
  const draftHandoff = buildSessionHandoff(session, dirtyFiles)

  return (
    <aside ref={panelRef} className="glass-panel-strong h-full max-h-[calc(100vh-112px)] overflow-auto rounded-[22px] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusDot status={session.status_dot || session.status} />
            <AgentBadge type={session.agent_type} confidence={session.agent_confidence} session={session} />
            {session.is_pinned && <span className="rounded-full bg-yellow-500/10 px-2 py-0.5 text-[11px] text-yellow-700 dark:text-yellow-300">Pinned</span>}
          </div>
          <h2 className="mt-3 truncate text-xl font-semibold tracking-tight text-app">{projectName}</h2>
          <div className="mt-1 truncate text-sm text-muted">{session.short_cwd || session.cwd}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-[var(--border)] px-3 py-1 text-sm text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10"
        >
          Close
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Metric label="State" value={statusLabel(session.status)} />
        <Metric label="Elapsed" value={fmtElapsed(session.elapsed_sec)} />
        <Metric label="CPU" value={`${session.cpu_percent.toFixed(1)}%`} />
        <Metric label="Memory" value={`${session.memory_percent.toFixed(1)}%`} />
      </div>

      <section className="mt-5">
        <HealthIndicator health={health} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Risk Hints" />
        <RiskHints hints={risks} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Current Activity" />
        <div className="quiet-panel rounded-2xl p-3 text-sm text-app">{session.current_activity || session.status_reason || '-'}</div>
      </section>

      <section className="mt-5">
        <SectionTitle title="Session Context" detail={session.source_file ? 'from session' : undefined} />
        <SessionContext session={session} />
      </section>

      <section className="mt-5">
        <SectionTitle title="User Instruction" detail={session.instruction_source || session.instruction?.source || undefined} />
        <div className="quiet-panel max-h-36 overflow-auto rounded-2xl p-3 text-sm leading-relaxed text-app">{instruction}</div>
      </section>

      <section className="mt-5">
        <SectionTitle title="Project Status" />
        <div className="space-y-2">
          <InfoLine label="Branch" value={session.git_status_detail?.branch || session.project_status?.branch || '-'} />
          <InfoLine label="Dirty files" value={String(session.git_status_detail?.dirty_count ?? dirtyFiles.length)} />
          <InfoLine label="Foreground" value={`${session.foreground?.status || '-'} ${session.foreground?.waiting_input ? '(waiting input)' : ''}`} />
          <InfoLine label="Background jobs" value={String(session.background_jobs?.length || 0)} />
        </div>
      </section>

      {errors.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Error Hints" />
          <div className="space-y-2">
            {errors.slice(0, 5).map((error, index) => (
              <div key={`${error}-${index}`} className="rounded-2xl border border-red-500/20 bg-red-500/[0.08] p-3 text-sm text-red-700 dark:text-red-300">
                {redact(error)}
              </div>
            ))}
          </div>
        </section>
      )}

      {dirtyFiles.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Changed Files" detail={`${dirtyFiles.length}`} />
          <div className="quiet-panel max-h-36 overflow-auto rounded-2xl p-3 mono text-xs text-app">
            {dirtyFiles.slice(0, 12).map(file => <div key={file} className="truncate">{file}</div>)}
          </div>
        </section>
      )}

      {recentFiles.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Recent Files" />
          <div className="quiet-panel max-h-28 overflow-auto rounded-2xl p-3 mono text-xs text-app">
            {recentFiles.slice(0, 8).map(file => <div key={file} className="truncate">{file}</div>)}
          </div>
        </section>
      )}

      <section className="mt-5">
        <SectionTitle title="Timeline" />
        <TaskTimeline events={timeline} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Handoff" />
        <HandoffPanel data={draftHandoff} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Live Logs" />
        <LogViewer lines={(session.recent_logs || []).map(redact)} height="240px" />
      </section>

      <section className="mt-5">
        <SectionTitle title="Process Tree" />
        <ProcessTree tree={session.root_process} />
      </section>

      <div className="sticky bottom-0 -mx-5 mt-5 flex gap-2 border-t border-[var(--border)] bg-[var(--surface-strong)] px-5 py-4 backdrop-blur-xl">
        <button
          type="button"
          onClick={() => onAction(session, 'pin')}
          className="flex-1 rounded-full border border-[var(--border)] px-3 py-2 text-sm font-medium text-app transition hover:bg-black/5 dark:hover:bg-white/10"
        >
          {session.is_pinned ? 'Unpin' : 'Pin'}
        </button>
        <button
          type="button"
          onClick={() => onAction(session, 'ignore')}
          className="flex-1 rounded-full border border-[var(--border)] px-3 py-2 text-sm font-medium text-app transition hover:bg-black/5 dark:hover:bg-white/10"
          title="Hide only. Does not stop processes or delete files."
        >
          {session.is_ignored ? 'Restore' : 'Ignore'}
        </button>
      </div>
    </aside>
  )
}

function SectionTitle({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      {detail && <div className="truncate text-xs text-muted">{detail}</div>}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="text-[11px] font-medium text-muted">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-app">{value}</div>
    </div>
  )
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl bg-black/[0.03] px-3 py-2 text-sm dark:bg-white/[0.04]">
      <span className="text-muted">{label}</span>
      <span className="min-w-0 truncate text-right text-app">{value}</span>
    </div>
  )
}

function SessionContext({ session }: { session: DiscoveredSession }) {
  const messages = session.conversation || []
  const hasRuntime = session.foreground?.cmd || session.active_commands.length > 0 || session.background_jobs.length > 0

  if (messages.length === 0 && !session.recent_output && !session.last_user_message && !hasRuntime) {
    return <div className="quiet-panel rounded-2xl p-3 text-sm text-muted">No structured session context is available yet.</div>
  }

  return (
    <div className="space-y-3">
      {messages.length > 0 ? (
        <div className="quiet-panel max-h-64 space-y-2 overflow-auto rounded-2xl p-3">
          {messages.slice(-8).map((message, index) => (
            <div key={`${message.ts || index}-${message.role}`} className="rounded-xl bg-white/45 px-3 py-2 text-sm shadow-sm">
              <div className="mb-1 flex items-center justify-between gap-3">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{contextRoleLabel(message.role)}</span>
                {message.ts && <span className="shrink-0 text-[10px] text-muted">{new Date(message.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
              </div>
              <div className="whitespace-pre-wrap break-words text-app">{redact(message.text)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="quiet-panel rounded-2xl p-3 text-sm text-app">
          {session.last_user_message && <div><span className="text-muted">Last user:</span> {redact(session.last_user_message)}</div>}
          {session.recent_output && <div className="mt-2"><span className="text-muted">Recent agent:</span> {redact(session.recent_output)}</div>}
        </div>
      )}

      <div className="quiet-panel space-y-2 rounded-2xl p-3 text-xs">
        <RuntimeLine label="Foreground" value={session.foreground?.cmd || session.root_cmd || '-'} />
        {session.active_commands.slice(0, 4).map(command => (
          <RuntimeLine key={command} label="Command" value={command} />
        ))}
        {session.background_jobs.slice(0, 4).map(job => (
          <RuntimeLine key={`${job.pid}-${job.cmd}`} label={job.job_type || 'Background'} value={`${job.cmd || `pid ${job.pid}`} · ${job.status || 'running'}`} />
        ))}
      </div>
    </div>
  )
}

function RuntimeLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[82px_minmax(0,1fr)] gap-2">
      <span className="text-muted">{label}</span>
      <span className="truncate mono text-muted-strong" title={value}>{value}</span>
    </div>
  )
}

function contextRoleLabel(role: string): string {
  if (role === 'user') return 'User'
  if (role === 'assistant') return 'Agent'
  if (role === 'tool') return 'Tool'
  return role || 'Context'
}

function buildSessionHandoff(session: DiscoveredSession, dirtyFiles: string[]): HandoffData | null {
  const logs = (session.recent_logs || []).slice(-12)
  const hasUsefulMetadata = session.user_instruction || session.current_activity || dirtyFiles.length > 0 || logs.length > 0 || session.error_hints.length > 0
  if (!hasUsefulMetadata) return null

  return {
    draft: true,
    summary: session.current_activity || session.status_reason || 'Session is visible in AgentDeck, but no structured handoff has been generated by the backend.',
    whatChanged: dirtyFiles.length > 0 ? ['Detected changed files in the current worktree.'] : undefined,
    filesTouched: dirtyFiles.slice(0, 10),
    commands: session.active_commands?.slice(0, 6),
    tests: logs.some(line => /\b(pytest|npm test|vitest|test)\b/i.test(line)) ? 'A test command appears in visible logs.' : 'No test command was observed in visible metadata.',
    blockers: session.error_hints?.slice(0, 3),
    suggestedNextPrompt: `Continue this ${session.agent_type || 'agent'} session in ${getProjectName(session)}. Review the current activity, changed files, and any risk hints before asking for the next implementation step.`,
    generatedAt: new Date().toISOString(),
  }
}
