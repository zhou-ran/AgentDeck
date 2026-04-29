import type { TaskStatus } from '../types'
import { formatStatus } from '../utils/status'

const STATUS_COLOR: Record<string, string> = {
  running: 'var(--green)',
  busy: 'var(--green)',
  testing: 'var(--blue)',
  editing: 'var(--green)',
  searching: 'var(--blue)',
  git_ops: 'var(--purple)',
  running_script: 'var(--purple)',
  needs_input: 'var(--orange)',
  waiting_input: 'var(--orange)',
  waiting: 'var(--orange)',
  idle: 'var(--yellow)',
  stale: 'var(--yellow)',
  completed: 'var(--blue)',
  failed: 'var(--red)',
  error_hint: 'var(--red)',
  unknown: 'var(--muted)',
  red: 'var(--red)',
  yellow: 'var(--yellow)',
  orange: 'var(--orange)',
  green: 'var(--green)',
  blue: 'var(--blue)',
  gray: 'var(--muted)',
}

export function statusColor(status: string | null | undefined): string {
  return STATUS_COLOR[status || 'unknown'] || STATUS_COLOR.unknown
}

export function statusLabel(status: string | null | undefined): string {
  return formatStatus(status)
}

export function StatusDot({
  status,
  label,
  pulse = false,
}: {
  status: TaskStatus | string | null | undefined
  label?: string
  pulse?: boolean
}) {
  const color = statusColor(status)

  return (
    <span className="inline-flex min-w-0 items-center gap-1.5">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${pulse ? 'animate-pulse' : ''}`}
        style={{ background: color, boxShadow: `0 0 0 3px color-mix(in srgb, ${color} 18%, transparent)` }}
      />
      {label !== undefined && <span className="truncate">{label}</span>}
    </span>
  )
}
