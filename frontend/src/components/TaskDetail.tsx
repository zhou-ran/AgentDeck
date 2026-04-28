import { useEffect, useState } from 'react'
import type { Task, ProcessInfo, LogResponse } from '../types'
import { api } from '../api/client'
import { StatusBadge } from './StatusBadge'
import { LogViewer } from './LogViewer'
import { ProcessTree } from './ProcessTree'

export function TaskDetail({ task, onBack }: { task: Task; onBack: () => void }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [tree, setTree] = useState<ProcessInfo | null>(null)
  const [newNote, setNewNote] = useState('')
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

  const handleAddNote = async () => {
    if (!newNote.trim()) return
    const updated = await api.addNote(task.task_id, newNote.trim())
    setTaskData(updated)
    setNewNote('')
  }

  const handleStop = async () => {
    if (!confirm('Stop this task?')) return
    await api.stopTask(task.task_id)
    const fresh = await api.getTask(task.task_id)
    setTaskData(fresh)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="text-gray-400 hover:text-white text-sm">
          &larr; Back
        </button>
        <h2 className="text-lg font-bold">{taskData.name}</h2>
        <StatusBadge status={taskData.status} />
        {(taskData.status === 'running' || taskData.status === 'idle') && (
          <button
            onClick={handleStop}
            className="ml-auto px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
          >
            Stop
          </button>
        )}
      </div>

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
          ['Error Hint', taskData.has_error_hint ? 'YES' : 'no'],
          ['Tags', taskData.tags.join(', ') || '-'],
        ].map(([label, value]) => (
          <div key={label} className="bg-gray-900 rounded-lg p-3">
            <div className="text-gray-500 text-xs mb-0.5">{label}</div>
            <div className="text-gray-200 font-mono text-xs break-all">{String(value)}</div>
          </div>
        ))}
      </div>

      {taskData.acceptance_criteria && (
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-gray-500 text-xs mb-1">Acceptance Criteria</div>
          <div className="text-gray-200 text-sm">{taskData.acceptance_criteria}</div>
        </div>
      )}

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

      {/* Progress notes */}
      <div>
        <h3 className="text-sm font-semibold text-gray-300 mb-2">Progress Notes</h3>
        {taskData.progress_notes.length > 0 ? (
          <div className="space-y-1 mb-3">
            {taskData.progress_notes.map((note, i) => (
              <div key={i} className="text-xs text-gray-400 font-mono bg-gray-900 rounded px-3 py-1.5">
                {note}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-gray-500 text-xs mb-3">No notes yet</div>
        )}
        <div className="flex gap-2">
          <input
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddNote()}
            placeholder="Add a progress note..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-gray-500"
          />
          <button
            onClick={handleAddNote}
            className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  )
}
