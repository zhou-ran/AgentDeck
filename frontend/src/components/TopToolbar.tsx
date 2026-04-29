import type { ScanMeta } from '../types'
import { CommandSearch } from './CommandSearch'
import { StatusDot } from './StatusDot'

function fmtScanTime(ts?: number): string {
  if (!ts) return 'Not scanned'
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function TopToolbar({
  search,
  onSearch,
  onRefresh,
  onOpenPalette,
  connected,
  scanMeta,
  demoMode = false,
}: {
  search: string
  onSearch: (value: string) => void
  onRefresh: () => void
  onOpenPalette?: () => void
  connected: boolean
  scanMeta: ScanMeta | null
  demoMode?: boolean
}) {
  return (
    <header className="sticky top-0 z-30 px-4 pt-3 lg:px-6">
      <div className="glass-panel flex flex-wrap items-center gap-3 rounded-[22px] px-3 py-2 lg:flex-nowrap">
        <div className="hidden min-w-[240px] items-center gap-2 lg:flex">
          <div className="grid h-8 w-8 place-items-center rounded-xl border border-[var(--border)] bg-white/70 shadow-sm">
            <span className="h-3 w-3 rounded-full bg-[var(--blue)] shadow-[0_0_0_5px_rgba(0,122,255,0.14)]" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="truncate text-sm font-semibold leading-tight text-app">Mission Control</div>
              {demoMode && (
                <span className="rounded-full border border-blue-500/15 bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                  Demo
                </span>
              )}
            </div>
            <div className="truncate text-[11px] leading-tight text-muted">Codex, Claude, Kimi and local agents</div>
          </div>
        </div>

        <CommandSearch value={search} onChange={onSearch} onOpenPalette={onOpenPalette} />

        <div className="hidden items-center gap-2 rounded-full bg-white/55 px-2.5 py-1 text-xs text-muted shadow-sm md:flex">
          <StatusDot status={connected ? 'green' : 'red'} label={connected ? 'Live' : 'Offline'} pulse={connected} />
          <span className="hidden xl:inline">{fmtScanTime(scanMeta?.last_scan_time)}</span>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          className="rounded-full border border-[var(--border)] bg-white/75 px-3 py-2 text-sm font-medium text-app shadow-sm transition hover:bg-white focus:outline focus:outline-2"
        >
          Refresh
        </button>
        <button
          type="button"
          className="hidden rounded-full border border-[var(--border)] bg-white/45 px-3 py-2 text-sm font-medium text-muted shadow-sm transition hover:bg-white/70 hover:text-app focus:outline focus:outline-2 md:block"
          title="Task creation stays in the CLI/API."
        >
          New Task
        </button>
      </div>
    </header>
  )
}
