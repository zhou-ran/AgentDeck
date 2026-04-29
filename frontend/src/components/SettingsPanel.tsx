import type { Rule, ScanMeta } from '../types'

export function SettingsPanel({
  scanMeta,
  ignoredRules,
  onRestoreIgnored,
}: {
  scanMeta: ScanMeta | null
  ignoredRules: Rule[]
  onRestoreIgnored: (rule: Rule) => void
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <div className="glass-panel-strong rounded-[20px] p-4">
        <div className="text-sm font-semibold text-app">Settings</div>
        <div className="mt-3 space-y-1 text-sm text-muted">
          {['General', 'Security', 'LAN Access', 'Paths', 'Appearance'].map((item, index) => (
            <div
              key={item}
              className={`rounded-xl px-3 py-2 ${index === 1 ? 'bg-blue-500/10 text-app' : ''}`}
            >
              {item}
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <section className="glass-panel-strong rounded-[20px] p-5">
          <div className="text-sm font-semibold text-app">Security</div>
          <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
            <SettingRow label="Default bind" value="127.0.0.1" />
            <SettingRow label="LAN access" value="Requires --host 0.0.0.0 and Bearer token" />
            <SettingRow label="Process env" value="Never reads /proc/<pid>/environ" />
            <SettingRow label="Shell actions" value="No browser command execution or kill endpoint" />
            <SettingRow label="Git access" value="Read-only whitelist with timeout" />
            <SettingRow label="Rate limit" value="120 requests / minute / IP" />
          </div>
        </section>

        <section className="glass-panel-strong rounded-[20px] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-app">Discovery</div>
              <div className="mt-1 text-xs text-muted">Scanner state from the live SSE stream.</div>
            </div>
            <div className="rounded-full bg-black/5 px-3 py-1 text-xs text-muted dark:bg-white/10">
              {scanMeta?.hostname || 'unknown host'}
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <SettingRow label="Scan interval" value={`${scanMeta?.scan_interval ?? 2}s`} />
            <SettingRow label="Discovery TTL" value={`${scanMeta?.discovery_ttl ?? '-'}s`} />
            <SettingRow label="Active sessions" value={String(scanMeta?.active_sessions_count ?? 0)} />
          </div>
        </section>

        <section className="glass-panel-strong rounded-[20px] p-5">
          <div className="text-sm font-semibold text-app">Ignored Rules</div>
          <div className="mt-1 text-xs text-muted">Hide-only rules. Restoring a rule does not touch processes, logs, or project files.</div>
          <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--border)]">
            {ignoredRules.length === 0 ? (
              <div className="px-4 py-6 text-sm text-muted">No ignored rules.</div>
            ) : (
              <div className="divide-y divide-[var(--border)]">
                {ignoredRules.map(rule => (
                  <div key={rule.id} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[120px_1fr_100px]">
                    <div className="text-muted">{rule.type}</div>
                    <div className="min-w-0 break-all mono text-xs text-app">{rule.value}</div>
                    <div className="text-right">
                      {rule.active ? (
                        <button
                          type="button"
                          onClick={() => onRestoreIgnored(rule)}
                          className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-app transition hover:bg-black/5 dark:hover:bg-white/10"
                        >
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
          </div>
        </section>
      </div>
    </div>
  )
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="quiet-panel rounded-2xl p-3">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className="mt-1 text-sm text-app">{value}</div>
    </div>
  )
}
