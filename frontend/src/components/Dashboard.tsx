import { useEffect, useMemo, useState } from 'react'
import type { DiscoveredSession, Rule, ScanMeta, SessionStatus, SystemMetrics, Task } from '../types'
import { api } from '../api/client'
import { TaskCard } from './TaskCard'
import { TaskDetail } from './TaskDetail'
import { DiscoveredCard } from './DiscoveredCard'
import { SystemOverview } from './SystemOverview'

type TabKey = 'all' | 'pinned' | 'needs_input' | 'working' | 'testing' | 'idle' | 'errors' | 'ignored'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pinned', label: 'Pinned' },
  { key: 'needs_input', label: 'Needs Input' },
  { key: 'working', label: 'Working' },
  { key: 'testing', label: 'Testing' },
  { key: 'idle', label: 'Idle' },
  { key: 'errors', label: 'Errors' },
  { key: 'ignored', label: 'Ignored' },
]

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
  needs_input: 'needs_input',
  testing: 'testing',
  editing: 'editing',
  searching: 'searching',
  git_ops: 'git_ops',
  running_script: 'running_script',
  busy: 'busy',
  idle: 'idle',
  stale: 'stale',
  error_hint: 'error_hint',
  unknown: 'unknown',
}

const DOT_CLASS: Record<string, string> = {
  red: 'bg-red-400',
  yellow: 'bg-yellow-300',
  green: 'bg-emerald-400',
  gray: 'bg-gray-600',
}

function sessionMatchesSearch(session: DiscoveredSession, q: string): boolean {
  const haystack = [
    session.project_name?.name,
    session.project,
    session.display_name,
    session.agent_type,
    session.status,
    session.cwd,
    session.short_cwd,
    session.current_activity,
    session.user_instruction,
    session.last_user_message,
    session.recent_output,
    session.root_cmd,
  ].join(' ').toLowerCase()
  return haystack.includes(q)
}

function tabIncludes(tab: TabKey, session: DiscoveredSession): boolean {
  if (tab === 'ignored') return session.is_ignored
  if (session.is_ignored) return false
  if (tab === 'all') return true
  if (tab === 'pinned') return session.is_pinned
  if (tab === 'needs_input') return session.status_group === 'needs_input'
  if (tab === 'working') return session.status_group === 'working'
  if (tab === 'testing') return session.status === 'testing'
  if (tab === 'idle') return session.status_group === 'idle'
  if (tab === 'errors') return session.status_group === 'error' || session.error_hints.length > 0
  return true
}

function tabDot(sessions: DiscoveredSession[]): string {
  if (sessions.length === 0) return 'gray'
  if (sessions.some(s => s.status_dot === 'red')) return 'red'
  if (sessions.some(s => s.status_dot === 'yellow')) return 'yellow'
  return 'green'
}

function fmtScanTime(ts?: number): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleTimeString()
}

function ruleMatchesSession(rule: Rule, session: DiscoveredSession): boolean {
  if (rule.type === 'session_id') return session.session_id === rule.value
  if (rule.type === 'project_key') return session.project_key === rule.value
  if (rule.type === 'cwd') return session.cwd === rule.value || session.project_root === rule.value
  if (rule.type === 'agent_type') return session.agent_type === rule.value
  if (rule.type === 'command_pattern') return session.root_cmd.toLowerCase().includes(rule.value.toLowerCase())
  return false
}

