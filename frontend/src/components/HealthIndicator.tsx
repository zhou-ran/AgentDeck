import type { HealthResult } from '../utils/health'
import { formatHealth } from '../utils/status'

const HEALTH_TONE: Record<string, string> = {
  healthy: 'text-emerald-700 dark:text-emerald-300',
  stale: 'text-yellow-700 dark:text-yellow-300',
  orphaned: 'text-orange-700 dark:text-orange-300',
  zombie: 'text-red-700 dark:text-red-300',
  unknown: 'text-muted',
}

const HEALTH_DOT: Record<string, string> = {
  healthy: 'var(--green)',
  stale: 'var(--yellow)',
  orphaned: 'var(--orange)',
  zombie: 'var(--red)',
  unknown: 'var(--muted)',
}

export function HealthIndicator({
  health,
  compact = false,
}: {
  health: HealthResult
  compact?: boolean
}) {
  const color = HEALTH_DOT[health.status]

  if (compact) {
    return (
      <span className={`inline-flex min-w-0 items-center gap-1.5 truncate text-[11px] ${HEALTH_TONE[health.status]}`}>
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />
        <span className="truncate">{formatHealth(health.status)}</span>
      </span>
    )
  }

  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] font-medium text-muted">Health</div>
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${HEALTH_TONE[health.status]}`}>
          <span className="h-2 w-2 rounded-full" style={{ background: color }} />
          {formatHealth(health.status)}
        </span>
      </div>
      <div className="mt-2 text-sm text-app">{health.message}</div>
    </div>
  )
}
