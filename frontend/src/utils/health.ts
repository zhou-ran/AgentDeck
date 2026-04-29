import type { DiscoveredSession, Task } from '../types'
import type { HealthStatus } from './status'

export interface HealthResult {
  status: HealthStatus
  message: string
  ageSec?: number | null
}

function hasRunningStatus(status: string): boolean {
  return ['running', 'busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script', 'working'].includes(status)
}

export function getSessionHealth(session: DiscoveredSession): HealthResult {
  const age = session.heartbeat_age_sec
  const processAlive = session.foreground?.alive ?? (session.root_pid ? true : null)
  const running = hasRunningStatus(session.status) || session.status_group === 'working'

  if (running && processAlive === false) {
    return { status: 'zombie', message: 'Marked running, but the process is no longer alive.', ageSec: age }
  }
  if (processAlive === false) {
    return { status: 'orphaned', message: 'Session exists but process is no longer alive.', ageSec: age }
  }
  if (age !== null && age !== undefined && age > 3600 && running) {
    return { status: 'zombie', message: `No log activity for ${Math.floor(age / 60)} minutes.`, ageSec: age }
  }
  if (age !== null && age !== undefined && age > 900) {
    return { status: 'stale', message: `No log activity for ${Math.floor(age / 60)} minutes.`, ageSec: age }
  }
  if (age !== null && age !== undefined) {
    return { status: 'healthy', message: 'Recent activity detected.', ageSec: age }
  }
  return { status: 'unknown', message: 'Not enough metadata to judge session health.', ageSec: age }
}

export function getTaskHealth(task: Task): HealthResult {
  const last = task.last_log_update || task.ended_at || task.started_at
  const age = last ? Math.max(0, Math.floor((Date.now() - new Date(last).getTime()) / 1000)) : null
  const running = hasRunningStatus(task.status)

  if (task.pid === null && running) {
    return { status: 'orphaned', message: 'Task is marked running, but no process id is available.', ageSec: age }
  }
  if (age !== null && age > 3600 && running) {
    return { status: 'zombie', message: `No log activity for ${Math.floor(age / 60)} minutes.`, ageSec: age }
  }
  if (age !== null && age > 900) {
    return { status: 'stale', message: `No log activity for ${Math.floor(age / 60)} minutes.`, ageSec: age }
  }
  if (age !== null) return { status: 'healthy', message: 'Recent task activity detected.', ageSec: age }
  return { status: 'unknown', message: 'Not enough metadata to judge task health.', ageSec: age }
}
