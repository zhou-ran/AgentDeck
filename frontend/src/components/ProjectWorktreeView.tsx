import { useMemo, useState } from 'react'
import type { DiscoveredSession } from '../types'
import { AgentBadge } from './AgentBadge'
import { EmptyStatePanel } from './EmptyState'
import { HealthIndicator } from './HealthIndicator'
import { StatusDot } from './StatusDot'
import { getSessionHealth } from '../utils/health'
import { getProjectName } from '../utils/agentIdentity'
import { formatStatus, relativeTimeFromSeconds } from '../utils/status'

export function ProjectWorktreeView({
  sessions,
  onSelect,
}: {
  sessions: DiscoveredSession[]
  onSelect: (session: DiscoveredSession) => void
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const groups = useMemo(() => {
    const map = new Map<string, DiscoveredSession[]>()
    for (const session of sessions) {
      const key = getProjectName(session)
      map.set(key, [...(map.get(key) || []), session])
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [sessions])

  if (groups.length === 0) {
    return <EmptyStatePanel title="No projects" description="Projects appear once local agent sessions are discovered." />
  }

  return (
    <div className="space-y-4">
      {groups.map(([project, items]) => {
        const isCollapsed = collapsed.has(project)
        const failed = items.filter(item => item.status_group === 'error' || item.error_hints.length > 0).length
        const active = items.filter(item => item.status_group === 'working' || item.status_group === 'needs_input').length
        return (
          <section key={project} className="glass-panel-strong overflow-hidden rounded-[22px]">
            <button
              type="button"
              onClick={() => setCollapsed(prev => {
                const next = new Set(prev)
                if (next.has(project)) next.delete(project)
                else next.add(project)
                return next
              })}
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-black/[0.025] dark:hover:bg-white/[0.04]"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted">{isCollapsed ? '>' : 'v'}</span>
                  <h2 className="truncate text-sm font-semibold text-app">{project}</h2>
                </div>
                <p className="mt-0.5 text-xs text-muted">{active} active · {failed} failed · {items.length} worktree{items.length === 1 ? '' : 's'}</p>
              </div>
              <span className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">{items.length}</span>
            </button>
            {!isCollapsed && (
              <div className="divide-y divide-[var(--border)]">
                {items.map(session => (
                  <button
                    key={session.session_id}
                    type="button"
                    onClick={() => onSelect(session)}
                    className="grid w-full gap-3 px-4 py-3 text-left text-sm transition hover:bg-black/[0.035] dark:hover:bg-white/[0.055] lg:grid-cols-[16px_minmax(110px,0.7fr)_minmax(160px,0.9fr)_minmax(220px,1.5fr)_110px_120px]"
                  >
                    <StatusDot status={session.status_dot || session.status} pulse={session.status_group === 'working'} />
                    <span className="truncate font-medium text-app">{session.git_status_detail?.branch || session.project_status?.branch || 'Unknown branch'}</span>
                    <AgentBadge type={session.agent_type} confidence={session.agent_confidence} session={session} compact />
                    <span className="truncate mono text-xs text-muted">{session.short_cwd || session.cwd}</span>
                    <span className="text-xs text-muted">{formatStatus(session.status)}</span>
                    <span className="flex items-center gap-2 text-xs text-muted">
                      <HealthIndicator health={getSessionHealth(session)} compact />
                      <span className="hidden xl:inline">{relativeTimeFromSeconds(session.heartbeat_age_sec)}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}
