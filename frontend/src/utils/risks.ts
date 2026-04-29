import type { DiscoveredSession, Task } from '../types'
import { getSessionHealth, getTaskHealth } from './health'

export type RiskSeverity = 'info' | 'warning' | 'critical'

export interface RiskHint {
  id: string
  title: string
  description: string
  severity: RiskSeverity
}

const ERROR_PATTERN = /\b(error|failed|failure|exception|traceback|panic|fatal)\b/i
const TEST_PATTERN = /\b(pytest|npm test|pnpm test|yarn test|vitest|cargo test|go test)\b/i

export function getSessionRiskHints(session: DiscoveredSession): RiskHint[] {
  const hints: RiskHint[] = []
  const health = getSessionHealth(session)
  const dirtyCount = session.git_status_detail?.dirty_count ?? session.project_status?.dirty_files?.length ?? 0
  const logs = [...(session.recent_logs || []), session.recent_output || '', ...(session.error_hints || [])].join('\n')

  if (session.status_group === 'error' || session.status === 'error_hint' || session.error_hints?.length > 0) {
    hints.push({ id: 'failed-status', title: 'Task failed', description: session.error_hints?.[0] || 'The latest session status indicates a failure.', severity: 'critical' })
  }
  if (ERROR_PATTERN.test(logs)) {
    hints.push({ id: 'failed-command', title: 'Failed command observed', description: 'Recent logs include error or failure output.', severity: 'warning' })
  }
  if (dirtyCount > 20) {
    hints.push({ id: 'many-files', title: 'Many files changed', description: `${dirtyCount} files are currently dirty in this worktree.`, severity: 'warning' })
  } else if (dirtyCount > 0) {
    hints.push({ id: 'dirty-worktree', title: 'Dirty worktree', description: `${dirtyCount} changed file${dirtyCount === 1 ? '' : 's'} detected.`, severity: 'info' })
  }
  if (health.status === 'stale' || health.status === 'zombie') {
    hints.push({ id: 'stale-logs', title: health.status === 'zombie' ? 'Possibly stuck' : 'Stale logs', description: health.message, severity: health.status === 'zombie' ? 'critical' : 'warning' })
  }
  if (session.elapsed_sec && session.elapsed_sec > 7200 && session.status_group === 'working') {
    hints.push({ id: 'long-running', title: 'Long-running task', description: 'This session has been running for more than two hours.', severity: 'info' })
  }
  if (session.status_group === 'needs_input' || session.foreground?.waiting_input) {
    hints.push({ id: 'needs-review', title: 'Needs review', description: 'The agent appears to be waiting for user input.', severity: 'warning' })
  }
  if ((session.status_group === 'working' || session.status === 'completed') && logs && !TEST_PATTERN.test(logs)) {
    hints.push({ id: 'no-tests', title: 'No tests observed', description: 'No test command was seen in recent logs.', severity: 'info' })
  }

  return dedupe(hints).slice(0, 5)
}

export function getTaskRiskHints(task: Task, logLines: string[] = []): RiskHint[] {
  const hints: RiskHint[] = []
  const health = getTaskHealth(task)
  const logs = [...logLines, ...task.progress_log.map(entry => entry.message), task.risk_notes || '', task.final_summary || ''].join('\n')

  if (task.status === 'failed' || task.has_error_hint) {
    hints.push({ id: 'failed-status', title: 'Task failed', description: task.risk_notes || task.status_reason || 'The task status indicates a failure.', severity: 'critical' })
  }
  if (ERROR_PATTERN.test(logs)) {
    hints.push({ id: 'failed-command', title: 'Failed command observed', description: 'Task logs or notes include error output.', severity: 'warning' })
  }
  if (task.changed_files.length > 20) {
    hints.push({ id: 'many-files', title: 'Large diff', description: `${task.changed_files.length} files changed.`, severity: 'warning' })
  }
  if (health.status === 'stale' || health.status === 'zombie') {
    hints.push({ id: 'stale-logs', title: health.status === 'zombie' ? 'Possibly stuck' : 'Stale logs', description: health.message, severity: health.status === 'zombie' ? 'critical' : 'warning' })
  }
  if ((task.status === 'completed' || task.status === 'running') && logs && !TEST_PATTERN.test(logs)) {
    hints.push({ id: 'no-tests', title: 'No tests observed', description: 'No test command was observed in available metadata.', severity: 'info' })
  }
  if (task.exit_code !== null && task.exit_code !== 0) {
    hints.push({ id: 'exit-code', title: 'Unknown exit status', description: `Process exited with code ${task.exit_code}.`, severity: 'warning' })
  }

  return dedupe(hints).slice(0, 5)
}

function dedupe(hints: RiskHint[]): RiskHint[] {
  const seen = new Set<string>()
  return hints.filter(hint => {
    if (seen.has(hint.id)) return false
    seen.add(hint.id)
    return true
  })
}
