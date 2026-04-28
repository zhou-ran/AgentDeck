import type { Task } from '../types'
import { StatusBadge } from './StatusBadge'
import { SparkLine } from './SparkLine'
import { elapsed, formatBytes } from '../utils/format'

export function TaskCard({ task, onClick }: { task: Task; onClick: () => void }) {
  const borderColor =
    task.status === 'running' ? 'border-green-600' :
    task.status === 'failed' ? 'border-red-600' :
    task.status === 'waiting_input' ? 'border-orange-600' :
    task.status === 'idle' ? 'border-yellow-600' :
    task.status === 'completed' ? 'border-blue-600' :
    'border-gray-700'

  const res = task.resources
  const history = task.cpu_mem_history || []

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

        {/* Resource metrics row */}
        {res && (
          <div className="flex gap-3 mt-1 pt-1 border-t border-gray-800">
            <span title="CPU percent">
              <span className="text-gray-500">CPU:</span>{' '}
              <span className={res.cpu_percent > 80 ? 'text-red-400' : res.cpu_percent > 50 ? 'text-yellow-400' : 'text-green-400'}>
                {res.cpu_percent.toFixed(1)}%
              </span>
            </span>
            <span title="Memory percent">
              <span className="text-gray-500">MEM:</span>{' '}
              <span className={res.memory_percent > 80 ? 'text-red-400' : 'text-blue-400'}>
                {res.memory_percent.toFixed(1)}%
              </span>
            </span>
            <span title="RSS memory">
              <span className="text-gray-500">RSS:</span> {res.rss_mb.toFixed(0)}M
            </span>
            {res.child_count > 0 && (
              <span title="Child processes">
                <span className="text-gray-500">children:</span> {res.child_count}
              </span>
            )}
            {res.open_files > 0 && (
              <span title="Open file descriptors">
                <span className="text-gray-500">fds:</span> {res.open_files}
              </span>
            )}
            {(res.read_bytes > 0 || res.write_bytes > 0) && (
              <span title="I/O bytes read/written">
                <span className="text-gray-500">io:</span>{' '}
                <span className="text-cyan-400">{formatBytes(res.read_bytes)}</span>
                {' / '}
                <span className="text-orange-400">{formatBytes(res.write_bytes)}</span>
              </span>
            )}
          </div>
        )}

        {/* Sparkline for active tasks */}
        {history.length > 2 && (
          <div className="mt-1 pt-1 border-t border-gray-800">
            <SparkLine data={history} width={240} height={32} />
          </div>
        )}

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
