import { EmptyState } from './EmptyState'

export interface HandoffData {
  summary?: string
  whatChanged?: string[]
  filesTouched?: string[]
  commands?: string[]
  tests?: string
  blockers?: string[]
  openQuestions?: string[]
  suggestedNextPrompt?: string
  generatedAt?: string
  draft?: boolean
}

export function HandoffPanel({
  data,
  onGenerate,
}: {
  data: HandoffData | null
  onGenerate?: () => void
}) {
  const text = data ? handoffToText(data) : ''

  if (!data) {
    return (
      <div>
        <EmptyState
          title="No handoff generated"
          description="Generate a handoff when this task finishes or needs to be resumed."
          action={onGenerate && (
            <button type="button" onClick={onGenerate} className="rounded-full border border-[var(--border)] px-3 py-1.5 text-xs text-app transition hover:bg-black/5 dark:hover:bg-white/10">
              Generate Handoff
            </button>
          )}
        />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-muted">
          {data.draft ? 'Best-effort draft from visible metadata' : 'Generated handoff'}
          {data.generatedAt ? ` · ${new Date(data.generatedAt).toLocaleString()}` : ''}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => navigator.clipboard.writeText(text)} className="rounded-full border border-[var(--border)] px-2.5 py-1 text-[11px] text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10">
            Copy Handoff
          </button>
          {data.suggestedNextPrompt && (
            <button type="button" onClick={() => navigator.clipboard.writeText(data.suggestedNextPrompt || '')} className="rounded-full border border-[var(--border)] px-2.5 py-1 text-[11px] text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10">
              Copy Prompt
            </button>
          )}
        </div>
      </div>
      {data.summary && <HandoffSection title="Summary" body={data.summary} />}
      {data.whatChanged && data.whatChanged.length > 0 && <HandoffList title="What changed" items={data.whatChanged} />}
      {data.filesTouched && data.filesTouched.length > 0 && <HandoffList title="Files touched" items={data.filesTouched} mono />}
      {data.commands && data.commands.length > 0 && <HandoffList title="Commands" items={data.commands} mono />}
      {data.tests && <HandoffSection title="Tests" body={data.tests} />}
      {data.blockers && data.blockers.length > 0 && <HandoffList title="Blockers" items={data.blockers} />}
      {data.openQuestions && data.openQuestions.length > 0 && <HandoffList title="Open questions" items={data.openQuestions} />}
      {data.suggestedNextPrompt && (
        <div className="quiet-panel rounded-2xl p-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Suggested next prompt</div>
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap mono text-xs text-app">{data.suggestedNextPrompt}</pre>
        </div>
      )}
    </div>
  )
}

function HandoffSection({ title, body }: { title: string; body: string }) {
  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      <div className="text-sm leading-relaxed text-app whitespace-pre-wrap">{body}</div>
    </div>
  )
}

function HandoffList({ title, items, mono = false }: { title: string; items: string[]; mono?: boolean }) {
  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      <div className="space-y-1">
        {items.map(item => (
          <div key={item} className={`truncate text-sm text-app ${mono ? 'mono text-xs' : ''}`}>{item}</div>
        ))}
      </div>
    </div>
  )
}

function handoffToText(data: HandoffData): string {
  const sections: string[] = []
  if (data.draft) sections.push('Draft handoff generated from visible AgentDeck metadata.')
  if (data.summary) sections.push(`Summary\n${data.summary}`)
  if (data.whatChanged?.length) sections.push(`What changed\n${data.whatChanged.map(item => `- ${item}`).join('\n')}`)
  if (data.filesTouched?.length) sections.push(`Files touched\n${data.filesTouched.map(item => `- ${item}`).join('\n')}`)
  if (data.commands?.length) sections.push(`Commands\n${data.commands.map(item => `- ${item}`).join('\n')}`)
  if (data.tests) sections.push(`Tests\n${data.tests}`)
  if (data.blockers?.length) sections.push(`Blockers\n${data.blockers.map(item => `- ${item}`).join('\n')}`)
  if (data.openQuestions?.length) sections.push(`Open questions\n${data.openQuestions.map(item => `- ${item}`).join('\n')}`)
  if (data.suggestedNextPrompt) sections.push(`Suggested next prompt\n${data.suggestedNextPrompt}`)
  return sections.join('\n\n')
}
