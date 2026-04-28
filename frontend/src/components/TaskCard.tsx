import type { Task } from '../types'
import { StatusBadge } from './StatusBadge'

function elapsed(started: string, ended: string | null): string {
  const start = new Date(started).getTime()
  const end = ended ? new Date(ended).getTime() : Date.now()
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m${secs % 60}s`
  return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}m`
}

export function TaskCard({ task, onClick }: { task: Task; onClick: () => void }) {
  const borderColor =
    task.status === 'running' ? 'border-green-600' :
    task.status === 'failed' ? 'border-red-600' :
    task.status === 'waiting_input' ? 'border-orange-600' :
    task.status === 'idle' ? 'border-yellow-600' :
    task.status === 'completed' ? 'border-blue-600' :
    'border-gray-700'

  return (
    <div
      onClick={onClick}
      className={`bg-gray-900 rounded-xl border-l-4 ${borderColor} p-4 cursor-pointer hover:bg-gray-800 transition-colors`}
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-sm truncate flex-1 mr-2">
          {task.has_error_hint && <span className="text-red-400 mr-1">⚠</span>}
          {task.name}
        </h3>
        <StatusBadge status={task.status} />
      </div>

      <div className="space-y-1 text-xs text-gray-400">
        <div className="truncate">
          <span className="text-gray-500">cmd:</span>{' '}
          <span className="font-mono">{task.command}</span>
        </div>
        <div className="flex gap-4">
          <span>
            <span className="text-gray-500">dir:</span>{' '}
            <span className="truncate inline-block max-w-[200px] align-bottom">{task.project_dir}</span>
          </span>
          {task.pid && (
            <span>
              <span className="text-gray-500">pid:</span> {task.pid}
            </span>
          )}
          <span>
            <span className="text-gray-500">elapsed:</span> {elapsed(task.started_at, task.ended_at)}
          </span>
        </div>
        {task.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap mt-1">
            {task.tags.map((t) => (
              <span key={t} className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 text-[10px]">{t}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
