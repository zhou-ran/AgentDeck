export type HealthStatus = 'healthy' | 'stale' | 'orphaned' | 'zombie' | 'unknown'
export type TaskMode = 'focus' | 'background' | 'pinned' | 'idle' | 'unknown'

const STATUS_LABELS: Record<string, string> = {
  running: 'Running',
  busy: 'Running',
  needs_input: 'Needs input',
  waiting_input: 'Needs input',
  waiting: 'Needs input',
  testing: 'Testing',
  editing: 'Editing',
  searching: 'Searching',
  git_ops: 'Git',
  running_script: 'Script',
  idle: 'Idle',
  stale: 'Stale',
  completed: 'Done',
  failed: 'Failed',
  error_hint: 'Failed',
  done: 'Done',
  pending: 'Pending',
  blocked: 'Blocked',
  working: 'Running',
  error: 'Failed',
  unknown: 'Unknown',
}

const HEALTH_LABELS: Record<HealthStatus, string> = {
  healthy: 'Healthy',
  stale: 'Stale',
  orphaned: 'Orphaned',
  zombie: 'Possibly stuck',
  unknown: 'Unknown',
}

const MODE_LABELS: Record<TaskMode, string> = {
  focus: 'Focus',
  background: 'Background',
  pinned: 'Pinned',
  idle: 'Idle',
  unknown: 'Unknown',
}

export function formatStatus(status: string | null | undefined): string {
  if (!status) return 'Unknown'
  return STATUS_LABELS[status] || status.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

export function formatHealth(status: HealthStatus): string {
  return HEALTH_LABELS[status]
}

export function formatTaskMode(mode: TaskMode): string {
  return MODE_LABELS[mode]
}

export function relativeTimeFromDate(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return 'Unknown'
  const ts = typeof value === 'number' ? value : new Date(value).getTime()
  if (!Number.isFinite(ts)) return 'Unknown'
  return relativeTimeFromSeconds(Math.max(0, Math.floor((Date.now() - ts) / 1000)))
}

export function relativeTimeFromSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return 'Unknown'
  if (seconds < 30) return 'Just now'
  if (seconds < 60) return `${Math.floor(seconds)}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 60) return `${Math.floor(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}
