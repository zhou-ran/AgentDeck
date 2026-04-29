import type { SystemMetrics } from '../types'
import { formatBytesRate } from '../utils/format'

export function SystemOverview({ metrics }: { metrics: SystemMetrics | null }) {
  if (!metrics) return null

  return (
    <section className="glass-panel rounded-[22px] px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">System Load</h3>
        <span className="rounded-full bg-white/55 px-2 py-0.5 text-[11px] text-muted shadow-sm">Host</span>
      </div>
      <div className="grid grid-cols-2 gap-x-5 gap-y-3 text-sm md:grid-cols-4">
        <div className="min-w-0">
          <div className="mb-1 flex items-center justify-between gap-2 text-xs">
            <span className="text-muted">CPU</span>
            <span className="mono text-muted-strong">{metrics.cpu_percent.toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-black/[0.055]">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  metrics.cpu_percent > 80 ? 'bg-[var(--red)]' :
                  metrics.cpu_percent > 50 ? 'bg-[var(--yellow)]' : 'bg-[var(--green)]'
                }`}
                style={{ width: `${Math.min(100, metrics.cpu_percent)}%` }}
              />
            </div>
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-1 flex items-center justify-between gap-2 text-xs">
            <span className="text-muted">Memory</span>
            <span className="mono text-muted-strong">{metrics.mem_percent.toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 rounded-full bg-black/[0.055]">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  metrics.mem_percent > 85 ? 'bg-[var(--red)]' :
                  metrics.mem_percent > 60 ? 'bg-[var(--yellow)]' : 'bg-[var(--blue)]'
                }`}
                style={{ width: `${Math.min(100, metrics.mem_percent)}%` }}
              />
            </div>
          </div>
          <div className="mt-1 text-[10px] text-muted">{metrics.mem_used_gb}/{metrics.mem_total_gb} GB</div>
        </div>

        {metrics.disk_usages.map((disk) => (
          <div key={disk.path} className="min-w-0">
            <div className="mb-1 flex items-center justify-between gap-2 text-xs">
              <span className="truncate text-muted">Disk {disk.path.length > 20 ? '...' + disk.path.slice(-18) : disk.path}</span>
              <span className="mono text-muted-strong">{disk.percent}%</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-1.5 flex-1 rounded-full bg-black/[0.055]">
                <div
                  className={`h-1.5 rounded-full transition-all ${
                    disk.percent > 90 ? 'bg-[var(--red)]' :
                    disk.percent > 75 ? 'bg-[var(--yellow)]' : 'bg-[var(--purple)]'
                  }`}
                  style={{ width: `${Math.min(100, disk.percent)}%` }}
                />
              </div>
            </div>
            <div className="mt-1 text-[10px] text-muted">{disk.used_gb}/{disk.total_gb} GB</div>
          </div>
        ))}
      </div>

      {metrics.net_interfaces.length > 0 && (
        <div className="mt-3 border-t border-[var(--border)] pt-3">
          <div className="mb-2 text-xs text-muted">Network</div>
          <div className="flex flex-wrap gap-4">
            {metrics.net_interfaces.map((iface) => (
              <div key={iface.name} className="text-xs">
                <span className="mono text-muted-strong">{iface.name}</span>
                <span className="ml-2 text-[var(--green)]">up {formatBytesRate(iface.tx_mbps)}</span>
                <span className="ml-2 text-[var(--blue)]">down {formatBytesRate(iface.rx_mbps)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
