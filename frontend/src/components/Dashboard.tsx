import { useMemo, useState } from 'react'
import type { Task, DiscoveredSession, SessionStatus, SystemMetrics } from '../types'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { SystemOverview } from './SystemOverview'
import { LANE_GROUPS, getLaneForStatus } from './StatusBadge'

const SESSION_STATUSES: SessionStatus[] = [
  'needs_input',
  'testing',
  'editing',
  'searching',
  'git_ops',
  'running_script',
  'busy',
  'idle',
  'stale',
  'error_hint',
  'unknown',
]

const STATUS_LABELS: Record<SessionStatus, string> = {
  needs_input: '等输入',
  testing: '测试中',
  editing: '编辑中',
  searching: '搜索中',
  git_ops: 'Git操作',
  running_script: '脚本运行',
  busy: '忙碌',
  idle: '空闲',
  stale: '失联',
  error_hint: '有错误',
  unknown: '未知',
}

const SUMMARY_CARDS = [
  { key: 'all', label: '全部 agent', filter: (s: DiscoveredSession[]) => s },
  { key: 'input', label: '等输入', filter: (s: DiscoveredSession[]) => s.filter(x => x.status === 'needs_input') },
  { key: 'work', label: '正在工作', filter: (s: DiscoveredSession[]) => s.filter(x => ['busy', 'editing', 'searching', 'git_ops', 'running_script'].includes(x.status)) },
  { key: 'testing', label: '正在测试', filter: (s: DiscoveredSession[]) => s.filter(x => x.status === 'testing') },
  { key: 'idle', label: '疑似摸鱼/idle', filter: (s: DiscoveredSession[]) => s.filter(x => ['idle', 'stale', 'unknown'].includes(x.status)) },
  { key: 'error', label: '有错误', filter: (s: DiscoveredSession[]) => s.filter(x => x.status === 'error_hint' || (x.error_hints?.length ?? 0) > 0) },
]

function sessionMatchesSearch(session: DiscoveredSession, q: string): boolean {
  const haystack = [
    session.project_name?.name,
    session.project,
    session.agent_type,
    session.status,
    session.cwd,
    session.user_instruction,
    session.last_user_message,
    session.recent_output,
    session.root_process?.cmdline?.join(' '),
  ].join(' ').toLowerCase()
  return haystack.includes(q)
}

export function Dashboard({ tasks, discovered, systemMetrics, connected }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  connected: boolean
}) {
  const [selected, setSelected] = useState<Task | null>(null)
  const [search, setSearch] = useState('')
  const [agentType, setAgentType] = useState('all')
  const [statusFilter, setStatusFilter] = useState<SessionStatus | 'all'>('all')
  const [summaryFilter, setSummaryFilter] = useState('all')
  const [showManagedTasks, setShowManagedTasks] = useState(false)

  const filteredDiscovered = useMemo(() => {
    let result = discovered
    const summary = SUMMARY_CARDS.find(c => c.key === summaryFilter)
    if (summary && summary.key !== 'all') {
      result = summary.filter(result)
    }
    if (agentType !== 'all') {
      result = result.filter(s => s.agent_type === agentType)
    }
    if (statusFilter !== 'all') {
      result = result.filter(s => s.status === statusFilter)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(s => sessionMatchesSearch(s, q))
    }
    return result
  }, [discovered, summaryFilter, agentType, statusFilter, search])

  const laneGroups = useMemo(() => {
    const groups: Record<string, DiscoveredSession[]> = {}
    for (const lane of LANE_GROUPS) {
      groups[lane.key] = []
    }
    for (const s of filteredDiscovered) {
      const lane = getLaneForStatus(s.status)
      groups[lane].push(s)
    }
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => (a.heartbeat_age_sec ?? 999999) - (b.heartbeat_age_sec ?? 999999))
    }
    return groups
  }, [filteredDiscovered])

  const agentTypes = useMemo(() => {
    return Array.from(new Set(discovered.map(s => s.agent_type).filter(Boolean))).sort()
  }, [discovered])

  const selectedTask = selected
    ? tasks.find(t => t.task_id === selected.task_id) || selected
    : null

  if (selectedTask) {
    return <TaskDetail task={selectedTask} onBack={() => setSelected(null)} />
  }

  return (
    <div>
      <SystemOverview metrics={systemMetrics} />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
        {SUMMARY_CARDS.map(card => {
          const count = card.filter(discovered).length
          const isActive = summaryFilter === card.key
          return (
            <button
              key={card.key}
              onClick={() => setSummaryFilter(card.key)}
              className={`p-2 rounded-lg border text-left transition-colors ${
                isActive
                  ? 'bg-gray-800 border-cyan-600 text-cyan-300'
                  : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600'
              }`}
            >
              <div className="text-xs font-medium">{card.label}</div>
              <div className="text-xl font-bold">{count}</div>
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-3 mb-4">
        <h2 className="text-lg font-bold">Live Agent Sessions</h2>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-xs text-gray-500">{connected ? '已连接' : '断开'}</span>
        <span className="text-xs text-gray-600 ml-auto">{filteredDiscovered.length}/{discovered.length}</span>
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-3 mb-4 space-y-3">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="搜索项目、agent、状态、cwd、指令或最近输出..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-gray-500"
        />
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={agentType}
            onChange={e => setAgentType(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-gray-500"
          >
            <option value="all">全部 agent 类型</option>
            {agentTypes.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as SessionStatus | 'all')}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 focus:outline-none focus:border-gray-500"
          >
            <option value="all">全部状态</option>
            {SESSION_STATUSES.map(status => (
              <option key={status} value={status}>{STATUS_LABELS[status]}</option>
            ))}
          </select>
          {summaryFilter !== 'all' && (
            <button
              onClick={() => setSummaryFilter('all')}
              className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-400"
            >
              清除摘要过滤
            </button>
          )}
        </div>
      </div>

      {discovered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <p className="text-lg mb-2">没有发现本机 coding agent</p>
          <p className="text-sm">支持 Codex、Claude Code、Kimi、Aider、Gemini。</p>
        </div>
      ) : (
        <div className="mb-6">
          {LANE_GROUPS.map(lane => {
            const sessions = laneGroups[lane.key] || []
            if (sessions.length === 0) return null
            return (
              <div key={lane.key} className="mb-4">
                <h3 className="text-xs font-medium text-gray-400 mb-2">
                  {lane.label} ({sessions.length})
                </h3>
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

      {tasks.length > 0 && (
        <div className="border-t border-gray-800 pt-4 mt-6">
          <button
            onClick={() => setShowManagedTasks(!showManagedTasks)}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            {showManagedTasks ? '隐藏托管任务' : `显示托管任务 (${tasks.length})`}
          </button>
          {showManagedTasks && (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 mt-3">
              {tasks.map(t => (
                <TaskCard key={t.task_id} task={t} onClick={() => setSelected(t)} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
