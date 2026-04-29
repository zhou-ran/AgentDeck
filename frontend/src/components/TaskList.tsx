import type { DiscoveredSession } from '../types'
import { EmptyState } from './EmptyState'
import { TaskRow } from './TaskRow'

export function TaskList({
  title,
  description,
  sessions,
  selectedSessionId,
  onSelect,
  onAction,
  emptyTitle,
  emptyDescription,
}: {
  title: string
  description?: string
  sessions: DiscoveredSession[]
  selectedSessionId: string | null
  onSelect: (session: DiscoveredSession) => void
  onAction: (session: DiscoveredSession, action: 'pin' | 'ignore') => void
  emptyTitle: string
  emptyDescription: string
}) {
  return (
    <section className="glass-panel-strong overflow-hidden rounded-[22px]">
      <div className="flex flex-wrap items-end justify-between gap-3 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-app">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
        </div>
        <div className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">
          {sessions.length}
        </div>
      </div>

      {sessions.length === 0 ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <>
          <div className="hidden border-y border-[var(--border)] bg-black/[0.025] px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-muted dark:bg-white/[0.04] md:grid md:grid-cols-[16px_minmax(130px,0.8fr)_minmax(180px,1.2fr)_minmax(160px,1fr)_minmax(220px,1.5fr)_86px_96px_92px] md:gap-3">
            <span />
            <span>Agent</span>
            <span>Task</span>
            <span>Project</span>
            <span>Current step</span>
            <span>Duration</span>
            <span>Updated</span>
            <span className="text-right">Actions</span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {sessions.map(session => (
              <TaskRow
                key={session.session_id}
                session={session}
                selected={selectedSessionId === session.session_id}
                onSelect={() => onSelect(session)}
                onAction={action => onAction(session, action)}
              />
            ))}
          </div>
        </>
      )}
    </section>
  )
}
