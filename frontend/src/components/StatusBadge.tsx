import type { TaskStatus } from '../types'

const CONFIG: Record<TaskStatus, { color: string; bg: string; label: string }> = {
  running:       { color: 'text-green-100',   bg: 'bg-green-600',    label: 'Running' },
  busy:          { color: 'text-cyan-100',    bg: 'bg-cyan-700',     label: 'Busy' },
  testing:       { color: 'text-purple-100',  bg: 'bg-purple-700',   label: 'Testing' },
  editing:       { color: 'text-emerald-100', bg: 'bg-emerald-700',  label: 'Editing' },
  searching:     { color: 'text-sky-100',     bg: 'bg-sky-700',      label: 'Searching' },
  git_ops:       { color: 'text-indigo-100',  bg: 'bg-indigo-700',   label: 'Git Ops' },
  running_script:{ color: 'text-teal-100',    bg: 'bg-teal-700',     label: 'Script' },
  waiting:       { color: 'text-orange-100',  bg: 'bg-orange-600',   label: 'Waiting' },
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
