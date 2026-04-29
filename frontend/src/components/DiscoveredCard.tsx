import { useState } from 'react'
import type { DiscoveredSession, ProcessInfo } from '../types'
import { ProcessTree } from './ProcessTree'

const AGENT_TYPE_LABELS: Record<string, string> = {
  codex: 'Codex',
  claude: 'Claude',
  'claude-code': 'Claude Code',
  kimi: 'Kimi',
  'kimi-code': 'Kimi Code',
  aider: 'Aider',
  gemini: 'Gemini',
}

const STATUS_LABELS: Record<string, string> = {
  needs_input: '等输入',
  busy: '忙碌',
  testing: '测试中',
  editing: '编辑中',
  searching: '搜索中',
  git_ops: 'Git 操作',
  running_script: '脚本运行',
  idle: '空闲',
  stale: '失联',
  error_hint: '有错误',
  unknown: '未知',
  waiting_input: '等输入',
}

const STATUS_STYLE: Record<string, { border: string; badge: string }> = {
  needs_input: { border: 'border-orange-500', badge: 'bg-orange-900 text-orange-300' },
  busy: { border: 'border-emerald-500', badge: 'bg-emerald-900 text-emerald-300' },
  testing: { border: 'border-cyan-500', badge: 'bg-cyan-900 text-cyan-300' },
  editing: { border: 'border-teal-500', badge: 'bg-teal-900 text-teal-300' },
  searching: { border: 'border-sky-500', badge: 'bg-sky-900 text-sky-300' },
  git_ops: { border: 'border-indigo-500', badge: 'bg-indigo-900 text-indigo-300' },
  running_script: { border: 'border-violet-500', badge: 'bg-violet-900 text-violet-300' },
  idle: { border: 'border-yellow-500', badge: 'bg-yellow-900 text-yellow-300' },
  stale: { border: 'border-gray-500', badge: 'bg-gray-800 text-gray-300' },
  error_hint: { border: 'border-red-500', badge: 'bg-red-900 text-red-300' },
  unknown: { border: 'border-gray-500', badge: 'bg-gray-800 text-gray-300' },
  waiting_input: { border: 'border-orange-500', badge: 'bg-orange-900 text-orange-300' },
}

