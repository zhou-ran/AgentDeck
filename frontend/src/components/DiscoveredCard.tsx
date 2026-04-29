import type { DiscoveredSession } from '../types'
import { StatusBadge } from './StatusBadge'

export function DiscoveredCard({ session, onClick }: { session: DiscoveredSession; onClick: () => void }) {
  const project = session.project_name || session.project?.display_name || session.short_cwd || 'unknown project'
  const instruction = session.user_instruction || '未找到原始指令'
  const branch = session.project_status?.git_branch || '-'
  const dirtyCount = session.project_status?.git_dirty_files_count ?? 0
  const changed = session.project_status?.git_changed_files || []
  const recent = session.project_status?.recent_modified_files || []
  const hasTests = (session.project_status?.test_processes || []).length > 0
  const hasErrors = (session.error_hints || []).length > 0

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusBadge status={session.status} />
            <span className="px-1.5 py-0.5 bg-gray-800 text-gray-300 rounded text-[10px] font-mono">
              {session.agent_type || 'unknown'}
            </span>
            {session.project?.workspace && (
              <span className="px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded text-[10px]">
                {session.project.workspace}
              </span>
            )}
          </div>
          <h3 className="font-semibold text-gray-100 truncate">{project}</h3>
          <div className="text-xs text-gray-500 truncate">{session.short_cwd || session.cwd}</div>
        </div>
        <div className="text-right text-xs text-gray-500 shrink-0">
          <div>{session.elapsed}</div>
          <div>PID {session.root_pid || session.root_process.pid}</div>
        </div>
      </div>

      <div className="space-y-2 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">Current Activity</div>
          <div className="text-gray-100 line-clamp-2">{session.current_activity || 'Unknown activity'}</div>
          {session.status_reason && <div className="text-xs text-gray-500 truncate">{session.status_reason}</div>}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">User Instruction</div>
          <div className={`line-clamp-2 ${session.user_instruction ? 'text-gray-300' : 'text-gray-500'}`}>{instruction}</div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
          <div className="truncate">branch: <span className="text-gray-300">{branch}</span></div>
          <div>dirty: <span className={dirtyCount ? 'text-yellow-300' : 'text-gray-300'}>{dirtyCount}</span></div>
          <div>tests: <span className={hasTests ? 'text-purple-300' : 'text-gray-300'}>{hasTests ? 'yes' : 'no'}</span></div>
          <div>errors: <span className={hasErrors ? 'text-red-300' : 'text-gray-300'}>{hasErrors ? 'yes' : 'no'}</span></div>
          <div>children: <span className="text-gray-300">{session.child_processes?.length ?? 0}</span></div>
          <div>cpu/mem: <span className="text-gray-300">{session.cpu_percent.toFixed(1)}% / {session.memory_percent.toFixed(1)}%</span></div>
        </div>
        {(changed.length > 0 || recent.length > 0) && (
          <div className="text-xs text-gray-500 truncate">
            files: <span className="text-gray-400">{(changed.length ? changed : recent).slice(0, 3).join(', ')}</span>
          </div>
        )}
      </div>

      <div className="flex gap-2 mt-4 pt-3 border-t border-gray-800">
        <button onClick={onClick} className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-100">
          View Details
        </button>
        <button
          onClick={() => navigator.clipboard.writeText(session.project?.project_dir || session.cwd)}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-300"
        >
          Copy Path
        </button>
      </div>
    </div>
  )
}
