import type { TaskStatus } from '../types'

const CONFIG: Record<TaskStatus, { color: string; bg: string; label: string }> = {
  running:       { color: 'text-green-100',   bg: 'bg-green-600',    label: 'Running' },
  idle:          { color: 'text-yellow-100',  bg: 'bg-yellow-600',   label: 'Idle' },
  waiting_input: { color: 'text-orange-100',  bg: 'bg-orange-600',   label: 'Waiting Input' },
  completed:     { color: 'text-blue-100',    bg: 'bg-blue-600',     label: 'Completed' },
  failed:        { color: 'text-red-100',     bg: 'bg-red-600',      label: 'Failed' },
  unknown:       { color: 'text-gray-100',    bg: 'bg-gray-600',     label: 'Unknown' },
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  const cfg = CONFIG[status] || CONFIG.unknown
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {cfg.label}
    </span>
  )
}
