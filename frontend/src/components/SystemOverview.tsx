import type { SystemMetrics } from '../types'
import { formatBytesRate } from '../utils/format'

export function SystemOverview({ metrics }: { metrics: SystemMetrics | null }) {
  if (!metrics) return null

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 mb-6">
      <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">System Overview</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        {/* CPU */}
        <div>
          <div className="text-gray-500 text-xs mb-0.5">CPU</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-800 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  metrics.cpu_percent > 80 ? 'bg-red-500' :
                  metrics.cpu_percent > 50 ? 'bg-yellow-500' : 'bg-green-500'
                }`}
                style={{ width: `${Math.min(100, metrics.cpu_percent)}%` }}
              />
            </div>
            <span className="text-gray-200 font-mono text-xs w-12 text-right">{metrics.cpu_percent.toFixed(1)}%</span>
          </div>
        </div>

        {/* Memory */}
        <div>
          <div className="text-gray-500 text-xs mb-0.5">Memory</div>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-800 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${
                  metrics.mem_percent > 85 ? 'bg-red-500' :
                  metrics.mem_percent > 60 ? 'bg-yellow-500' : 'bg-blue-500'
                }`}
                style={{ width: `${Math.min(100, metrics.mem_percent)}%` }}
              />
            </div>
            <span className="text-gray-200 font-mono text-xs w-12 text-right">{metrics.mem_percent.toFixed(1)}%</span>
          </div>
          <div className="text-gray-500 text-[10px] mt-0.5">{metrics.mem_used_gb}/{metrics.mem_total_gb} GB</div>
        </div>

        {/* Disk */}
        {metrics.disk_usages.map((disk) => (
          <div key={disk.path}>
            <div className="text-gray-500 text-xs mb-0.5">Disk <span className="text-gray-600">{disk.path.length > 20 ? '...' + disk.path.slice(-18) : disk.path}</span></div>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-800 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    disk.percent > 90 ? 'bg-red-500' :
                    disk.percent > 75 ? 'bg-yellow-500' : 'bg-purple-500'
                  }`}
                  style={{ width: `${Math.min(100, disk.percent)}%` }}
                />
              </div>
              <span className="text-gray-200 font-mono text-xs w-12 text-right">{disk.percent}%</span>
            </div>
            <div className="text-gray-500 text-[10px] mt-0.5">{disk.used_gb}/{disk.total_gb} GB</div>
          </div>
        ))}
      </div>

      {/* Network interfaces */}
      {metrics.net_interfaces.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800">
          <div className="text-gray-500 text-xs mb-2">Network</div>
          <div className="flex flex-wrap gap-4">
            {metrics.net_interfaces.map((iface) => (
              <div key={iface.name} className="text-xs">
                <span className="text-gray-400 font-mono">{iface.name}</span>
                <span className="text-green-400 ml-2">&#8593; {formatBytesRate(iface.tx_mbps)}</span>
                <span className="text-blue-400 ml-2">&#8595; {formatBytesRate(iface.rx_mbps)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
