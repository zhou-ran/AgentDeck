import { useState, useMemo } from 'react'
import type { Task, TaskStatus, DiscoveredSession, SystemMetrics } from '../types'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { SystemOverview } from './SystemOverview'
import { FilterBar } from './FilterBar'

export function Dashboard({ tasks, discovered, systemMetrics, connected }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  connected: boolean
}) {
  const [selected, setSelected] = useState<Task | null>(null)
  const [filterStatuses, setFilterStatuses] = useState<TaskStatus[]>([])
  const [search, setSearch] = useState('')
  const [runningOnly, setRunningOnly] = useState(false)

  const filtered = useMemo(() => {
    let result = tasks

    if (runningOnly) {
      result = result.filter(t => t.status === 'running')
    }

    if (filterStatuses.length > 0) {
      result = result.filter(t => filterStatuses.includes(t.status))
    }

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(t =>
        t.task_id.toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q) ||
        t.command.toLowerCase().includes(q) ||
        t.project_dir.toLowerCase().includes(q) ||
        t.goal.toLowerCase().includes(q)
      )
    }

    return result
  }, [tasks, filterStatuses, search, runningOnly])
  const selectedTask = selected
    ? tasks.find(t => t.task_id === selected.task_id) || selected
    : null

  if (selectedTask) {
    return <TaskDetail task={selectedTask} onBack={() => setSelected(null)} />
  }

  const active = filtered.filter(t =>
    ['running', 'idle', 'waiting_input'].includes(t.status)
  )
  const done = filtered.filter(t =>
    ['completed', 'failed', 'unknown'].includes(t.status)
  )

  const isFiltering = runningOnly || filterStatuses.length > 0 || search.trim()

  return (
    <div>
      <SystemOverview metrics={systemMetrics} />

      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-bold">Tasks</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-500">{connected ? 'connected' : 'disconnected'}</span>
      </div>

      <FilterBar
        statuses={filterStatuses}
        onStatusesChange={setFilterStatuses}
        search={search}
        onSearchChange={setSearch}
        runningOnly={runningOnly}
        onRunningOnlyChange={setRunningOnly}
        totalCount={tasks.length}
        filteredCount={filtered.length}
      />

      {filtered.length === 0 && discovered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg mb-2">No tasks yet</p>
          <p className="text-sm">
            Use <code className="bg-gray-800 px-2 py-0.5 rounded">
              agent-foreman-local start
            </code> to launch a task
          </p>
        </div>
      ) : (
        <>
          {discovered.length > 0 && !isFiltering && (
            <div className="mb-6">
              <h3 className="text-xs font-medium text-purple-400 uppercase tracking-wider mb-3">
                Discovered Agents ({discovered.length})
              </h3>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {discovered.map(s => (
                  <DiscoveredCard key={s.session_id} session={s} />
                ))}
              </div>
            </div>
          )}

          {isFiltering ? (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {filtered.map(t => (
                <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
              ))}
            </div>
          ) : (
            <>
              {active.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                    Active ({active.length})
                  </h3>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {active.map(t => (
                      <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                    ))}
                  </div>
                </div>
              )}
              {done.length > 0 && (
                <div>
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                    Finished ({done.length})
                  </h3>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {done.map(t => (
                      <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
