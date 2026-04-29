import { useEffect, useMemo, useState } from 'react'
import type { DiscoveredSession, Rule, ScanMeta, SystemMetrics, Task } from '../types'
import { api } from '../api/client'
import { AppShell } from './AppShell'
import { CommandPalette, type CommandItem } from './CommandPalette'
import { EmptyState, EmptyStatePanel } from './EmptyState'
import { LogViewer } from './LogViewer'
import { ProjectWorktreeView } from './ProjectWorktreeView'
import { SessionDetailPanel } from './SessionDetailPanel'
import { SettingsPanel } from './SettingsPanel'
import { SidebarItem, ViewKey } from './Sidebar'
import { StatCard } from './StatCard'
import { StatusDot, statusLabel } from './StatusDot'
import { SystemOverview } from './SystemOverview'
import { TaskDetailPanel } from './TaskDetailPanel'
import { TaskList } from './TaskList'
import { getProjectName } from '../utils/agentIdentity'
import { formatStatus } from '../utils/status'

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

function projectName(session: DiscoveredSession): string {
  return session.project_name?.name || session.project || 'Unknown project'
}

function isFailed(session: DiscoveredSession): boolean {
  return session.status_group === 'error' || session.status === 'error_hint' || session.status_dot === 'red' || session.error_hints.length > 0
}

function isWaiting(session: DiscoveredSession): boolean {
  return session.status_group === 'needs_input' || session.status === 'needs_input' || session.foreground?.waiting_input
}

function isRunning(session: DiscoveredSession): boolean {
  return session.status_group === 'working' || ['busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script'].includes(session.status)
}

function isIdle(session: DiscoveredSession): boolean {
  return session.status_group === 'idle' || ['idle', 'stale'].includes(session.status)
}

function tabIncludes(view: ViewKey, session: DiscoveredSession): boolean {
  if (view === 'ignored') return session.is_ignored
  if (session.is_ignored) return false
  if (view === 'overview' || view === 'logs' || view === 'projects' || view === 'agents') return true
  if (view === 'pinned') return session.is_pinned
  if (view === 'running') return isRunning(session)
  if (view === 'waiting') return isWaiting(session)
  if (view === 'failed') return isFailed(session)
  if (view === 'completed') return false
  if (view === 'settings') return false
  return true
}

function ruleMatchesSession(rule: Rule, session: DiscoveredSession): boolean {
  if (rule.type === 'session_id') return session.session_id === rule.value
  if (rule.type === 'project_key') return session.project_key === rule.value
  if (rule.type === 'cwd') return session.cwd === rule.value || session.project_root === rule.value
  if (rule.type === 'agent_type') return session.agent_type === rule.value
  if (rule.type === 'command_pattern') return session.root_cmd.toLowerCase().includes(rule.value.toLowerCase())
  return false
}

function sortSessions(sessions: DiscoveredSession[]): DiscoveredSession[] {
  return [...sessions].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
    if (isWaiting(a) !== isWaiting(b)) return isWaiting(a) ? -1 : 1
    if (isFailed(a) !== isFailed(b)) return isFailed(a) ? -1 : 1
    return (a.heartbeat_age_sec ?? 999999) - (b.heartbeat_age_sec ?? 999999)
  })
}

function completedToday(tasks: Task[]): number {
  const today = new Date().toDateString()
  return tasks.filter(task => task.status === 'completed' && task.ended_at && new Date(task.ended_at).toDateString() === today).length
}

function taskMatchesSearch(task: Task, q: string): boolean {
  return [task.name, task.project_name, task.project_dir, task.agent_type, task.status, task.current_activity, task.goal]
    .join(' ')
    .toLowerCase()
    .includes(q)
}