export function Dashboard({ tasks, discovered, systemMetrics, scanMeta, connected }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  scanMeta: ScanMeta | null
  connected: boolean
}) {
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [search, setSearch] = useState('')
  const [agentType, setAgentType] = useState('all')
  const [statusFilter, setStatusFilter] = useState<SessionStatus | 'all'>('all')
  const [activeTab, setActiveTab] = useState<TabKey>('all')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [showManagedTasks, setShowManagedTasks] = useState(false)
  const [allSessions, setAllSessions] = useState<DiscoveredSession[]>(discovered)
  const [pinRules, setPinRules] = useState<Rule[]>([])
  const [ignoredRules, setIgnoredRules] = useState<Rule[]>([])

  useEffect(() => {
    setAllSessions(prev => {
      const merged = new Map<string, DiscoveredSession>()
      for (const item of prev) merged.set(item.session_id, item)
      for (const item of discovered) merged.set(item.session_id, item)
      return Array.from(merged.values())
    })
  }, [discovered])

  async function refreshRules() {
    try {
      const [pins, ignored] = await Promise.all([
        api.listPins(),
        api.listIgnored(true),
      ])
      setPinRules(pins.rules)
      setIgnoredRules(ignored.rules)
    } catch {
      // Rules are auxiliary; live sessions continue via SSE.
    }
  }

  async function refreshAllSessions() {
    try {
      const response = await api.discover(true)
      setAllSessions(response.sessions)
    } catch {
      // SSE remains the primary live source.
    }
    await refreshRules()
  }

  useEffect(() => {
    refreshAllSessions()
    const id = window.setInterval(refreshAllSessions, 10000)
    return () => window.clearInterval(id)
  }, [])

  const agentTypes = useMemo(() => {
    return Array.from(new Set(allSessions.map(s => s.agent_type).filter(Boolean))).sort()
  }, [allSessions])

  const tabCounts = useMemo(() => {
    const entries = new Map<TabKey, DiscoveredSession[]>()
    for (const tab of TABS) {
      entries.set(tab.key, allSessions.filter(s => tabIncludes(tab.key, s)))
    }
    return entries
  }, [allSessions])

  const filteredSessions = useMemo(() => {
    let result = allSessions.filter(s => tabIncludes(activeTab, s))
    if (agentType !== 'all') result = result.filter(s => s.agent_type === agentType)
    if (statusFilter !== 'all') result = result.filter(s => s.status === statusFilter)
    if (search.trim()) result = result.filter(s => sessionMatchesSearch(s, search.toLowerCase()))
    return result.sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
      return (a.heartbeat_age_sec ?? 999999) - (b.heartbeat_age_sec ?? 999999)
    })
  }, [allSessions, activeTab, agentType, statusFilter, search])

  const unmatchedPinRules = useMemo(() => {
    return pinRules.filter(rule => !allSessions.some(session => ruleMatchesSession(rule, session)))
  }, [pinRules, allSessions])

  useEffect(() => {
    setSelectedIndex(index => Math.min(index, Math.max(filteredSessions.length - 1, 0)))
  }, [filteredSessions.length])

  async function handleSessionAction(session: DiscoveredSession, action: 'pin' | 'ignore') {
    if (action === 'pin') {
      if (session.is_pinned) await api.unpinSession(session.session_id)
      else await api.pinSession(session.session_id)
    } else {
      if (session.is_ignored) await api.unignoreSession(session.session_id)
      else await api.ignoreSession(session.session_id)
    }
    await refreshAllSessions()
  }

  async function restoreIgnored(rule: Rule) {
    await api.restoreIgnored(rule.id)
    await refreshAllSessions()
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const isTyping = target?.tagName === 'INPUT' || target?.tagName === 'SELECT' || target?.tagName === 'TEXTAREA'
      if (isTyping && event.key !== 'Escape') return

      if (event.key === 'j' || event.key === 'ArrowDown') {
        event.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, Math.max(filteredSessions.length - 1, 0)))
      } else if (event.key === 'k' || event.key === 'ArrowUp') {
        event.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (event.key === 'Enter') {
        const current = filteredSessions[selectedIndex]
        if (current) setExpandedId(id => id === current.session_id ? null : current.session_id)
      } else if (event.key === '/') {
        event.preventDefault()
        document.getElementById('session-filter')?.focus()
      } else if (event.key === 'Escape') {
        setExpandedId(null)
        ;(document.activeElement as HTMLElement | null)?.blur()
      } else if (/^[1-8]$/.test(event.key)) {
        setActiveTab(TABS[Number(event.key) - 1].key)
      } else if (event.key === 'r') {
        refreshAllSessions()
      } else if (event.key === 'p' || event.key === 'i') {
        const current = filteredSessions[selectedIndex]
        if (current) handleSessionAction(current, event.key === 'p' ? 'pin' : 'ignore')
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [filteredSessions, selectedIndex])

  const liveCount = allSessions.filter(s => !s.is_ignored).length

  if (selectedTask) {
    const current = tasks.find(t => t.task_id === selectedTask.task_id) || selectedTask
    return <TaskDetail task={current} onBack={() => setSelectedTask(null)} />
  }

  return (
    <div>
      <SystemOverview metrics={systemMetrics} />

      <div className="mb-4 border border-gray-800 bg-[#080b10] px-3 py-2 font-mono text-xs text-gray-400">
        <span className="text-cyan-300">[LOCAL]</span> agentdeck :: host={scanMeta?.hostname || 'unknown'} :: scan={scanMeta?.scan_interval ?? 2}s :: last={fmtScanTime(scanMeta?.last_scan_time)} :: sessions={scanMeta?.active_sessions_count ?? liveCount} :: {connected ? 'connected' : 'offline'}
      </div>

      <div className="mb-4 flex flex-wrap gap-1 font-mono text-xs">
        {TABS.map((tab, index) => {
          const sessions = tabCounts.get(tab.key) || []
          const active = activeTab === tab.key
          const dot = tabDot(sessions)
          const count = tab.key === 'ignored' ? ignoredRules.filter(r => r.active).length : tab.key === 'pinned' ? Math.max(sessions.length, pinRules.length) : sessions.length
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`border px-2 py-1 ${active ? 'border-cyan-600 bg-gray-900 text-cyan-200' : 'border-gray-800 bg-[#080b10] text-gray-400 hover:border-gray-600'}`}
            >
              <span className={`mr-1 inline-block h-2 w-2 rounded-full ${DOT_CLASS[dot]}`} />
              {index + 1}:{tab.label} {count}
            </button>
          )
        })}
      </div>

      <div className="mb-4 grid gap-2 border border-gray-800 bg-[#080b10] p-3 md:grid-cols-[1fr_auto_auto]">
        <input
          id="session-filter"
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="/ filter: precancer codex testing"
          className="border border-gray-800 bg-gray-950 px-3 py-1.5 font-mono text-xs text-gray-200 outline-none placeholder-gray-600 focus:border-cyan-700"
        />
        <select
          value={agentType}
          onChange={e => setAgentType(e.target.value)}
          className="border border-gray-800 bg-gray-950 px-2 py-1.5 font-mono text-xs text-gray-200 outline-none focus:border-cyan-700"
        >
          <option value="all">agent:all</option>
          {agentTypes.map(type => <option key={type} value={type}>{type}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as SessionStatus | 'all')}
          className="border border-gray-800 bg-gray-950 px-2 py-1.5 font-mono text-xs text-gray-200 outline-none focus:border-cyan-700"
        >
          <option value="all">status:all</option>
          {SESSION_STATUSES.map(status => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
        </select>
      </div>

      {activeTab === 'ignored' && (
        <div className="mb-4 border border-gray-800 bg-[#080b10] font-mono text-xs">
          <div className="border-b border-gray-800 px-3 py-2 text-gray-500">Ignored Rules: hide only; no kill, no log deletion, no project deletion.</div>
          <div className="overflow-auto">
            <table className="w-full text-left">
              <thead className="text-gray-600">
                <tr>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Value</th>
                  <th className="px-3 py-2">Note</th>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {ignoredRules.map(rule => (
                  <tr key={rule.id} className="border-t border-gray-900 text-gray-400">
                    <td className="px-3 py-2">{rule.type}</td>
                    <td className="max-w-[360px] break-all px-3 py-2">{rule.value}</td>
                    <td className="px-3 py-2">{rule.note || '-'}</td>
                    <td className="px-3 py-2">{rule.created_at}</td>
                    <td className="px-3 py-2">{rule.active ? 'active' : 'restored'}</td>
                    <td className="px-3 py-2">
                      {rule.active && (
                        <button onClick={() => restoreIgnored(rule)} className="border border-gray-700 px-2 py-1 text-gray-300 hover:border-cyan-700">
                          restore
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {ignoredRules.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-6 text-gray-600">&gt; no ignored rules</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'pinned' && unmatchedPinRules.length > 0 && (
        <div className="mb-4 border border-gray-800 bg-[#080b10] p-3 font-mono text-xs text-gray-500">
          <div className="mb-2 text-gray-400">Pinned rules without live matching sessions</div>
          {unmatchedPinRules.map(rule => (
            <div key={rule.id} className="grid gap-1 border-t border-gray-900 py-2 md:grid-cols-[100px_1fr_160px]">
              <span>{rule.type}</span>
              <span className="break-all">{rule.value}</span>
              <span>{rule.note || rule.created_at}</span>
            </div>
          ))}
        </div>
      )}

      {filteredSessions.length === 0 ? (
        <div className="border border-gray-800 bg-[#080b10] p-8 font-mono text-sm text-gray-500">
          <div>&gt; no live agent sessions detected</div>
          <div>&gt; start codex/claude/kimi-code or check scanner patterns</div>
        </div>
      ) : (
        <div className="grid gap-2">
          {filteredSessions.map((session, index) => (
            <DiscoveredCard
              key={session.session_id}
              session={session}
              expanded={expandedId === session.session_id}
              selected={index === selectedIndex}
              onToggle={() => {
                setSelectedIndex(index)
                setExpandedId(id => id === session.session_id ? null : session.session_id)
              }}
              onAction={action => handleSessionAction(session, action)}
            />
          ))}
        </div>
      )}

      {tasks.length > 0 && (
        <div className="mt-6 border-t border-gray-800 pt-4">
          <button onClick={() => setShowManagedTasks(!showManagedTasks)} className="font-mono text-xs text-gray-500 hover:text-gray-300">
            {showManagedTasks ? 'hide managed tasks' : `managed tasks (${tasks.length})`}
          </button>
          {showManagedTasks && (
            <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {tasks.map(t => <TaskCard key={t.task_id} task={t} onClick={() => setSelectedTask(t)} />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
