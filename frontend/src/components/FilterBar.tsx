import type { TaskStatus } from '../types'

interface FilterBarProps {
  statuses: TaskStatus[]
  onStatusesChange: (statuses: TaskStatus[]) => void
  search: string
  onSearchChange: (search: string) => void
  runningOnly: boolean
  onRunningOnlyChange: (v: boolean) => void
  totalCount: number
  filteredCount: number
}

const ALL_STATUSES: TaskStatus[] = [
  'running', 'busy', 'testing', 'editing', 'searching', 'git_ops',
  'running_script', 'waiting', 'idle', 'waiting_input', 'completed', 'failed', 'unknown'
]

const STATUS_COLORS: Record<TaskStatus, string> = {
  running:        'bg-green-600 text-green-100 border-green-500',
  busy:           'bg-emerald-600 text-emerald-100 border-emerald-500',
  testing:        'bg-cyan-600 text-cyan-100 border-cyan-500',
  editing:        'bg-teal-600 text-teal-100 border-teal-500',
  searching:      'bg-sky-600 text-sky-100 border-sky-500',
  git_ops:        'bg-indigo-600 text-indigo-100 border-indigo-500',
  running_script: 'bg-violet-600 text-violet-100 border-violet-500',
  waiting:        'bg-amber-600 text-amber-100 border-amber-500',
  idle:           'bg-yellow-600 text-yellow-100 border-yellow-500',
  waiting_input:  'bg-orange-600 text-orange-100 border-orange-500',
  completed:      'bg-blue-600 text-blue-100 border-blue-500',
  failed:         'bg-red-600 text-red-100 border-red-500',
  unknown:        'bg-gray-600 text-gray-100 border-gray-500',
}

const STATUS_LABELS: Record<TaskStatus, string> = {
  running: '运行中',
  busy: '忙碌',
  testing: '测试中',
  editing: '编辑中',
  searching: '搜索中',
  git_ops: 'Git操作',
  running_script: '脚本运行',
  waiting: '等待中',
  idle: '空闲',
  waiting_input: '等输入',
  completed: '已完成',
  failed: '失败',
  unknown: '未知',
}

export function FilterBar({
  statuses, onStatusesChange,
  search, onSearchChange,
  runningOnly, onRunningOnlyChange,
  totalCount, filteredCount,
}: FilterBarProps) {
  const toggleStatus = (s: TaskStatus) => {
    if (statuses.includes(s)) {
      onStatusesChange(statuses.filter(x => x !== s))
    } else {
      onStatusesChange([...statuses, s])
    }
  }

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-3 mb-4 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => onRunningOnlyChange(!runningOnly)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            runningOnly
              ? 'bg-green-600 text-white border-green-500'
              : 'bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-500'
          }`}
        >
          仅活跃
        </button>

        {ALL_STATUSES.map(s => (
          <button
            key={s}
            onClick={() => toggleStatus(s)}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium border transition-colors ${
              statuses.includes(s)
                ? STATUS_COLORS[s]
                : 'bg-gray-800 text-gray-500 border-gray-700 hover:border-gray-500'
            }`}
          >
            {STATUS_LABELS[s]}
          </button>
        ))}

        <span className="text-xs text-gray-500 ml-auto">
          {filteredCount}/{totalCount}
        </span>
      </div>

      <input
        type="text"
        value={search}
        onChange={e => onSearchChange(e.target.value)}
        placeholder="搜索名称、命令、目录或任务ID..."
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-gray-500"
      />
    </div>
  )
}