export function Dashboard({ tasks, discovered, systemMetrics, scanMeta, connected, demoMode = false }: {
  tasks: Task[]
  discovered: DiscoveredSession[]
  systemMetrics: SystemMetrics | null
  scanMeta: ScanMeta | null
  connected: boolean
  demoMode?: boolean
}) {
  const [search, setSearch] = useState('')
  const [activeView, setActiveView] = useState<ViewKey>('overview')
  const [allSessions, setAllSessions] = useState<DiscoveredSession[]>(discovered)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [pinRules, setPinRules] = useState<Rule[]>([])
  const [ignoredRules, setIgnoredRules] = useState<Rule[]>([])
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    setAllSessions(prev => {
      const prevById = new Map(prev.map(item => [item.session_id, item]))
      const liveIds = new Set(discovered.map(item => item.session_id))
      const retainedIgnored = prev.filter(item => item.is_ignored && !liveIds.has(item.session_id))
      // Merge SSE updates with local pin/ignore overrides so an optimistic
      // click is not undone by a stale SSE frame that arrives a moment later.
      // The server-truth is reconciled by refreshAllSessions() in the
      // background — this just prevents the visible "flash back".
      const merged = discovered.map(item => {
        const local = prevById.get(item.session_id)
        if (!local) return item
        return {
          ...item,
          is_ignored: local.is_ignored ? true : item.is_ignored,
          is_pinned: local.is_pinned ? true : item.is_pinned,
        }
      })
      return [...retainedIgnored, ...merged]
    })
  }, [discovered])

  async function refreshRules() {
    if (demoMode) return
    try {
      const [pins, ignored] = await Promise.all([
        api.listPins(),
        api.listIgnored(true),
      ])
      setPinRules(pins.rules)
      setIgnoredRules(ignored.rules)
    } catch (err) {
      console.error('Failed to fetch rules:', err)
    }
  }

  async function refreshAllSessions() {
    if (demoMode) {
      setAllSessions(discovered)
      return
    }
    try {
      const response = await api.discover(true)
      setAllSessions(response.sessions)
    } catch (err) {
      console.error('Failed to refresh sessions:', err)
    }
    await refreshRules()
  }

  useEffect(() => {
    refreshAllSessions()
  }, [])

  const projects = useMemo(() => {
    return Array.from(new Set(allSessions.filter(s => !s.is_ignored).map(projectName))).sort()
  }, [allSessions])

  const agents = useMemo(() => {
    return Array.from(new Set(allSessions.filter(s => !s.is_ignored).map(s => s.agent_type).filter(Boolean))).sort()
  }, [allSessions])

  const liveSessions = useMemo(() => allSessions.filter(s => !s.is_ignored), [allSessions])
  const waitingSessions = useMemo(() => liveSessions.filter(isWaiting), [liveSessions])
  const failedSessions = useMemo(() => liveSessions.filter(isFailed), [liveSessions])
  const runningSessions = useMemo(() => liveSessions.filter(isRunning), [liveSessions])
  const idleSessions = useMemo(() => liveSessions.filter(isIdle), [liveSessions])
  const pinnedSessions = useMemo(() => liveSessions.filter(s => s.is_pinned), [liveSessions])

  const sidebarItems: SidebarItem[] = [
    { key: 'overview', label: 'Overview', count: liveSessions.length, status: connected ? 'green' : 'red' },
    { key: 'running', label: 'Running', count: runningSessions.length, status: 'green' },
    { key: 'waiting', label: 'Waiting', count: waitingSessions.length, status: 'orange' },
    { key: 'completed', label: 'Completed', count: tasks.filter(t => t.status === 'completed').length, status: 'blue' },
    { key: 'failed', label: 'Failed', count: failedSessions.length + tasks.filter(t => t.status === 'failed').length, status: 'red' },
    { key: 'pinned', label: 'Pinned', count: Math.max(pinnedSessions.length, pinRules.length), status: 'yellow' },
    { key: 'projects', label: 'Projects', count: projects.length, status: 'blue' },
    { key: 'agents', label: 'Agents', count: agents.length, status: 'green' },
    { key: 'logs', label: 'Logs', count: liveSessions.filter(s => s.recent_logs?.length > 0).length, status: 'gray' },
    { key: 'settings', label: 'Settings', status: 'gray' },
    { key: 'ignored', label: 'Ignored', count: ignoredRules.filter(r => r.active).length, status: 'gray' },
  ]

  const visibleSessions = useMemo(() => {
    let result = allSessions.filter(s => tabIncludes(activeView, s))
    if (search.trim()) result = result.filter(s => sessionMatchesSearch(s, search.toLowerCase()))
    return sortSessions(result)
  }, [allSessions, activeView, search])

  const focusSessions = useMemo(() => {
    return sortSessions(liveSessions.filter(session => session.is_pinned || isWaiting(session) || isFailed(session) || (session.heartbeat_age_sec ?? 0) > 900))
  }, [liveSessions])

  const backgroundSessions = useMemo(() => {
    const focusIds = new Set(focusSessions.map(s => s.session_id))
    return sortSessions(liveSessions.filter(session => !focusIds.has(session.session_id) && (isRunning(session) || isIdle(session))))
  }, [liveSessions, focusSessions])

  const searchedManagedTasks = useMemo(() => {
    let result = tasks
    if (activeView === 'running') result = result.filter(task => ['running', 'busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script'].includes(task.status))
    if (activeView === 'waiting') result = result.filter(task => task.status === 'needs_input' || task.status === 'waiting_input' || task.status === 'waiting')
    if (activeView === 'completed') result = result.filter(task => task.status === 'completed')
    if (activeView === 'failed') result = result.filter(task => task.status === 'failed' || task.has_error_hint)
    if (activeView === 'pinned' || activeView === 'ignored' || activeView === 'projects' || activeView === 'agents' || activeView === 'logs' || activeView === 'settings') result = []
    if (!search.trim()) return result
    return result.filter(task => taskMatchesSearch(task, search.toLowerCase()))
  }, [tasks, search, activeView])

  const selectedSession = useMemo(() => {
    return allSessions.find(session => session.session_id === selectedSessionId) || visibleSessions[0] || null
  }, [allSessions, selectedSessionId, visibleSessions])

  const unmatchedPinRules = useMemo(() => {
    return pinRules.filter(rule => !allSessions.some(session => ruleMatchesSession(rule, session)))
  }, [pinRules, allSessions])

  useEffect(() => {
    setSelectedIndex(index => Math.min(index, Math.max(visibleSessions.length - 1, 0)))
  }, [visibleSessions.length])

  async function handleSessionAction(session: DiscoveredSession, action: 'pin' | 'ignore') {
    // Optimistic update: reflect the click instantly, then reconcile in background.
    const nextPinned = action === 'pin' ? !session.is_pinned : session.is_pinned
    const nextIgnored = action === 'ignore' ? !session.is_ignored : session.is_ignored
    setAllSessions(prev => prev.map(item =>
      item.session_id === session.session_id
        ? { ...item, is_pinned: nextPinned, is_ignored: nextIgnored }
        : item
    ))

    if (demoMode) return

    try {
      if (action === 'pin') {
        if (session.is_pinned) await api.unpinSession(session.session_id)
        else await api.pinSession(session.session_id)
      } else if (session.is_ignored) {
        await api.unignoreSession(session.session_id)
      } else {
        await api.ignoreSession(session.session_id)
      }
    } catch {
      // Roll back the optimistic update by re-syncing from the server.
      refreshAllSessions()
      return
    }
    // Reconcile in the background — do not block the UI.
    refreshAllSessions()
  }

  async function restoreIgnored(rule: Rule) {
    if (demoMode) return
    await api.restoreIgnored(rule.id)
    await refreshAllSessions()
  }

  function selectSession(session: DiscoveredSession) {
    preserveWindowScroll(() => {
      setSelectedTask(null)
      setSelectedSessionId(session.session_id)
    })
  }

  function selectTask(task: Task) {
    preserveWindowScroll(() => {
      setSelectedTask(task)
    })
  }

  const commands = useMemo<CommandItem[]>(() => {
    const items: CommandItem[] = [
      { id: 'nav-overview', group: 'Navigation', title: 'Open Overview', shortcut: 'G O', action: () => setActiveView('overview') },
      { id: 'nav-logs', group: 'Navigation', title: 'Open Logs', shortcut: 'L', action: () => setActiveView('logs') },
      { id: 'nav-settings', group: 'Navigation', title: 'Open Settings', action: () => setActiveView('settings') },
      { id: 'filter-running', group: 'Filters', title: 'Filter running tasks', shortcut: 'R', action: () => setActiveView('running') },
      { id: 'filter-waiting', group: 'Filters', title: 'Filter waiting input tasks', action: () => setActiveView('waiting') },
      { id: 'filter-failed', group: 'Filters', title: 'Filter failed tasks', shortcut: 'F', action: () => setActiveView('failed') },
      { id: 'action-refresh', group: 'Actions', title: 'Refresh discovery', shortcut: 'R', action: refreshAllSessions },
      { id: 'action-generate-handoff', group: 'Actions', title: 'Generate handoff', subtitle: 'Open task detail and use the safe handoff copy action.', disabled: !selectedSession, action: () => selectedSession && selectSession(selectedSession) },
    ]

    for (const session of allSessions.filter(s => !s.is_ignored).slice(0, 80)) {
      const path = session.cwd || session.project_root || ''
      items.push({
        id: `task-open-${session.session_id}`,
        group: 'Tasks',
        title: `Open ${session.display_name || getProjectName(session)}`,
        subtitle: `${session.agent_type || 'Agent'} · ${getProjectName(session)} · ${formatStatus(session.status)}`,
        keywords: [session.cwd, session.short_cwd, session.agent_type, session.status, session.current_activity],
        action: () => {
          selectSession(session)
          setActiveView('overview')
        },
      })
      items.push({
        id: `task-pin-${session.session_id}`,
        group: 'Tasks',
        title: `${session.is_pinned ? 'Unpin' : 'Pin'} ${session.display_name || getProjectName(session)}`,
        subtitle: 'Visibility rule only. Process is untouched.',
        keywords: ['pin', 'pinned', session.agent_type, getProjectName(session)],
        action: () => handleSessionAction(session, 'pin'),
      })
      items.push({
        id: `task-ignore-${session.session_id}`,
        group: 'Tasks',
        title: `${session.is_ignored ? 'Restore' : 'Ignore'} ${session.display_name || getProjectName(session)}`,
        subtitle: 'Hide only. Does not stop the process.',
        keywords: ['ignore', 'hide', 'restore', session.agent_type],
        action: () => handleSessionAction(session, 'ignore'),
      })
      if (path) {
        items.push({
          id: `task-copy-path-${session.session_id}`,
          group: 'Tasks',
          title: `Copy path for ${getProjectName(session)}`,
          subtitle: path,
          keywords: ['copy', 'path', 'project', session.short_cwd, session.cwd],
          action: () => navigator.clipboard.writeText(path),
        })
      }
    }

    for (const project of projects) {
      items.push({
        id: `project-${project}`,
        group: 'Projects',
        title: `Open project ${project}`,
        subtitle: 'Show Project Worktree View',
        keywords: [project],
        action: () => {
          setSearch(project)
          setActiveView('projects')
        },
      })
    }

    for (const agent of agents) {
      items.push({
        id: `agent-${agent}`,
        group: 'Agents',
        title: `Show ${formatStatus(agent)} sessions`,
        subtitle: 'Filter by agent type',
        keywords: [agent],
        action: () => {
          setSearch(agent)
          setActiveView('agents')
        },
      })
    }

    return items
  }, [allSessions, projects, agents, selectedSession])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const isTyping = target?.tagName === 'INPUT' || target?.tagName === 'SELECT' || target?.tagName === 'TEXTAREA' || target?.isContentEditable
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
        return
      }
      if (isTyping && event.key !== 'Escape') return

      if (event.key === 'j' || event.key === 'ArrowDown') {
        event.preventDefault()
        setSelectedIndex(i => Math.min(i + 1, Math.max(visibleSessions.length - 1, 0)))
      } else if (event.key === 'k' || event.key === 'ArrowUp') {
        event.preventDefault()
        setSelectedIndex(i => Math.max(i - 1, 0))
      } else if (event.key === 'Enter') {
        const current = visibleSessions[selectedIndex]
        if (current) selectSession(current)
      } else if (event.key === '/') {
        event.preventDefault()
        document.getElementById('session-filter')?.focus()
      } else if (event.key === 'Escape') {
        if (commandOpen) setCommandOpen(false)
        setSelectedTask(null)
      } else if (event.key.toLowerCase() === 'r') {
        refreshAllSessions()
      } else if (event.key.toLowerCase() === 'l') {
        setActiveView('logs')
      } else if (event.key.toLowerCase() === 'f') {
        setActiveView('failed')
      } else if (event.key.toLowerCase() === 'p') {
        const current = visibleSessions[selectedIndex]
        if (current) handleSessionAction(current, 'pin')
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visibleSessions, selectedIndex, commandOpen])

  const selectedTaskLive = selectedTask ? tasks.find(t => t.task_id === selectedTask.task_id) || selectedTask : null

  return (
    <AppShell
      activeView={activeView}
      onViewChange={view => {
        setActiveView(view)
        setSelectedTask(null)
      }}
      sidebarItems={sidebarItems}
      projects={projects}
      agents={agents}
      search={search}
      onSearch={setSearch}
      onRefresh={refreshAllSessions}
      connected={connected}
      scanMeta={scanMeta}
      onOpenPalette={() => setCommandOpen(true)}
      demoMode={demoMode}
      sidebarStats={(
        <DashboardStats
          active={liveSessions.length}
          running={runningSessions.length}
          waiting={waitingSessions.length}
          idle={idleSessions.length}
          failed={failedSessions.length}
          doneToday={completedToday(tasks)}
        />
      )}
    >
      <div className="space-y-5">
        {activeView === 'settings' ? (
          <SettingsPanel scanMeta={scanMeta} ignoredRules={ignoredRules} onRestoreIgnored={restoreIgnored} />
        ) : activeView === 'logs' ? (
          <LogsView sessions={visibleSessions} />
        ) : activeView === 'projects' ? (
          <ProjectWorktreeView sessions={visibleSessions} onSelect={session => {
            selectSession(session)
            setActiveView('overview')
          }} />
        ) : activeView === 'agents' ? (
          <AgentsView sessions={visibleSessions} onSelect={session => {
            selectSession(session)
            setActiveView('overview')
          }} />
        ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="space-y-5">
              {activeView === 'overview' ? (
                <>
                  <TaskList
                    title="Focus Now"
                    description="Pinned, failed, waiting, and stale sessions that deserve attention."
                    sessions={search.trim() ? visibleSessions : focusSessions}
                    selectedSessionId={selectedSession?.session_id || null}
                    onSelect={selectSession}
                    onAction={handleSessionAction}
                    emptyTitle={search.trim() ? 'No results found' : 'Nothing needs your attention'}
                    emptyDescription={search.trim() ? 'Try searching by task, project, agent, or status.' : 'Waiting input, failed, pinned, and stale sessions will appear here.'}
                  />
                  {!search.trim() && (
                    <TaskList
                      title="Running in Background"
                      description="Agents that are working or idle without immediate user action."
                      sessions={backgroundSessions}
                      selectedSessionId={selectedSession?.session_id || null}
                      onSelect={selectSession}
                      onAction={handleSessionAction}
                      emptyTitle="No background agents"
                      emptyDescription="Long-running and idle sessions will show up here."
                    />
                  )}
                </>
              ) : activeView === 'ignored' ? (
                <IgnoredView rules={ignoredRules} sessions={visibleSessions} onRestore={restoreIgnored} onSelect={selectSession} onAction={handleSessionAction} />
              ) : activeView === 'pinned' && unmatchedPinRules.length > 0 ? (
                <>
                  <UnmatchedPins rules={unmatchedPinRules} />
                  <TaskList
                    title="Pinned Sessions"
                    description="Live sessions matching pinned rules."
                    sessions={visibleSessions}
                    selectedSessionId={selectedSession?.session_id || null}
                    onSelect={selectSession}
                    onAction={handleSessionAction}
                    emptyTitle="No pinned sessions"
                    emptyDescription="Pinned sessions and matching rules will stay easy to reach."
                  />
                </>
              ) : (
                <TaskList
                  title={sidebarItems.find(item => item.key === activeView)?.label || 'Sessions'}
                  description="Compact view of live local agent sessions."
                  sessions={visibleSessions}
                  selectedSessionId={selectedSession?.session_id || null}
                  onSelect={selectSession}
                  onAction={handleSessionAction}
                  emptyTitle={search.trim() ? 'No results found' : 'No active agents'}
                  emptyDescription={search.trim() ? 'Try searching by task, project, agent, or status.' : 'Start a task from your terminal and it will appear here automatically.'}
                />
              )}

              {searchedManagedTasks.length > 0 && activeView !== 'ignored' && (
                <ManagedTasks tasks={searchedManagedTasks} selectedTaskId={selectedTaskLive?.task_id || null} onSelect={selectTask} />
              )}

              {systemMetrics && <SystemOverview metrics={systemMetrics} />}
            </div>

            <aside className="detail-sidebar hidden h-[calc(100vh-104px)] min-h-0 overflow-hidden xl:sticky xl:top-[92px] xl:block">
              <div className="h-full min-h-0 overflow-hidden">
                {selectedTaskLive ? (
                  <TaskDetailPanel task={selectedTaskLive} onClose={() => preserveWindowScroll(() => setSelectedTask(null))} />
                ) : (
                  <SessionDetailPanel session={selectedSession} onClose={() => preserveWindowScroll(() => setSelectedSessionId(null))} onAction={handleSessionAction} />
                )}
              </div>
            </aside>
          </div>
        )}
      </div>
      <CommandPalette open={commandOpen} commands={commands} onClose={() => setCommandOpen(false)} />
    </AppShell>
  )
}

