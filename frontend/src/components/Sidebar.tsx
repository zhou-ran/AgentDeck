import type { ReactNode } from 'react'
import { AgentBadge } from './AgentBadge'
import { StatusDot } from './StatusDot'

export type ViewKey = 'overview' | 'pinned' | 'running' | 'waiting' | 'completed' | 'failed' | 'projects' | 'agents' | 'logs' | 'settings' | 'ignored'

export interface SidebarItem {
  key: ViewKey
  label: string
  count?: number
  status?: string
}

export function Sidebar({
  activeView,
  onViewChange,
  items,
  projects,
  agents,
}: {
  activeView: ViewKey
  onViewChange: (view: ViewKey) => void
  items: SidebarItem[]
  projects: string[]
  agents: string[]
}) {
  return (
    <aside className="glass-panel fixed inset-x-3 bottom-3 top-3 z-40 hidden w-[240px] flex-col rounded-[22px] p-3 lg:flex">
      <div className="mb-4 flex items-center gap-2 px-2">
        <div className="relative h-9 w-9 rounded-2xl border border-[var(--border)] bg-white/70 shadow-sm dark:bg-white/10">
          <div className="absolute left-2 top-2 h-5 w-5 rounded-md border border-[var(--border-strong)] bg-white/80 dark:bg-white/10" />
          <div className="absolute left-3 top-3 h-5 w-5 rounded-md border border-[var(--border-strong)] bg-white/80 dark:bg-white/10" />
          <div className="absolute bottom-1.5 right-1.5 h-2.5 w-2.5 rounded-full bg-[var(--green)] shadow-[0_0_0_3px_rgba(48,209,88,0.16)]" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-app">AgentDeck</div>
          <div className="truncate text-[11px] text-muted">Local agent control</div>
        </div>
      </div>

      <nav className="space-y-5 overflow-y-auto pr-1">
        <SidebarSection title="Status">
          {items.map(item => (
            <button
              key={item.key}
              type="button"
              onClick={() => onViewChange(item.key)}
              className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition focus:outline focus:outline-2 ${
                activeView === item.key
                  ? 'bg-blue-500/10 text-app shadow-sm ring-1 ring-blue-500/20'
                  : 'text-muted-strong hover:bg-white/50 dark:hover:bg-white/10'
              }`}
            >
              {item.status && <StatusDot status={item.status} />}
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              {item.count !== undefined && (
                <span className="rounded-full bg-black/5 px-2 py-0.5 text-[11px] text-muted dark:bg-white/10">{item.count}</span>
              )}
            </button>
          ))}
        </SidebarSection>

        <SidebarSection title="Projects">
          {projects.length === 0 ? (
            <div className="px-3 py-1 text-xs text-muted">No live projects</div>
          ) : (
            projects.slice(0, 8).map(project => (
              <button
                key={project}
                type="button"
                className="flex w-full items-center gap-2 rounded-xl px-3 py-1.5 text-left text-xs text-muted-strong transition hover:bg-white/50 focus:outline focus:outline-2 dark:hover:bg-white/10"
              >
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--blue)]/70" />
                <span className="truncate">{project}</span>
              </button>
            ))
          )}
        </SidebarSection>

        <SidebarSection title="Agents">
          {agents.length === 0 ? (
            <div className="px-3 py-1 text-xs text-muted">No agents detected</div>
          ) : (
            agents.slice(0, 8).map(agent => (
              <div key={agent} className="px-2 py-1">
                <AgentBadge type={agent} />
              </div>
            ))
          )}
        </SidebarSection>
      </nav>
    </aside>
  )
}

function SidebarSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <div className="mb-1 px-3 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      <div className="space-y-1">{children}</div>
    </section>
  )
}
