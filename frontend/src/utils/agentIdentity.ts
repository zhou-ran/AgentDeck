import type { DiscoveredSession } from '../types'
import { formatStatus } from './status'

export function getAgentDisplayName(type: string | null | undefined): string {
  const normalized = (type || 'unknown').toLowerCase()
  const labels: Record<string, string> = {
    codex: 'Codex',
    claude: 'Claude Code',
    'claude-code': 'Claude Code',
    kimi: 'Kimi',
    'kimi-code': 'Kimi Code',
    aider: 'Aider',
    gemini: 'Gemini',
    pytest: 'Pytest',
    npm: 'Npm',
    git: 'Git',
    unknown: 'Unknown',
  }
  return labels[normalized] || formatStatus(normalized)
}

export function getAgentRuntime(session?: DiscoveredSession | null): string {
  if (!session) return 'Unknown'
  const command = `${session.root_cmd || ''} ${session.foreground?.cmd || ''}`.toLowerCase()
  if (command.includes('claude')) return 'CLI'
  if (command.includes('codex')) return 'CLI'
  if (command.includes('kimi')) return 'CLI'
  if (command.includes('aider')) return 'CLI'
  if (command.includes('gemini')) return 'CLI'
  if (session.tty) return 'CLI'
  if (session.background_jobs?.some(job => job.job_type === 'browser')) return 'Browser'
  if (session.root_process?.name?.includes('python') || command.includes('.py')) return 'Script'
  return session.is_interactive ? 'Local' : 'Unknown'
}

export function getSessionIdentity(session: DiscoveredSession): string {
  const project = session.project_name?.name || session.project || 'Unknown project'
  const branch = session.git_status_detail?.branch || session.project_status?.branch
  if (branch) return `${project} · ${branch}`
  if (session.short_cwd) return `${project} · ${session.short_cwd}`
  if (session.root_pid) return `${project} · pid ${session.root_pid}`
  return project
}

export function getProjectName(session: DiscoveredSession): string {
  return session.project_name?.name || session.project || session.display_name || 'Unknown project'
}