function preserveWindowScroll(update: () => void) {
  const x = window.scrollX
  const y = window.scrollY
  update()
  requestAnimationFrame(() => window.scrollTo(x, y))
}

function DashboardStats({
  active,
  running,
  waiting,
  idle,
  failed,
  doneToday,
}: {
  active: number
  running: number
  waiting: number
  idle: number
  failed: number
  doneToday: number
}) {
  return (
    <section className="grid shrink-0 grid-cols-2 gap-2">
      <StatCard compact label="Active" value={active} detail={`${running} running`} status="green" />
      <StatCard compact label="Needs Input" value={waiting} detail="Waiting for you" status="orange" />
      <StatCard compact label="Idle" value={idle} detail="No immediate action" status="yellow" />
      <StatCard compact label="Failed" value={failed} detail="Review recommended" status="red" />
      <div className="col-span-2">
        <StatCard compact label="Done Today" value={doneToday} detail="Managed tasks" status="blue" />
      </div>
    </section>
  )
}

function ManagedTasks({ tasks, selectedTaskId, onSelect }: { tasks: Task[]; selectedTaskId: string | null; onSelect: (task: Task) => void }) {
  return (
    <section className="glass-panel-strong overflow-hidden rounded-[22px]">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-app">Managed Tasks</h2>
          <p className="mt-0.5 text-xs text-muted">CLI-created tasks with plans, notes, handoff, and logs.</p>
        </div>
        <span className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">{tasks.length}</span>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {tasks.map(task => (
          <button
            key={task.task_id}
            type="button"
            onClick={() => onSelect(task)}
            className={`grid w-full items-center gap-3 px-4 py-3 text-left text-sm transition md:grid-cols-[16px_minmax(180px,1.2fr)_minmax(180px,1fr)_110px_110px] ${
              selectedTaskId === task.task_id ? 'bg-blue-500/[0.09]' : 'hover:bg-black/[0.035] dark:hover:bg-white/[0.055]'
            }`}
          >
            <StatusDot status={task.status} pulse={task.status === 'running' || task.status === 'busy'} />
            <div className="min-w-0">
              <div className="truncate font-medium text-app">{task.name}</div>
              <div className="mt-0.5 truncate text-xs text-muted">{task.goal || task.command}</div>
            </div>
            <div className="hidden truncate text-muted-strong md:block">{task.project_name || task.short_cwd || task.project_dir}</div>
            <div className="hidden text-xs text-muted md:block">{statusLabel(task.status)}</div>
            <div className="hidden text-xs text-muted md:block">{task.agent_type || 'Unknown'}</div>
          </button>
        ))}
      </div>
    </section>
  )
}