function fmtHeartbeat(ageSec: number | null): string {
  if (ageSec === null || ageSec === undefined) return '无心跳'
  if (ageSec < 60) return `${Math.floor(ageSec)}s 前`
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m 前`
  return `${Math.floor(ageSec / 3600)}h 前`
}

function commandOf(proc: ProcessInfo): string {
  return proc.cmdline?.join(' ') || proc.name || '-'
}

function DetailRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <span className="text-gray-600">{label}: </span>
      <span className="font-mono text-gray-400 break-all">{value || '-'}</span>
    </div>
  )
}

export function DiscoveredCard({ session }: { session: DiscoveredSession }) {
  const [expanded, setExpanded] = useState(false)

  const root = session.root_process
  const typeLabel = AGENT_TYPE_LABELS[session.agent_type] || session.agent_type || 'unknown'
  const statusLabel = STATUS_LABELS[session.status] || session.status
  const statusStyle = STATUS_STYLE[session.status] || STATUS_STYLE.unknown
  const projectName = session.project_name?.name || session.project || 'unknown'
  const shortCwd = session.project_name?.short_cwd || session.cwd
  const instruction = session.user_instruction || '未找到原始指令'
  const confidence = session.confidence ?? session.instruction?.confidence ?? 0
  const sourceFile = session.source_file || session.instruction?.source_file || ''

  return (
    <div className={`bg-gray-900 rounded-lg border-l-4 ${statusStyle.border} p-4`}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-gray-100 truncate">{projectName}</div>
          <div className="text-[11px] text-gray-500 font-mono truncate">{shortCwd}</div>
        </div>
        <div className="flex gap-1.5 shrink-0">
          <span className="px-1.5 py-0.5 bg-purple-900 text-purple-300 rounded text-[10px] font-mono">
            {typeLabel}
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${statusStyle.badge}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      <div className="space-y-2 text-xs text-gray-400">
        <div className="flex gap-4 flex-wrap">
          <span>
            <span className="text-gray-500">心跳:</span>{' '}
            <span className={session.heartbeat_age_sec !== null && session.heartbeat_age_sec < 120 ? 'text-green-400' : 'text-gray-400'}>
              {fmtHeartbeat(session.heartbeat_age_sec)}
            </span>
          </span>
          {session.project_name?.git_branch && (
            <span><span className="text-gray-500">分支:</span> {session.project_name.git_branch}</span>
          )}
          <span><span className="text-gray-500">PID:</span> {root.pid}</span>
          <span><span className="text-gray-500">CPU:</span> {session.cpu_percent.toFixed(1)}%</span>
          <span><span className="text-gray-500">MEM:</span> {session.memory_percent.toFixed(1)}%</span>
        </div>

        <div>
          <span className="text-gray-500">当前活动:</span>{' '}
          <span className="text-gray-300">{session.current_activity || session.status_reason || '-'}</span>
        </div>

        <div>
          <span className="text-gray-500">用户指令:</span>{' '}
          <span className={confidence > 0 ? 'text-gray-300' : 'text-gray-500'}>
            {instruction.slice(0, 160)}
          </span>
          <span className="ml-2 text-[10px] text-gray-600">confidence {confidence.toFixed(1)}</span>
        </div>

        {session.recent_output && (
          <div>
            <span className="text-gray-500">最近输出:</span>
            <pre className="mt-1 bg-gray-800 rounded p-2 text-[10px] text-gray-300 overflow-hidden max-h-16 whitespace-pre-wrap break-all">
              {session.recent_output.slice(0, 240)}
            </pre>
          </div>
        )}

        {session.pending_items?.length > 0 && (
          <div>
            <span className="text-gray-500">待办:</span>
            <ul className="mt-1 space-y-0.5">
              {session.pending_items.slice(0, 4).map((item, i) => (
                <li key={i} className="text-[10px] text-gray-400 pl-2 before:content-['·'] before:mr-1 before:text-gray-600">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-4 flex-wrap">
          <span><span className="text-gray-500">Git:</span> {session.git_status || '-'}</span>
          <span><span className="text-gray-500">脏文件:</span> {session.project_status?.dirty_files?.length ?? 0}</span>
          <span><span className="text-gray-500">最近文件:</span> {session.recent_files?.length ?? 0}</span>
          <span><span className="text-gray-500">进程:</span> {session.all_pids.length}</span>
        </div>

        {session.error_hints?.length > 0 && (
          <div>
            {session.error_hints.map((hint, i) => (
              <span key={i} className="inline-block mr-1 px-1.5 py-0.5 bg-red-900 text-red-300 rounded text-[10px]">
                {hint}
              </span>
            ))}
          </div>
        )}
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[10px] text-gray-500 hover:text-gray-300 mt-3"
      >
        {expanded ? '收起详情' : '查看详情'}
      </button>

      {expanded && (
        <div className="border-t border-gray-800 pt-3 mt-3 space-y-3 text-[10px] text-gray-500">
          <div className="grid gap-1">
            <DetailRow label="cwd" value={session.cwd} />
            <DetailRow label="command" value={commandOf(root)} />
            <DetailRow label="pid/ppid/user" value={`${root.pid}/${root.ppid}/${root.user || '-'}`} />
            <DetailRow label="elapsed" value={root.elapsed} />
            <DetailRow label="session file" value={sourceFile} />
            <DetailRow label="source" value={session.instruction?.source || '-'} />
          </div>

          {session.project_status?.dirty_files?.length > 0 && (
            <div>
              <div className="text-gray-500 mb-1">Git dirty files</div>
              <div className="font-mono text-gray-400 space-y-0.5">
                {session.project_status.dirty_files.slice(0, 8).map(file => <div key={file}>{file}</div>)}
              </div>
            </div>
          )}

          {session.recent_files?.length > 0 && (
            <div>
              <div className="text-gray-500 mb-1">Recent files</div>
              <div className="font-mono text-gray-400 space-y-0.5">
                {session.recent_files.slice(0, 8).map(file => <div key={file}>{file}</div>)}
              </div>
            </div>
          )}

          {session.active_commands?.length > 0 && (
            <div>
              <div className="text-gray-500 mb-1">Active commands</div>
              <div className="font-mono text-gray-400 space-y-0.5">
                {session.active_commands.map(cmd => <div key={cmd}>{cmd}</div>)}
              </div>
            </div>
          )}

          <div>
            <div className="text-gray-500 mb-1">Process tree</div>
            <ProcessTree tree={root} />
          </div>

          {session.recent_logs?.length > 0 && (
            <div>
              <div className="text-gray-500 mb-1">Logs tail</div>
              <pre className="bg-gray-800 rounded p-2 text-[10px] text-gray-300 max-h-32 overflow-auto whitespace-pre-wrap break-all">
                {session.recent_logs.join('\n')}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
