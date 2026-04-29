import { useState } from 'react'
import type { DiscoveredSession } from '../types'
import { api } from '../api/client'

const AGENT_TYPE_LABELS: Record<string, string> = {
  codex: 'Codex 班组',
  claude: 'Claude 班组',
  'claude-code': 'Claude 班组',
  kimi: 'Kimi 班组',
  'kimi-code': 'Kimi 班组',
  aider: 'Aider 班组',
  gemini: 'Gemini 班组',
  node: 'Node 班组',
  python: 'Python 班组',
  python3: 'Python 班组',
}

const STATUS_LANE_LABELS: Record<string, string> = {
  busy: '忙碌',
  testing: '测试中',
  editing: '编辑中',
  searching: '搜索中',
  git_ops: 'Git操作',
  running_script: '脚本运行',
  running: '运行中',
  idle: '空闲',
  waiting: '等待中',
  waiting_input: '等回话',
  unknown: '未知',
}

function fmtHeartbeat(ageSec: number | null): string {
  if (ageSec === null || ageSec === undefined) return '无心跳'
  if (ageSec < 60) return `${Math.floor(ageSec)}s 前`
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m 前`
  return `${Math.floor(ageSec / 3600)}h 前`
}

export function DiscoveredCard({ session }: { session: DiscoveredSession }) {
  const [importing, setImporting] = useState(false)
  const [importName, setImportName] = useState('')
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)

  const root = session.root_process
  const typeLabel = AGENT_TYPE_LABELS[session.agent_type] || session.agent_type
  const statusLabel = STATUS_LANE_LABELS[session.status] || session.status
  const projectName = session.project_name?.name || session.project || 'unknown'
  const shortCwd = session.project_name?.short_cwd || session.cwd

  const handleImport = async () => {
    if (!importName.trim()) return
    setImporting(true)
    setError('')
    try {
      await api.importPid(root.pid, importName.trim())
      setImportName('')
    } catch (e: any) {
      setError(e.message || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  // Status color for left border
  const borderColor = {
    busy: 'border-emerald-500',
    testing: 'border-cyan-500',
    editing: 'border-teal-500',
    searching: 'border-sky-500',
    git_ops: 'border-indigo-500',
    running_script: 'border-violet-500',
    running: 'border-green-500',
    idle: 'border-yellow-500',
    waiting: 'border-amber-500',
    waiting_input: 'border-orange-500',
    unknown: 'border-gray-500',
  }[session.status] || 'border-gray-500'

  return (
    <div className={`bg-gray-900 rounded-xl border-l-4 ${borderColor} p-4`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="px-1.5 py-0.5 bg-purple-900 text-purple-300 rounded text-[10px] font-mono">
            {typeLabel}
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
            session.status === 'waiting_input' ? 'bg-orange-900 text-orange-300' :
            session.status === 'idle' ? 'bg-yellow-900 text-yellow-300' :
            'bg-green-900 text-green-300'
          }`}>
            {statusLabel}
          </span>
          <span className="text-xs text-gray-500">{session.all_pids.length} 进程</span>
        </div>
        <span className="text-[10px] text-gray-600 font-mono">{session.session_id}</span>
      </div>

      {/* Project name + cwd */}
      <div className="mb-2">
        <div className="text-sm font-semibold text-gray-200">{projectName}</div>
        <div className="text-[11px] text-gray-500 font-mono truncate">{shortCwd}</div>
      </div>

      {/* Heartbeat + Activity */}
      <div className="space-y-1 text-xs text-gray-400 mb-3">
        <div className="flex gap-4">
          <span>
            <span className="text-gray-500">心跳:</span>{' '}
            <span className={session.heartbeat_age_sec !== null && session.heartbeat_age_sec < 120 ? 'text-green-400' : 'text-gray-400'}>
              {fmtHeartbeat(session.heartbeat_age_sec)}
            </span>
          </span>
          {session.project_name?.git_branch && (
            <span>
              <span className="text-gray-500">分支:</span>{' '}
              <span className="text-gray-300">{session.project_name.git_branch}</span>
            </span>
          )}
        </div>

        {session.current_activity && (
          <div>
            <span className="text-gray-500">当前活动:</span>{' '}
            <span className="text-gray-300">{session.current_activity}</span>
          </div>
        )}

        {/* Recent output preview */}
        {session.recent_output && (
          <div>
            <span className="text-gray-500">最近动静:</span>
            <pre className="mt-1 bg-gray-800 rounded p-2 text-[10px] text-gray-300 overflow-hidden max-h-16 whitespace-pre-wrap break-all">
              {session.recent_output.slice(0, 200)}
            </pre>
          </div>
        )}

        {/* Pending items */}
        {session.pending_items && session.pending_items.length > 0 && (
          <div>
            <span className="text-gray-500">还没干完:</span>
            <ul className="mt-1 space-y-0.5">
              {session.pending_items.slice(0, 4).map((item, i) => (
                <li key={i} className="text-[10px] text-gray-400 pl-2 before:content-['·'] before:mr-1 before:text-gray-600">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* User instruction */}
        {session.user_instruction && (
          <div>
            <span className="text-gray-500">用户指令:</span>{' '}
            <span className="text-gray-300 italic">"{session.user_instruction.slice(0, 120)}"</span>
          </div>
        )}

        {/* Metrics grid */}
        <div className="flex gap-4 flex-wrap">
          {session.project_status?.dirty_files && session.project_status.dirty_files.length > 0 && (
            <span>
              <span className="text-gray-500">脏文件:</span>{' '}
              <span className="text-orange-400">{session.project_status.dirty_files.length}</span>
            </span>
          )}
          {session.git_status && (
            <span>
              <span className="text-gray-500">Git:</span>{' '}
              <span className={session.git_status === 'dirty' ? 'text-orange-400' : 'text-green-400'}>{session.git_status}</span>
            </span>
          )}
          {session.child_processes && session.child_processes.length > 0 && (
            <span>
              <span className="text-gray-500">子进程:</span> {session.child_processes.length}
            </span>
          )}
          {(session.cpu_percent > 0 || session.memory_percent > 0) && (
            <>
              <span><span className="text-gray-500">CPU:</span> {session.cpu_percent.toFixed(1)}%</span>
              <span><span className="text-gray-500">MEM:</span> {session.memory_percent.toFixed(1)}%</span>
            </>
          )}
        </div>

        {/* Error hints */}
        {session.error_hints && session.error_hints.length > 0 && (
          <div className="mt-1">
            {session.error_hints.map((hint, i) => (
              <span key={i} className="inline-block mr-1 px-1.5 py-0.5 bg-red-900 text-red-300 rounded text-[10px]">
                {hint}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Expand/Collapse details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[10px] text-gray-500 hover:text-gray-300 mb-2"
      >
        {expanded ? '收起详情' : '查看详情'}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 pt-2 mb-2 space-y-1 text-[10px] text-gray-500">
          <div>cmd: <span className="font-mono text-gray-400">{root.cmdline.slice(0, 3).join(' ')}</span></div>
          <div>pid: {root.pid} | user: {root.user || '-'} | elapsed: {root.elapsed}</div>
          {session.active_commands && session.active_commands.length > 0 && (
            <div>活跃命令: {session.active_commands.slice(0, 3).join(' | ')}</div>
          )}
          {session.project_status?.last_commit_msg && (
            <div>最近提交: {session.project_status.last_commit_msg}</div>
          )}
        </div>
      )}

      {/* Import controls */}
      <div className="border-t border-gray-800 pt-3">
        <div className="flex gap-2">
          <input
            value={importName}
            onChange={(e) => setImportName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleImport()}
            placeholder="任务名称..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-gray-500"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importName.trim()}
            className="px-3 py-1 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded text-xs"
          >
            导入
          </button>
          <button
            onClick={() => navigator.clipboard.writeText(session.cwd)}
            className="px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-[10px] text-gray-400"
            title="复制路径"
          >
            复制路径
          </button>
        </div>
        {error && <div className="text-red-400 text-[10px] mt-1">{error}</div>}
      </div>
    </div>
  )
}