function LogsView({ sessions }: { sessions: DiscoveredSession[] }) {
  const lines = sessions.flatMap(session => {
    const label = `[${session.agent_type || 'agent'}:${projectName(session)}]`
    return (session.recent_logs || []).slice(-20).map(line => `${label} ${line}`)
  })

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="glass-panel-strong rounded-[22px] p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-app">Live Logs</h2>
            <p className="mt-0.5 text-xs text-muted">Apple Console-style tail from visible sessions.</p>
          </div>
          <span className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">{lines.length} lines</span>
        </div>
        <LogViewer lines={lines} height="620px" />
      </section>
      <SystemOverview metrics={null} />
    </div>
  )
}

function ProjectsView({ sessions, onSelect }: { sessions: DiscoveredSession[]; onSelect: (session: DiscoveredSession) => void }) {
  const groups = new Map<string, DiscoveredSession[]>()
  for (const session of sessions) {
    const key = projectName(session)
    groups.set(key, [...(groups.get(key) || []), session])
  }

  if (groups.size === 0) {
    return <EmptyStatePanel title="No projects" description="Projects appear once local agent sessions are discovered." />
  }

  return (
    <div className="space-y-4">
      {Array.from(groups.entries()).map(([project, items]) => (
        <section key={project} className="glass-panel-strong overflow-hidden rounded-[22px]">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-app">{project}</h2>
              <p className="mt-0.5 text-xs text-muted">{items.length} live session{items.length === 1 ? '' : 's'}</p>
            </div>
            <span className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">
              {items.filter(isFailed).length} failed
            </span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {items.map(session => (
              <button key={session.session_id} type="button" onClick={() => onSelect(session)} className="grid w-full gap-3 px-4 py-3 text-left text-sm transition hover:bg-black/[0.035] dark:hover:bg-white/[0.055] md:grid-cols-[16px_160px_minmax(180px,1fr)_120px]">
                <StatusDot status={session.status_dot || session.status} />
                <span className="truncate text-app">{session.git_status_detail?.branch || session.project_status?.branch || 'Unknown branch'}</span>
                <span className="truncate mono text-xs text-muted">{session.short_cwd || session.cwd}</span>
                <span className="text-muted">{statusLabel(session.status)}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function AgentsView({ sessions, onSelect }: { sessions: DiscoveredSession[]; onSelect: (session: DiscoveredSession) => void }) {
  const groups = new Map<string, DiscoveredSession[]>()
  for (const session of sessions) {
    const key = session.agent_type || 'unknown'
    groups.set(key, [...(groups.get(key) || []), session])
  }

  if (groups.size === 0) {
    return <EmptyStatePanel title="No agents detected" description="Start Codex, Claude, Kimi, Aider, or another supported tool to see it here." />
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {Array.from(groups.entries()).map(([agent, items]) => (
        <section key={agent} className="glass-panel-strong overflow-hidden rounded-[22px]">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <h2 className="text-sm font-semibold text-app">{statusLabel(agent)}</h2>
            <span className="rounded-full bg-black/[0.04] px-2.5 py-1 text-xs text-muted dark:bg-white/[0.08]">{items.length}</span>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {items.map(session => (
              <button key={session.session_id} type="button" onClick={() => onSelect(session)} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition hover:bg-black/[0.035] dark:hover:bg-white/[0.055]">
                <StatusDot status={session.status_dot || session.status} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-app">{projectName(session)}</div>
                  <div className="truncate text-xs text-muted">{session.current_activity || session.short_cwd || session.cwd}</div>
                </div>
                <span className="text-xs text-muted">{statusLabel(session.status)}</span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function IgnoredView({
  rules,
  sessions,
  onRestore,
  onSelect,
  onAction,
}: {
  rules: Rule[]
  sessions: DiscoveredSession[]
  onRestore: (rule: Rule) => void
  onSelect: (session: DiscoveredSession) => void
  onAction: (session: DiscoveredSession, action: 'pin' | 'ignore') => void
}) {
  return (
    <div className="space-y-5">
      <TaskList
        title="Ignored Sessions"
        description="Hidden only. Processes, logs, and project files are untouched."
        sessions={sessions}
        selectedSessionId={null}
        onSelect={onSelect}
        onAction={onAction}
        emptyTitle="No ignored sessions"
        emptyDescription="Sessions you hide from the main dashboard appear here."
      />
      <section className="glass-panel-strong overflow-hidden rounded-[22px]">
        <div className="px-4 py-3">
          <h2 className="text-sm font-semibold text-app">Ignored Rules</h2>
          <p className="mt-0.5 text-xs text-muted">Restoring a rule only changes visibility.</p>
        </div>
        {rules.length === 0 ? (
          <EmptyState title="No ignored rules" description="Hide rules are created when you ignore a session." />
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {rules.map(rule => (
              <div key={rule.id} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[130px_minmax(0,1fr)_110px]">
                <span className="text-muted">{rule.type}</span>
                <span className="break-all mono text-xs text-app">{rule.value}</span>
                <div className="text-right">
                  {rule.active ? (
                    <button type="button" onClick={() => onRestore(rule)} className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-app transition hover:bg-black/5 dark:hover:bg-white/10">
                      Restore
                    </button>
                  ) : (
                    <span className="text-xs text-muted">Restored</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function UnmatchedPins({ rules }: { rules: Rule[] }) {
  return (
    <section className="glass-panel-strong rounded-[22px] p-4">
      <h2 className="text-sm font-semibold text-app">Pinned Rules Without Live Sessions</h2>
      <div className="mt-3 space-y-2">
        {rules.map(rule => (
          <div key={rule.id} className="grid gap-2 rounded-2xl bg-black/[0.03] px-3 py-2 text-xs dark:bg-white/[0.04] md:grid-cols-[120px_1fr_160px]">
            <span className="text-muted">{rule.type}</span>
            <span className="break-all mono text-app">{rule.value}</span>
            <span className="text-muted">{rule.note || rule.created_at}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
