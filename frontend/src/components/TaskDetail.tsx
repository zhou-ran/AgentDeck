import { useEffect, useState } from 'react'
import type { Task, ProcessInfo, LogResponse } from '../types'
import { api } from '../api/client'
import { StatusBadge } from './StatusBadge'
import { LogViewer } from './LogViewer'
import { ProcessTree } from './ProcessTree'

export function TaskDetail({ task, onBack }: { task: Task; onBack: () => void }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [tree, setTree] = useState<ProcessInfo | null>(null)
  const [taskData, setTaskData] = useState(task)

  useEffect(() => {
    const load = async () => {
      try {
        const [logData, treeData, freshTask] = await Promise.all([
          api.getLog(task.task_id, 80).catch(() => null),
          api.getProcessTree(task.task_id).catch(() => null),
          api.getTask(task.task_id).catch(() => task),
        ])
        if (logData) setLog(logData)
        if (treeData) setTree(treeData)
        setTaskData(freshTask)
      } catch {}
    }
    load()
    const iv = setInterval(load, 3000)
    return () => clearInterval(iv)
  }, [task.task_id])

  const handleStop = async () => {
    if (!confirm('Stop this task?')) return
    await api.stopTask(task.task_id)
    const fresh = await api.getTask(task.task_id)
    setTaskData(fresh)
  }

  // Find current step
  const currentStep = taskData.plan.find(s => s.id === taskData.current_step_id)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-gray-400 hover:text-white text-sm">
          &larr; Back
        </button>
        <h2 className="text-lg font-bold">{taskData.name}</h2>
        <StatusBadge status={taskData.status} />
        {taskData.has_error_hint && (
          <span className="text-red-400 text-sm">⚠ errors detected in log</span>
        )}
        {(taskData.status === 'running' || taskData.status === 'idle') && (
          <button
            onClick={handleStop}
            className="ml-auto px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
          >
            Stop
          </button>
        )}
      </div>

      {/* Top section: Goal, Feature, Acceptance Criteria, Current Step */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Goal */}
        {taskData.goal && (
          <div className="bg-gray-900 rounded-lg p-3">
            <div className="text-gray-500 text-xs mb-1">Goal</div>
            <div className="text-gray-200 text-sm">{taskData.goal}</div>
          </div>
        )}

        {/* Feature */}
        {taskData.feature && (
          <div className="bg-gray-900 rounded-lg p-3">
            <div className="text-gray-500 text-xs mb-1">Feature</div>
            <div className="text-gray-200 text-sm">{taskData.feature}</div>
          </div>
        )}

        {/* Current Step */}
        {currentStep && (
          <div className="bg-gray-900 rounded-lg p-3">
            <div className="text-gray-500 text-xs mb-1">Current Step</div>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${
                currentStep.status === 'done' ? 'bg-green-500' :
                currentStep.status === 'running' ? 'bg-yellow-500' :
                currentStep.status === 'blocked' ? 'bg-red-500' :
                'bg-gray-600'
              }`} />
              <span className="text-gray-200 text-sm">{currentStep.title}</span>
            </div>
          </div>
        )}

        {/* Status */}
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Status</div>
          <div className="text-gray-200 text-sm">{taskData.status}</div>
        </div>
      </div>

      {/* Acceptance criteria */}
      {taskData.acceptance_criteria.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Acceptance Criteria</div>
          <ul className="text-gray-200 text-sm list-disc list-inside">
            {taskData.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}

      {/* Middle section: Plan checklist and Progress timeline */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Plan checklist */}
        {taskData.plan.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Plan</h3>
            <div className="space-y-1">
              {taskData.plan.map((step) => (
                <div key={step.id} className={`flex items-center gap-2 rounded px-3 py-2 text-sm ${
                  step.id === taskData.current_step_id ? 'bg-gray-800 border border-gray-700' : 'bg-gray-900'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    step.status === 'done' ? 'bg-green-500' :
                    step.status === 'running' ? 'bg-yellow-500' :
                    step.status === 'blocked' ? 'bg-red-500' :
                    'bg-gray-600'
                  }`} />
                  <span className="text-gray-300">{step.id}: {step.title}</span>
                  {step.notes && <span className="text-gray-500 text-xs ml-auto">{step.notes}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Progress timeline */}
        <div>
          <h3 className="text-sm font-semibold text-gray-300 mb-2">Progress Timeline</h3>
          {taskData.progress_log.length > 0 ? (
            <div className="space-y-1">
              {taskData.progress_log.map((entry, i) => (
                <div key={i} className="text-xs text-gray-400 font-mono bg-gray-900 rounded px-3 py-1.5">
                  <span className="text-gray-500">[{entry.timestamp}]</span>
                  {entry.step_id && <span className="text-blue-400 ml-1">[{entry.step_id}]</span>}
                  <span className="ml-1">{entry.message}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500 text-xs">No progress entries</div>
          )}
        </div>
      </div>

      {/* Handoff notes */}
      {taskData.handoff_notes && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Handoff Notes</div>
          <div className="text-gray-200 text-sm whitespace-pre-wrap">{taskData.handoff_notes}</div>
        </div>
      )}

      {/* Bottom section: Logs, Process tree, Changed files, Risk notes */}
      {/* Process tree */}
      <div>
        <h3 className="text-sm font-semibold text-gray-300 mb-2">Process Tree</h3>
        <ProcessTree tree={tree} />
      </div>

      {/* Logs */}
      <div>
        <h3 className="text-sm font-semibold text-gray-300 mb-2">
          Logs
          {log && <span className="text-gray-500 text-xs ml-2">({(log.size / 1024).toFixed(1)} KB)</span>}
        </h3>
        <LogViewer lines={log?.lines ?? []} height="400px" />
      </div>

      {/* Changed files */}
      {taskData.changed_files.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Changed Files ({taskData.changed_files.length})</div>
          <div className="text-gray-200 text-xs font-mono space-y-0.5">
            {taskData.changed_files.map((f, i) => (
              <div key={i}>{f}</div>
            ))}
          </div>
        </div>
      )}

      {/* Risk notes */}
      {taskData.risk_notes && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Risk Notes / Blockers</div>
          <div className="text-gray-200 text-sm whitespace-pre-wrap">{taskData.risk_notes}</div>
        </div>
      )}

      {/* Final summary */}
      {taskData.final_summary && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Final Summary</div>
          <div className="text-gray-200 text-sm whitespace-pre-wrap">{taskData.final_summary}</div>
        </div>
      )}

      {/* Metadata grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        {[
          ['Task ID', taskData.task_id],
          ['PID', taskData.pid ?? '-'],
          ['Command', taskData.command],
          ['Project Dir', taskData.project_dir],
          ['Started', taskData.started_at],
          ['Ended', taskData.ended_at ?? '-'],
          ['Exit Code', taskData.exit_code ?? '-'],
          ['Tags', taskData.tags.join(', ') || '-'],
        ].map(([label, value]) => (
          <div key={label} className="bg-gray-900 rounded-lg p-3">
            <div className="text-gray-500 text-xs mb-0.5">{label}</div>
            <div className="text-gray-200 font-mono text-xs break-all">{String(value)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
