import { useState } from 'react'
import type { DiscoveredSession, Task } from '../types'
import { EmptyState } from './EmptyState'
import { relativeTimeFromDate, relativeTimeFromSeconds } from '../utils/status'

export interface TimelineEvent {
  id: string
  at: string | number | null
  title: string
  detail: string
  kind?: 'info' | 'success' | 'warning' | 'error'
}

export function buildSessionTimeline(session: DiscoveredSession): TimelineEvent[] {
  const events: TimelineEvent[] = []
  if (session.started_at) {
    events.push({ id: 'started', at: session.started_at, title: `${session.agent_type || 'Agent'} started working`, detail: session.root_cmd || session.short_cwd || session.cwd })
  }
  for (const item of session.timeline || []) {
    events.push({ id: `${item.ts}-${item.event}`, at: item.ts * 1000, title: item.event, detail: item.detail })
  }
  if (session.foreground?.waiting_input || session.status_group === 'needs_input') {
    events.push({ id: 'waiting', at: Date.now() - (session.heartbeat_age_sec || 0) * 1000, title: 'Needs your input', detail: session.status_reason || session.foreground?.last_message_summary || 'The foreground agent is waiting.', kind: 'warning' })
  }
  if (session.error_hints?.length > 0 || session.status_group === 'error') {
    events.push({ id: 'failed', at: Date.now(), title: 'Failure hint detected', detail: session.error_hints?.[0] || session.status_reason || 'The session reported an error.', kind: 'error' })
  }
  if ((session.heartbeat_age_sec ?? 0) > 900) {
    events.push({ id: 'stale', at: Date.now() - (session.heartbeat_age_sec || 0) * 1000, title: 'Became stale', detail: `No log activity for ${Math.floor((session.heartbeat_age_sec || 0) / 60)} minutes.`, kind: 'warning' })
  }
  if (session.is_pinned) {
    events.push({ id: 'pinned', at: Date.now(), title: 'Pinned', detail: 'This session is pinned in Focus Now.' })
  }
  return sortTimeline(events)
}

export function buildTaskTimeline(task: Task, logLines: string[] = []): TimelineEvent[] {
  const events: TimelineEvent[] = [
    { id: 'created', at: task.started_at, title: 'Task created', detail: task.goal || task.command || task.project_dir },
  ]
  if (task.pid) events.push({ id: 'started', at: task.started_at, title: `${task.agent_type || 'Agent'} started working`, detail: `pid ${task.pid}` })
  for (const entry of task.progress_log || []) {
    events.push({ id: `${entry.timestamp}-${entry.message}`, at: entry.timestamp, title: entry.step_id ? `Step ${entry.step_id}` : 'User note added', detail: entry.message })
  }
  if (task.has_error_hint || task.status === 'failed') {
    events.push({ id: 'failed', at: task.ended_at || task.last_log_update || Date.now(), title: 'Failed', detail: task.risk_notes || task.status_reason || 'The task reported a failure.', kind: 'error' })
  }
  if (task.status === 'completed') {
    events.push({ id: 'completed', at: task.ended_at || task.last_log_update || Date.now(), title: 'Marked as done', detail: task.final_summary || 'The task was completed.', kind: 'success' })
  }
  if (task.handoff_notes) {
    events.push({ id: 'handoff', at: task.ended_at || task.last_log_update || Date.now(), title: 'Handoff generated', detail: 'A handoff note is available.', kind: 'success' })
  }
  if (logLines.some(line => /\b(test|pytest|vitest|npm test)\b/i.test(line))) {
    events.push({ id: 'tests', at: task.last_log_update || Date.now(), title: 'Tests observed', detail: 'A test command appears in available logs.', kind: 'info' })
  }
  return sortTimeline(events)
}

export function TaskTimeline({ events }: { events: TimelineEvent[] }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? events : events.slice(0, 8)

  if (events.length === 0) {
    return <EmptyState title="No timeline events" description="Lifecycle events will appear as this task produces activity." />
  }

  return (
    <div>
      <div className="relative space-y-0 pl-4 before:absolute before:bottom-2 before:left-[5px] before:top-2 before:w-px before:bg-[var(--border-strong)]">
        {shown.map(event => (
          <TimelineItem key={event.id} event={event} />
        ))}
      </div>
      {events.length > 8 && (
        <button
          type="button"
          onClick={() => setExpanded(value => !value)}
          className="mt-2 rounded-full px-2.5 py-1 text-xs text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10"
        >
          {expanded ? 'Show less' : `Show ${events.length - 8} more`}
        </button>
      )}
    </div>
  )
}

function TimelineItem({ event }: { event: TimelineEvent }) {
  const color = event.kind === 'error' ? 'var(--red)' : event.kind === 'warning' ? 'var(--orange)' : event.kind === 'success' ? 'var(--green)' : 'var(--blue)'
  const title = typeof event.at === 'number' ? new Date(event.at).toLocaleString() : event.at ? new Date(event.at).toLocaleString() : undefined
  const relative = typeof event.at === 'number'
    ? relativeTimeFromSeconds(Math.floor((Date.now() - event.at) / 1000))
    : relativeTimeFromDate(event.at)

  return (
    <div className="relative pb-3 pl-4">
      <span className="absolute left-[-13px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-[var(--surface-strong)]" style={{ background: color }} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-app">{event.title}</div>
          <div className="mt-0.5 line-clamp-2 text-xs text-muted">{event.detail}</div>
        </div>
        <time className="shrink-0 text-[11px] text-muted" title={title}>{relative}</time>
      </div>
    </div>
  )
}

function sortTimeline(events: TimelineEvent[]): TimelineEvent[] {
  return [...events]
    .filter(event => event.title)
    .sort((a, b) => toMs(b.at) - toMs(a.at))
}

function toMs(value: string | number | null): number {
  if (typeof value === 'number') return value
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}
