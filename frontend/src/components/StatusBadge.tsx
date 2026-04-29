import type { TaskStatus } from '../types'

const CONFIG: Record<TaskStatus, { color: string; bg: string; label: string }> = {
  running:        { color: 'text-green-100',   bg: 'bg-green-600',    label: '运行中' },
  busy:           { color: 'text-emerald-100', bg: 'bg-emerald-600',  label: '忙碌' },
  testing:        { color: 'text-cyan-100',    bg: 'bg-cyan-600',     label: '测试中' },
  editing:        { color: 'text-teal-100',    bg: 'bg-teal-600',     label: '编辑中' },
  searching:      { color: 'text-sky-100',     bg: 'bg-sky-600',      label: '搜索中' },
  git_ops:        { color: 'text-indigo-100',  bg: 'bg-indigo-600',   label: 'Git操作' },
  running_script: { color: 'text-violet-100',  bg: 'bg-violet-600',   label: '脚本运行' },
  waiting:        { color: 'text-amber-100',   bg: 'bg-amber-600',    label: '等待中' },
  idle:           { color: 'text-yellow-100',  bg: 'bg-yellow-600',   label: '空闲' },
  waiting_input:  { color: 'text-orange-100',  bg: 'bg-orange-600',   label: '等输入' },
  completed:      { color: 'text-blue-100',    bg: 'bg-blue-600',     label: '已完成' },
  failed:         { color: 'text-red-100',     bg: 'bg-red-600',      label: '失败' },
  unknown:        { color: 'text-gray-100',    bg: 'bg-gray-600',     label: '未知' },
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

// Lane grouping for dashboard
export const LANE_GROUPS = [
  { key: 'working',    label: '开工', statuses: ['busy', 'testing', 'editing', 'searching', 'git_ops', 'running_script', 'running'] },
  { key: 'slacking',   label: '摸鱼', statuses: ['idle', 'waiting', 'unknown'] },
  { key: 'needs-input', label: '等回话', statuses: ['waiting_input'] },
] as const

export function getLaneForStatus(status: string): string {
  for (const lane of LANE_GROUPS) {
    if ((lane.statuses as readonly string[]).includes(status)) {
      return lane.key
    }
  }
  return 'slacking' // default
}
