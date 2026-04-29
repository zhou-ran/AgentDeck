import type { SystemMetrics } from '../types'
import { formatBytesRate } from '../utils/format'

export function SystemOverview({ metrics }: { metrics: SystemMetrics | null }) {
  if (!metrics) return null

  return (
    <div className="glass-panel-strong rounded-[22px] p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">System Overview</h3>
      <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div>
          <div className="mb-1 text-xs text-muted">CPU</div>
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
              <div
                className={`h-2 rounded-full transition-all ${
                  metrics.cpu_percent > 80 ? 'bg-[var(--red)]' :
                  metrics.cpu_percent > 50 ? 'bg-[var(--yellow)]' : 'bg-[var(--green)]'
                }`}
                style={{ width: `${Math.min(100, metrics.cpu_percent)}%` }}
              />
            </div>
            <span className="mono w-12 text-right text-xs text-app">{metrics.cpu_percent.toFixed(1)}%</span>
          </div>
        </div>

        <div>
          <div className="mb-1 text-xs text-muted">Memory</div>
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
              <div
                className={`h-2 rounded-full transition-all ${
                  metrics.mem_percent > 85 ? 'bg-[var(--red)]' :
                  metrics.mem_percent > 60 ? 'bg-[var(--yellow)]' : 'bg-[var(--blue)]'
                }`}
                style={{ width: `${Math.min(100, metrics.mem_percent)}%` }}
              />
            </div>
            <span className="mono w-12 text-right text-xs text-app">{metrics.mem_percent.toFixed(1)}%</span>
          </div>
          <div className="mt-1 text-[10px] text-muted">{metrics.mem_used_gb}/{metrics.mem_total_gb} GB</div>
        </div>

        {metrics.disk_usages.map((disk) => (
          <div key={disk.path}>
            <div className="mb-1 truncate text-xs text-muted">Disk <span>{disk.path.length > 20 ? '...' + disk.path.slice(-18) : disk.path}</span></div>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 rounded-full bg-black/[0.06] dark:bg-white/[0.08]">
                <div
                  className={`h-2 rounded-full transition-all ${
                    disk.percent > 90 ? 'bg-[var(--red)]' :
                    disk.percent > 75 ? 'bg-[var(--yellow)]' : 'bg-[var(--purple)]'
                  }`}
                  style={{ width: `${Math.min(100, disk.percent)}%` }}
                />
              </div>
              <span className="mono w-12 text-right text-xs text-app">{disk.percent}%</span>
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
    </div>
  )
}
