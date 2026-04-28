import { useState } from 'react'
import type { Task, DiscoveredSession, SystemMetrics } from '../types'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { SystemOverview } from './SystemOverview'

export function Dashboard({ tasks, discovered, systemMetrics, connected }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  connected: boolean
}) {
  const [selected, setSelected] = useState<Task | null>(null)

  if (selected) {
    return <TaskDetail task={selected} onBack={() => setSelected(null)} />
  }

  const active = tasks.filter((t) => ['running', 'idle', 'waiting_input'].includes(t.status))
  const done = tasks.filter((t) => ['completed', 'failed', 'unknown'].includes(t.status))

  return (
    <div>
      {/* System Overview */}
      <SystemOverview metrics={systemMetrics} />

      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-lg font-bold">Tasks</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-500">{connected ? 'connected' : 'disconnected'}</span>
        <span className="text-xs text-gray-500 ml-auto">{tasks.length} total</span>
      </div>

      {tasks.length === 0 && discovered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg mb-2">No tasks yet</p>
          <p className="text-sm">Use <code className="bg-gray-800 px-2 py-0.5 rounded">agentctl start</code> to launch a task</p>
        </div>
      ) : (
        <>
          {/* Discovered Agents */}
          {discovered.length > 0 && (
            <div className="mb-6">
              <h3 className="text-xs font-medium text-purple-400 uppercase tracking-wider mb-3">
                Discovered Agents ({discovered.length})
              </h3>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {discovered.map((s) => (
                  <DiscoveredCard key={s.session_id} session={s} />
                ))}
              </div>
            </div>
          )}

          {active.length > 0 && (
            <div className="mb-6">
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">Active ({active.length})</h3>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {active.map((t) => (
                  <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                ))}
              </div>
            </div>
          )}
          {done.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">Finished ({done.length})</h3>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {done.map((t) => (
                  <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
