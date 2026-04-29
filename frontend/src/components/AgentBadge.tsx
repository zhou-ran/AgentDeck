import type { DiscoveredSession } from '../types'
import { getAgentDisplayName, getAgentRuntime, getSessionIdentity } from '../utils/agentIdentity'

const AGENT_TONE: Record<string, string> = {
  codex: 'border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  claude: 'border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300',
  'claude-code': 'border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300',
  kimi: 'border-purple-500/20 bg-purple-500/10 text-purple-700 dark:text-purple-300',
  'kimi-code': 'border-purple-500/20 bg-purple-500/10 text-purple-700 dark:text-purple-300',
  aider: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  gemini: 'border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  pytest: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
  npm: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-300',
  git: 'border-gray-500/20 bg-gray-500/10 text-gray-700 dark:text-gray-300',
}

export function AgentBadge({
  type,
  confidence,
  session,
  compact = false,
}: {
  type: string | null | undefined
  confidence?: number | null
  session?: DiscoveredSession | null
  compact?: boolean
}) {
  const normalized = (type || 'unknown').toLowerCase()
  const tone = AGENT_TONE[normalized] || 'border-gray-500/20 bg-gray-500/10 text-gray-700 dark:text-gray-300'
  const label = getAgentDisplayName(type)
  const runtime = session ? getAgentRuntime(session) : null
  const identity = session ? getSessionIdentity(session) : null
  const lowConfidence = confidence !== undefined && confidence !== null && confidence < 0.8

  if (compact) {
    return (
      <span className={`inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`} title={identity || undefined}>
        <span className="truncate">{lowConfidence ? `Maybe ${label}` : label}{runtime && runtime !== 'Unknown' ? ` ${runtime}` : ''}</span>
      </span>
    )
  }

  return (
    <span className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`} title={identity || undefined}>
      <span className="truncate">{lowConfidence ? `Maybe ${label}` : label}</span>
      {runtime && runtime !== 'Unknown' && <span className="text-[10px] opacity-70">{runtime}</span>}
      {lowConfidence && <span className="mono text-[10px] opacity-70">{confidence.toFixed(2)}</span>}
    </span>
  )
}
