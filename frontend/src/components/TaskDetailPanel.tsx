import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { LogResponse, ProcessInfo, Task } from '../types'
import { api } from '../api/client'
import { HandoffPanel, type HandoffData } from './HandoffPanel'
import { HealthIndicator } from './HealthIndicator'
import { LogViewer } from './LogViewer'
import { ProcessTree } from './ProcessTree'
import { RiskHints } from './RiskHints'
import { StatusDot, statusLabel } from './StatusDot'
import { TaskTimeline, buildTaskTimeline } from './TaskTimeline'
import { elapsed } from '../utils/format'
import { getTaskHealth } from '../utils/health'
import { getTaskRiskHints } from '../utils/risks'

export function TaskDetailPanel({
  task,
  onClose,
}: {
  task: Task | null
  onClose: () => void
}) {
  const panelRef = useRef<HTMLElement>(null)
  const [log, setLog] = useState<LogResponse | null>(null)
  const [tree, setTree] = useState<ProcessInfo | null>(null)

  useLayoutEffect(() => {
    panelRef.current?.scrollTo({ top: 0 })
  }, [task?.task_id])

  useEffect(() => {
    if (!task) return
    let mounted = true
    const load = async () => {
      const [logData, treeData] = await Promise.all([
        api.getLog(task.task_id, 80).catch(() => null),
        api.getProcessTree(task.task_id).catch(() => null),
      ])
      if (!mounted) return
      if (logData) setLog(logData)
      if (treeData) setTree(treeData)
    }
    load()
    const iv = setInterval(load, 3000)
    return () => {
      mounted = false
      clearInterval(iv)
    }
  }, [task?.task_id])

  if (!task) {
    return (
      <aside className="glass-panel-strong hidden min-h-[560px] rounded-[22px] p-5 xl:block">
        <div className="text-sm font-semibold text-app">Task Detail</div>
        <div className="mt-2 text-sm text-muted">Select a managed task to inspect plan, progress, logs, and process tree.</div>
      </aside>
    )
  }

  const currentStep = task.plan.find(s => s.id === task.current_step_id)
  const res = task.resources
  const history = task.cpu_mem_history || []
  const logLines = log?.lines ?? []
  const health = getTaskHealth(task)
  const risks = getTaskRiskHints(task, logLines)
  const timeline = buildTaskTimeline(task, logLines)
  const handoff = buildTaskHandoff(task, logLines)

  return (
    <aside ref={panelRef} className="glass-panel-strong h-full max-h-[calc(100vh-112px)] overflow-auto rounded-[22px] p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusDot status={task.status} pulse={task.status === 'running' || task.status === 'busy'} />
            {task.has_error_hint && <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] text-red-700 dark:text-red-300">Error hint</span>}
          </div>
          <h2 className="mt-3 truncate text-xl font-semibold tracking-tight text-app">{task.name}</h2>
          <div className="mt-1 truncate text-sm text-muted">{task.project_dir}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-[var(--border)] px-3 py-1 text-sm text-muted transition hover:bg-black/5 hover:text-app dark:hover:bg-white/10"
        >
          Close
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Metric label="Status" value={statusLabel(task.status)} />
        <Metric label="Elapsed" value={elapsed(task.started_at, task.ended_at)} />
        {task.pid && <Metric label="PID" value={String(task.pid)} />}
        {res && <Metric label="CPU" value={`${res.cpu_percent.toFixed(1)}%`} />}
        {res && <Metric label="Memory" value={`${res.memory_percent.toFixed(1)}%`} />}
        <Metric label="Steps" value={`${task.plan.filter(s => s.status === 'done').length}/${task.plan.length}`} />
      </div>

      <section className="mt-5">
        <HealthIndicator health={health} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Risk Hints" />
        <RiskHints hints={risks} />
      </section>

      {task.goal && (
        <section className="mt-5">
          <SectionTitle title="Goal" />
          <div className="quiet-panel rounded-2xl p-3 text-sm text-app">{task.goal}</div>
        </section>
      )}

      {task.feature && (
        <section className="mt-5">
          <SectionTitle title="Feature" />
          <div className="quiet-panel rounded-2xl p-3 text-sm text-app">{task.feature}</div>
        </section>
      )}

      {currentStep && (
        <section className="mt-5">
          <SectionTitle title="Current Step" />
          <div className="quiet-panel rounded-2xl p-3">
            <div className="flex items-center gap-2">
              <StatusDot status={currentStep.status === 'done' ? 'blue' : currentStep.status === 'running' ? 'green' : currentStep.status === 'blocked' ? 'red' : 'gray'} />
              <span className="text-sm font-medium text-app">{currentStep.title}</span>
            </div>
            {currentStep.notes && <div className="mt-2 text-xs text-muted">{currentStep.notes}</div>}
          </div>
        </section>
      )}

      {task.plan.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Plan" detail={`${task.plan.filter(s => s.status === 'done').length}/${task.plan.length}`} />
          <div className="space-y-1.5">
            {task.plan.map(step => (
              <div
                key={step.id}
                className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${
                  step.id === task.current_step_id
                    ? 'bg-blue-500/8 ring-1 ring-blue-500/10'
                    : 'bg-black/[0.03] dark:bg-white/[0.04]'
                }`}
              >
                <StatusDot status={step.status === 'done' ? 'blue' : step.status === 'running' ? 'green' : step.status === 'blocked' ? 'red' : 'gray'} />
                <span className="min-w-0 flex-1 truncate text-app">{step.title}</span>
                {step.notes && <span className="truncate text-xs text-muted">{step.notes}</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      {task.progress_log.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Progress" />
          <div className="space-y-1.5">
            {task.progress_log.slice(-8).map((entry, i) => (
              <div key={i} className="rounded-xl bg-black/[0.03] px-3 py-2 text-xs dark:bg-white/[0.04]">
                <span className="text-muted">{entry.timestamp}</span>
                {entry.step_id && <span className="ml-1.5 text-blue-600 dark:text-blue-300">[{entry.step_id}]</span>}
                <span className="ml-1.5 text-app">{entry.message}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {task.acceptance_criteria.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Acceptance Criteria" />
          <ul className="space-y-1 text-sm text-app">
            {task.acceptance_criteria.map((c, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--blue)]" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {res && (
        <section className="mt-5">
          <SectionTitle title="Resources" />
          <div className="grid grid-cols-2 gap-3">
            <Metric label="CPU" value={`${res.cpu_percent.toFixed(1)}%`} />
            <Metric label="Memory" value={`${res.memory_percent.toFixed(1)}%`} />
            <Metric label="RSS" value={`${res.rss_mb.toFixed(0)} MB`} />
            <Metric label="Children" value={String(res.child_count)} />
          </div>
        </section>
      )}

      {history.length > 2 && (
        <section className="mt-5">
          <SectionTitle title="History" />
          <div className="quiet-panel rounded-2xl p-3">
            <div className="mono text-[11px] text-muted">CPU / MEM last 60s</div>
            {/* SparkLine could be added here */}
            <div className="mt-2 flex gap-1">
              {history.slice(-30).map((s, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-sm"
                  style={{
                    height: `${Math.max(4, Math.min(32, s.cpu * 0.4))}px`,
                    background: s.cpu > 50 ? 'var(--red)' : s.cpu > 20 ? 'var(--orange)' : 'var(--green)',
                    opacity: 0.7,
                  }}
                  title={`CPU ${s.cpu.toFixed(1)}% MEM ${s.mem.toFixed(1)}%`}
                />
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="mt-5">
        <SectionTitle title="Timeline" />
        <TaskTimeline events={timeline} />
      </section>

      <section className="mt-5">
        <SectionTitle title="Handoff" />
        <HandoffPanel
          data={handoff}
          onGenerate={async () => {
            try {
              const data = await api.getHandoff(task.task_id)
              await navigator.clipboard.writeText(data.handoff_text)
            } catch {}
          }}
        />
      </section>

      {task.changed_files.length > 0 && (
        <section className="mt-5">
          <SectionTitle title="Changed Files" detail={`${task.changed_files.length}`} />
          <div className="quiet-panel max-h-36 overflow-auto rounded-2xl p-3 mono text-xs text-app">
            {task.changed_files.map(f => <div key={f} className="truncate">{f}</div>)}
          </div>
        </section>
      )}

      {task.risk_notes && (
        <section className="mt-5">
          <SectionTitle title="Risk Notes" />
          <div className="rounded-2xl border border-red-500/15 bg-red-500/[0.08] p-3 text-sm text-red-700 dark:text-red-300">{task.risk_notes}</div>
        </section>
      )}

      {task.final_summary && (
        <section className="mt-5">
          <SectionTitle title="Final Summary" />
          <div className="quiet-panel rounded-2xl p-3 text-sm leading-relaxed text-app whitespace-pre-wrap">{task.final_summary}</div>
        </section>
      )}

      <section className="mt-5">
        <SectionTitle title="Live Logs" detail={log ? `${(log.size / 1024).toFixed(1)} KB` : undefined} />
        <LogViewer lines={log?.lines ?? []} height="240px" />
      </section>

      <section className="mt-5">
        <SectionTitle title="Process Tree" />
        <ProcessTree tree={tree} />
      </section>

      <div className="sticky bottom-0 -mx-5 mt-5 flex gap-2 border-t border-[var(--border)] bg-[var(--surface-strong)] px-5 py-4 backdrop-blur-xl">
        <button
          type="button"
          onClick={async () => {
            try {
              const data = await api.getHandoff(task.task_id)
              await navigator.clipboard.writeText(data.handoff_text)
            } catch {}
          }}
          className="flex-1 rounded-full border border-[var(--border)] px-3 py-2 text-sm font-medium text-app transition hover:bg-black/5 dark:hover:bg-white/10"
        >
          Copy Handoff
        </button>
      </div>
    </aside>
  )
}

function SectionTitle({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      {detail && <div className="truncate text-xs text-muted">{detail}</div>}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="text-[11px] font-medium text-muted">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-app">{value}</div>
    </div>
  )
}

function buildTaskHandoff(task: Task, logLines: string[]): HandoffData | null {
  if (task.handoff_notes) {
    return {
      summary: task.handoff_notes,
      whatChanged: task.final_summary ? [task.final_summary] : undefined,
      filesTouched: task.changed_files,
      tests: detectTests(logLines),
      blockers: task.risk_notes ? [task.risk_notes] : undefined,
      suggestedNextPrompt: task.status === 'completed'
        ? `Review the completed ${task.name} work in ${task.project_name || task.short_cwd || task.project_dir} and decide whether to merge, test further, or ask for polish.`
        : `Resume ${task.name}. Start from the handoff notes, inspect the current plan step, and address any risk hints before continuing.`,
      generatedAt: task.ended_at || task.last_log_update || undefined,
    }
  }

  if (!task.final_summary && task.changed_files.length === 0 && task.progress_log.length === 0 && logLines.length === 0) {
    return null
  }

  return {
    draft: true,
    summary: task.final_summary || task.current_activity || task.status_reason || 'No structured handoff has been generated yet.',
    whatChanged: task.progress_log.slice(-5).map(entry => entry.message),
    filesTouched: task.changed_files,
    commands: logLines.filter(line => /\b(npm|pnpm|yarn|pytest|git|make|uv|python)\b/i.test(line)).slice(-6),
    tests: detectTests(logLines),
    blockers: task.risk_notes ? [task.risk_notes] : undefined,
    suggestedNextPrompt: `Continue ${task.name} in ${task.project_name || task.short_cwd || task.project_dir}. Use the current plan, recent logs, and risk hints as context before making the next change.`,
    generatedAt: new Date().toISOString(),
  }
}

function detectTests(logLines: string[]): string {
  return logLines.some(line => /\b(pytest|npm test|pnpm test|yarn test|vitest|cargo test|go test)\b/i.test(line))
    ? 'A test command appears in available logs.'
    : 'No test command was observed in available metadata.'
}
