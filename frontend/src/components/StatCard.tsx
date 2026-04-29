import { StatusDot } from './StatusDot'

export function StatCard({
  label,
  value,
  detail,
  status,
  compact = false,
}: {
  label: string
  value: number | string
  detail?: string
  status?: string
  compact?: boolean
}) {
  return (
    <div className={compact ? 'rounded-2xl border border-[var(--border)] bg-white/50 px-2.5 py-2 shadow-sm backdrop-blur-xl' : 'glass-panel-strong rounded-[18px] px-4 py-3'}>
      <div className="flex items-center justify-between gap-3">
        <div className={compact ? 'truncate text-[11px] font-medium text-muted' : 'text-xs font-medium text-muted'}>{label}</div>
        {status && <StatusDot status={status} />}
      </div>
      <div className={compact ? 'mt-1 text-lg font-semibold leading-none text-app' : 'mt-2 text-2xl font-semibold leading-none text-app'}>{value}</div>
      {detail && <div className="mt-1 truncate text-[11px] text-muted">{detail}</div>}
    </div>
  )
}
