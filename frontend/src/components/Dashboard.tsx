import { useState, useMemo } from 'react'
import type { Task, TaskStatus, DiscoveredSession, SystemMetrics } from '../types'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { AgentSessionDetail } from './AgentSessionDetail'
import { SystemOverview } from './SystemOverview'
import { FilterBar } from './FilterBar'

export function Dashboard({ tasks, discovered, systemMetrics, connected }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  connected: boolean
}) {
  const [selected, setSelected] = useState<Task | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [filterStatuses, setFilterStatuses] = useState<TaskStatus[]>([])
  const [search, setSearch] = useState('')
  const [runningOnly, setRunningOnly] = useState(false)

  const filtered = useMemo(() => {
    let result = tasks

    if (runningOnly) {
      result = result.filter(t =>
        ['running', 'busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script', 'waiting', 'waiting_input'].includes(t.status)
      )
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
  const selectedSession = selectedSessionId
    ? discovered.find(s => s.session_id === selectedSessionId) || null
    : null

  if (selectedTask) {
    return <TaskDetail task={selectedTask} onBack={() => setSelected(null)} />
  }
  if (selectedSession) {
    return <AgentSessionDetail session={selectedSession} onBack={() => setSelectedSessionId(null)} />
  }

  const active = filtered.filter(t =>
    ['running', 'busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script', 'waiting', 'idle', 'waiting_input'].includes(t.status)
  )
  const done = filtered.filter(t =>
    ['completed', 'failed', 'unknown'].includes(t.status)
  )

  const isFiltering = runningOnly || filterStatuses.length > 0 || search.trim()
  const sessionCounts = discovered.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1
    return acc
  }, {} as Record<string, number>)
  const totalSessionCpu = discovered.reduce((sum, s) => sum + (s.cpu_percent || 0), 0)
  const totalSessionMem = discovered.reduce((sum, s) => sum + (s.memory_percent || 0), 0)
  const recentProject = discovered[0]?.project_name || discovered[0]?.short_cwd || '-'

  return (
    <div>
      <SystemOverview metrics={systemMetrics} />

      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-bold">Live Agent Sessions</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-500">{connected ? 'connected' : 'disconnected'}</span>
      </div>

      <div className="grid gap-3 md:grid-cols-5 mb-6">
        <Metric label="agents" value={String(discovered.length)} />
        <Metric label="busy/testing/editing" value={`${sessionCounts.busy || 0}/${sessionCounts.testing || 0}/${sessionCounts.editing || 0}`} />
        <Metric label="idle/failed" value={`${sessionCounts.idle || 0}/${sessionCounts.failed || 0}`} />
        <Metric label="cpu/mem" value={`${totalSessionCpu.toFixed(1)}% / ${totalSessionMem.toFixed(1)}%`} />
        <Metric label="recent project" value={recentProject} />
      </div>

      {discovered.length > 0 && !isFiltering && (
        <div className="mb-8">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {discovered.map(s => (
              <DiscoveredCard key={s.session_id} session={s} onClick={() => setSelectedSessionId(s.session_id)} />
            ))}
          </div>
        </div>
      )}

      {discovered.length === 0 && !isFiltering && (
        <div className="text-center py-12 text-gray-500 border border-gray-800 rounded-lg mb-8">
          <p className="text-lg mb-2">No live agent sessions discovered</p>
          <p className="text-sm">Start Codex, Claude Code, kimi-code, aider, or gemini in a project directory.</p>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Managed Tasks</h2>
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

      {filtered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg mb-2">No managed tasks yet</p>
          <p className="text-sm">
            Use <code className="bg-gray-800 px-2 py-0.5 rounded">agentctl run</code> to record an instruction and log for future sessions.
          </p>
        </div>
      ) : (
        <>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 min-w-0">
      <div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className="text-sm text-gray-100 truncate">{value}</div>
    </div>
  )
}
