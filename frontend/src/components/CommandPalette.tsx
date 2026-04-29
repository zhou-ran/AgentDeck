import { useEffect, useMemo, useState } from 'react'

export interface CommandItem {
  id: string
  group: 'Tasks' | 'Projects' | 'Agents' | 'Filters' | 'Actions' | 'Navigation'
  title: string
  subtitle?: string
  keywords?: string[]
  shortcut?: string
  disabled?: boolean
  action: () => void
}

export function CommandPalette({
  open,
  commands,
  onClose,
}: {
  open: boolean
  commands: CommandItem[]
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const items = q ? commands.filter(command => fuzzyMatch(command, q)) : commands
    return items.slice(0, 80)
  }, [commands, query])

  useEffect(() => {
    if (!open) return
    setQuery('')
    setSelected(0)
  }, [open])

  useEffect(() => {
    setSelected(index => Math.min(index, Math.max(filtered.length - 1, 0)))
  }, [filtered.length])

  useEffect(() => {
    if (!open) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      } else if (event.key === 'ArrowDown') {
        event.preventDefault()
        setSelected(index => Math.min(index + 1, Math.max(filtered.length - 1, 0)))
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        setSelected(index => Math.max(index - 1, 0))
      } else if (event.key === 'Enter') {
        event.preventDefault()
        const command = filtered[selected]
        if (command && !command.disabled) {
          command.action()
          onClose()
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, filtered, selected, onClose])

  if (!open) return null

  const grouped = filtered.reduce<Record<string, CommandItem[]>>((acc, command) => {
    acc[command.group] = [...(acc[command.group] || []), command]
    return acc
  }, {})

  return (
    <div className="fixed inset-0 z-[80] bg-black/15 backdrop-blur-sm" onMouseDown={onClose}>
      <div
        className="mx-auto mt-[10vh] w-[min(760px,calc(100vw-2rem))] overflow-hidden rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] shadow-[0_24px_80px_rgba(0,0,0,0.22)] backdrop-blur-2xl motion-safe:animate-[palette-in_160ms_ease-out]"
        onMouseDown={event => event.stopPropagation()}
      >
        <div className="border-b border-[var(--border)] px-4 py-3">
          <div className="flex items-center gap-3">
            <span className="text-muted">⌘K</span>
            <input
              autoFocus
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search tasks, projects, agents, filters..."
              className="min-w-0 flex-1 bg-transparent text-[17px] text-app outline-none placeholder:text-[var(--muted)]"
            />
            <span className="hidden rounded-full bg-black/[0.04] px-2 py-0.5 text-[11px] text-muted dark:bg-white/[0.08] sm:inline">Esc</span>
          </div>
        </div>

        <div className="max-h-[62vh] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="px-4 py-10 text-center">
              <div className="text-sm font-semibold text-app">No results found</div>
              <div className="mt-1 text-xs text-muted">Try searching by task, project, agent, or status.</div>
            </div>
          ) : (
            Object.entries(grouped).map(([group, items]) => (
              <section key={group} className="py-1">
                <div className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{group}</div>
                <div className="space-y-1">
                  {items.map(command => {
                    const index = filtered.indexOf(command)
                    return (
                      <button
                        key={command.id}
                        type="button"
                        disabled={command.disabled}
                        onMouseEnter={() => setSelected(index)}
                        onClick={() => {
                          if (command.disabled) return
                          command.action()
                          onClose()
                        }}
                        className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition ${
                          selected === index ? 'bg-blue-500/[0.10] ring-1 ring-blue-500/15' : 'hover:bg-black/[0.035] dark:hover:bg-white/[0.055]'
                        } ${command.disabled ? 'cursor-not-allowed opacity-45' : ''}`}
                      >
                        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-xl bg-black/[0.04] text-xs text-muted dark:bg-white/[0.08]">
                          {command.group.slice(0, 1)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium text-app">{command.title}</div>
                          {command.subtitle && <div className="mt-0.5 truncate text-xs text-muted">{command.subtitle}</div>}
                        </div>
                        {command.shortcut && <span className="rounded-full bg-black/[0.04] px-2 py-0.5 text-[11px] text-muted dark:bg-white/[0.08]">{command.shortcut}</span>}
                      </button>
                    )
                  })}
                </div>
              </section>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function fuzzyMatch(command: CommandItem, query: string): boolean {
  const haystack = [command.title, command.subtitle, command.group, ...(command.keywords || [])].join(' ').toLowerCase()
  if (haystack.includes(query)) return true
  let pos = 0
  for (const char of haystack) {
    if (char === query[pos]) pos += 1
    if (pos === query.length) return true
  }
  return false
}
