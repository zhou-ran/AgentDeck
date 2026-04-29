import { StatusDot } from './StatusDot'

export function StatCard({
  label,
  value,
  detail,
  status,
}: {
  label: string
  value: number | string
  detail?: string
  status?: string
}) {
  return (
    <div className="glass-panel-strong rounded-[18px] px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-medium text-muted">{label}</div>
        {status && <StatusDot status={status} />}
      </div>
      <div className="mt-2 text-2xl font-semibold leading-none text-app">{value}</div>
      {detail && <div className="mt-1 truncate text-xs text-muted">{detail}</div>}
    </div>
  )
}
