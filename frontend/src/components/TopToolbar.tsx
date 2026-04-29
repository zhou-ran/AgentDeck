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
}: {
  search: string
  onSearch: (value: string) => void
  onRefresh: () => void
  onOpenPalette?: () => void
  connected: boolean
  scanMeta: ScanMeta | null
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-3 backdrop-blur-2xl lg:px-6">
      <div className="flex items-center gap-3">
        <div className="hidden min-w-[180px] items-center gap-2 lg:flex">
          <div className="grid h-8 w-8 place-items-center rounded-xl border border-[var(--border)] bg-white/60 shadow-sm dark:bg-white/10">
            <span className="h-3 w-3 rounded-full bg-[var(--blue)] shadow-[0_0_0_5px_rgba(0,122,255,0.14)]" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight text-app">AgentDeck</div>
            <div className="text-[11px] leading-tight text-muted">Mission Control</div>
          </div>
        </div>

        <CommandSearch value={search} onChange={onSearch} onOpenPalette={onOpenPalette} />

        <div className="hidden items-center gap-2 text-xs text-muted md:flex">
          <StatusDot status={connected ? 'green' : 'red'} label={connected ? 'Live' : 'Offline'} pulse={connected} />
          <span className="hidden xl:inline">Last scan {fmtScanTime(scanMeta?.last_scan_time)}</span>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          className="rounded-full border border-[var(--border)] bg-white/70 px-3 py-2 text-sm font-medium text-app shadow-sm transition hover:bg-white focus:outline focus:outline-2 dark:bg-white/10 dark:hover:bg-white/20"
        >
          Refresh
        </button>
        <button
          type="button"
          className="hidden rounded-full border border-[var(--border)] bg-white/70 px-3 py-2 text-sm font-medium text-app shadow-sm transition hover:bg-white focus:outline focus:outline-2 dark:bg-white/10 dark:hover:bg-white/20 md:block"
          title="Task creation stays in the CLI/API."
        >
          New Task
        </button>
      </div>
    </header>
  )
}
