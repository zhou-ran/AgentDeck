import { useState, useMemo } from 'react'
import type { Task, TaskStatus, DiscoveredSession, SystemMetrics } from '../types'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { SystemOverview } from './SystemOverview'
import { FilterBar } from './FilterBar'
import { LANE_GROUPS, getLaneForStatus } from './StatusBadge'

const SUMMARY_CARDS = [
  { key: 'all',    label: '牛马总数', icon: '📊', filter: null },
  { key: 'input',  label: '等输入',   icon: '💬', filter: (s: DiscoveredSession[]) => s.filter(x => x.status === 'waiting_input') },
  { key: 'work',   label: '正在工作', icon: '⚡', filter: (s: DiscoveredSession[]) => s.filter(x => ['busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script', 'running'].includes(x.status)) },
  { key: 'slack',  label: '疑似摸鱼', icon: '🐟', filter: (s: DiscoveredSession[]) => s.filter(x => ['idle', 'waiting', 'unknown'].includes(x.status)) },
  { key: 'error',  label: '有错误',   icon: '🔴', filter: (s: DiscoveredSession[]) => s.filter(x => x.error_hints && x.error_hints.length > 0) },
]

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
  const [summaryFilter, setSummaryFilter] = useState<string | null>(null)

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

  // Apply summary filter to discovered sessions
  const filteredDiscovered = useMemo(() => {
    if (!summaryFilter || summaryFilter === 'all') return discovered
    const card = SUMMARY_CARDS.find(c => c.key === summaryFilter)
    if (card?.filter) return card.filter(discovered)
    return discovered
  }, [discovered, summaryFilter])

  // Group discovered sessions by lane
  const laneGroups = useMemo(() => {
    const groups: Record<string, DiscoveredSession[]> = {}
    for (const lane of LANE_GROUPS) {
      groups[lane.key] = []
    }
    for (const s of filteredDiscovered) {
      const lane = getLaneForStatus(s.status)
      groups[lane].push(s)
    }
    // Sort each lane by heartbeat_age (most recent first)
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => (a.heartbeat_age_sec ?? 9999) - (b.heartbeat_age_sec ?? 9999))
    }
    return groups
  }, [filteredDiscovered])

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

      {/* Summary cards */}
      {discovered.length > 0 && (
        <div className="grid grid-cols-5 gap-2 mb-4">
          {SUMMARY_CARDS.map(card => {
            const count = card.key === 'all' ? discovered.length : card.filter ? card.filter(discovered).length : 0
            const isActive = summaryFilter === card.key || (card.key === 'all' && !summaryFilter)
            return (
              <button
                key={card.key}
                onClick={() => setSummaryFilter(isActive && card.key !== 'all' ? null : card.key)}
                className={`p-2 rounded-lg border text-center transition-colors ${
                  isActive
                    ? 'bg-gray-800 border-cyan-600 text-cyan-300'
                    : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600'
                }`}
              >
                <div className="text-lg">{card.icon}</div>
                <div className="text-xs font-medium">{card.label}</div>
                <div className="text-lg font-bold">{count}</div>
              </button>
            )
          })}
        </div>
      )}

      {/* Connection status */}
      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-bold">实时监控</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-500">{connected ? '已连接' : '断开'}</span>
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
          <p className="text-lg mb-2">暂无任务</p>
          <p className="text-sm">
            使用 <code className="bg-gray-800 px-2 py-0.5 rounded">
              agent-foreman-local start
            </code> 启动任务
          </p>
        </div>
      ) : (
        <>
          {/* Live Agent Sessions — primary view */}
          {discovered.length > 0 && !isFiltering && (
            <div className="mb-6">
              <h3 className="text-xs font-medium text-purple-400 uppercase tracking-wider mb-3">
                实时 Agent 会话 ({filteredDiscovered.length})
              </h3>
              {LANE_GROUPS.map(lane => {
                const sessions = laneGroups[lane.key] || []
                if (sessions.length === 0) return null
                return (
                  <div key={lane.key} className="mb-4">
                    <h4 className="text-xs font-medium text-gray-400 mb-2">
                      {lane.label} ({sessions.length})
                    </h4>
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                      {sessions.map(s => (
                        <DiscoveredCard key={s.session_id} session={s} />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Managed Tasks */}
          {filtered.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                托管任务 ({filtered.length})
              </h3>
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
                      <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                        活跃 ({active.length})
                      </h4>
                      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                        {active.map(t => (
                          <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                        ))}
                      </div>
                    </div>
                  )}
                  {done.length > 0 && (
                    <div>
                      <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                        已结束 ({done.length})
                      </h4>
                      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                        {done.map(t => (
                          <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
