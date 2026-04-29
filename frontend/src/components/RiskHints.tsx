import type { RiskHint } from '../utils/risks'
import { EmptyState } from './EmptyState'

const SEVERITY_TONE: Record<string, string> = {
  info: 'border-blue-500/15 bg-blue-500/[0.06] text-blue-700 dark:text-blue-300',
  warning: 'border-orange-500/18 bg-orange-500/[0.08] text-orange-800 dark:text-orange-300',
  critical: 'border-red-500/18 bg-red-500/[0.08] text-red-700 dark:text-red-300',
}

export function RiskHints({
  hints,
  compact = false,
}: {
  hints: RiskHint[]
  compact?: boolean
}) {
  if (compact) {
    const hint = hints[0]
    if (!hint) return null
    return (
      <span className={`inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-[11px] ${SEVERITY_TONE[hint.severity]}`} title={hint.description}>
        <span className="truncate">{hint.title}</span>
      </span>
    )
  }

  if (hints.length === 0) {
    return <EmptyState title="No risks detected" description="This task looks healthy based on the available metadata." />
  }

  return (
    <div className="space-y-2">
      {hints.map(hint => (
        <div key={hint.id} className={`rounded-2xl border px-3 py-2 ${SEVERITY_TONE[hint.severity]}`}>
          <div className="text-sm font-medium">{hint.title}</div>
          <div className="mt-0.5 text-xs opacity-80">{hint.description}</div>
        </div>
      ))}
    </div>
  )
}
