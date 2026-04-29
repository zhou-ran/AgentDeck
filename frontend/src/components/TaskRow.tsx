import type { DiscoveredSession } from '../types'
import { AgentBadge } from './AgentBadge'
import { HealthIndicator } from './HealthIndicator'
import { RiskHints } from './RiskHints'
import { StatusDot, statusLabel } from './StatusDot'
import { getSessionHealth } from '../utils/health'
import { getSessionRiskHints } from '../utils/risks'

function fmtElapsed(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 60) return `${Math.floor(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

function fmtLastActivity(ageSec: number | null | undefined): string {
  if (ageSec === null || ageSec === undefined) return 'No log'
  if (ageSec < 60) return 'Just now'
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m ago`
  return `${Math.floor(ageSec / 3600)}h ago`
}

function projectName(session: DiscoveredSession): string {
  return session.project_name?.name || session.project || session.display_name || 'Unknown project'
}

function activity(session: DiscoveredSession): string {
  return session.current_activity || session.status_reason || session.foreground?.last_message_summary || '-'
}

function modeLabel(session: DiscoveredSession): string {
  if (session.is_pinned) return 'Pinned'
  if (session.status_group === 'needs_input') return 'Focus'
  if (session.status_group === 'working') return 'Background'
  if (session.status_group === 'idle') return 'Idle'
  return statusLabel(session.status_group)
}

export function TaskRow({
  session,
  selected,
  onSelect,
  onAction,
}: {
  session: DiscoveredSession
  selected: boolean
  onSelect: () => void
  onAction: (action: 'pin' | 'ignore') => void
}) {
  const failed = session.status_group === 'error' || session.error_hints.length > 0 || session.status_dot === 'red'
  const waiting = session.status_group === 'needs_input'
  const path = session.short_cwd || session.cwd
  const health = getSessionHealth(session)
  const risks = getSessionRiskHints(session)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') onSelect()
      }}
      className={`task-row grid min-h-[56px] cursor-default items-center gap-3 px-3 py-2.5 text-sm transition md:grid-cols-[16px_minmax(140px,0.85fr)_minmax(180px,1.15fr)_minmax(160px,0.95fr)_minmax(220px,1.4fr)_86px_118px_92px] ${
        selected
          ? 'bg-blue-500/[0.09] ring-1 ring-inset ring-blue-500/15'
          : failed
            ? 'bg-red-500/[0.035] hover:bg-red-500/[0.055]'
            : waiting
              ? 'bg-orange-500/[0.035] hover:bg-orange-500/[0.06]'
              : 'hover:bg-black/[0.035] dark:hover:bg-white/[0.055]'
      }`}
    >
      <StatusDot status={session.status_dot || session.status} pulse={session.status_group === 'working'} />

      <div className="min-w-0">
        <AgentBadge type={session.agent_type} confidence={session.agent_confidence} session={session} />
      </div>

      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="truncate font-medium text-app">{session.display_name || projectName(session)}</span>
          {session.is_pinned && <span className="shrink-0 text-[13px] text-[var(--orange)]" title="Pinned">◆</span>}
        </div>
        <div className="mt-0.5 truncate text-xs text-muted md:hidden">{path}</div>
      </div>

      <div className="hidden min-w-0 md:block">
        <div className="truncate text-muted-strong">{projectName(session)}</div>
        <div className="truncate mono text-[11px] text-muted">{session.git_status_detail?.branch || session.project_status?.branch || path}</div>
      </div>

      <div className="hidden min-w-0 text-muted-strong md:block">
        <div className="truncate">{activity(session)}</div>
        <div className="mt-1"><RiskHints hints={risks} compact /></div>
      </div>

      <div className="hidden text-xs text-muted md:block">{fmtElapsed(session.elapsed_sec)}</div>
      <div className="hidden min-w-0 text-xs text-muted md:block">
        <HealthIndicator health={health} compact />
        <div className="mt-0.5">{fmtLastActivity(session.heartbeat_age_sec)}</div>
      </div>

      <div className="flex items-center justify-end gap-1.5">
        <span className="hidden rounded-full bg-black/[0.04] px-2 py-0.5 text-[11px] text-muted dark:bg-white/[0.08] xl:inline">
          {modeLabel(session)}
        </span>
        <button
          type="button"
          onClick={event => {
            event.stopPropagation()
            onAction('pin')
          }}
          className={`rounded-full px-2 py-1 text-[11px] transition ${
            session.is_pinned
              ? 'bg-orange-500/10 text-orange-700 dark:text-orange-300'
              : 'text-muted hover:bg-black/5 hover:text-app dark:hover:bg-white/10'
          }`}
          title={session.is_pinned ? 'Unpin' : 'Pin'}
        >
          Pin
        </button>
        <button
          type="button"
          onClick={event => {
            event.stopPropagation()
            onAction('ignore')
          }}
          className="rounded-full px-2 py-1 text-[11px] text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10"
          title={session.is_ignored ? 'Restore ignored session' : 'Hide only. Does not stop processes or delete files.'}
        >
          {session.is_ignored ? 'Restore' : 'Hide'}
        </button>
      </div>
    </div>
  )
}
