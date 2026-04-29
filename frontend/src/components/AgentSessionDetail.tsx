import type { DiscoveredSession } from '../types'
import { StatusBadge } from './StatusBadge'
import { ProcessTree } from './ProcessTree'

export function AgentSessionDetail({
  session,
  onBack,
}: {
  session: DiscoveredSession
  onBack: () => void
}) {
  const project = session.project_name || session.project?.display_name || session.short_cwd || 'unknown project'
  const instruction = session.user_instruction || '未找到原始指令'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={onBack} className="text-sm text-gray-400 hover:text-gray-200 mb-2">
            Back
          </button>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold">{project}</h2>
            <StatusBadge status={session.status} />
            <span className="px-2 py-0.5 bg-gray-800 rounded text-xs font-mono text-gray-300">
              {session.agent_type || 'unknown'}
            </span>
          </div>
          <div className="text-sm text-gray-500 mt-1">{session.short_cwd || session.cwd}</div>
        </div>
        <button
          onClick={() => navigator.clipboard.writeText(session.project?.project_dir || session.cwd)}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-sm"
        >
          Copy Project Path
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Overview</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Info label="Project" value={project} />
            <Info label="Workspace" value={session.project?.workspace || '-'} />
            <Info label="Root PID" value={String(session.root_pid || session.root_process.pid)} />
            <Info label="Elapsed" value={session.elapsed || '-'} />
            <Info label="CPU" value={`${session.cpu_percent.toFixed(1)}%`} />
            <Info label="MEM" value={`${session.memory_percent.toFixed(1)}%`} />
          </div>
          <div className="mt-4">
            <div className="text-xs text-gray-500 mb-1">Current Activity</div>
            <div className="text-gray-100">{session.current_activity || 'Unknown activity'}</div>
            {session.status_reason && <div className="text-xs text-gray-500 mt-1">{session.status_reason}</div>}
          </div>
          <div className="mt-4">
            <div className="text-xs text-gray-500 mb-1">Root Command</div>
            <div className="font-mono text-xs text-gray-300 break-all">{session.root_cmd || '-'}</div>
          </div>
        </section>

        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">User Instruction</h3>
          <div className={`whitespace-pre-wrap text-sm ${session.user_instruction ? 'text-gray-100' : 'text-gray-500'}`}>
            {instruction}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500">
            <div>source: <span className="text-gray-300 break-all">{session.instruction_source || '-'}</span></div>
            <div>confidence: <span className="text-gray-300">{session.instruction?.confidence?.toFixed(2) ?? '0.00'}</span></div>
          </div>
          {session.instruction_candidates?.length > 1 && (
            <details className="mt-4">
              <summary className="cursor-pointer text-xs text-gray-400">Candidate instructions</summary>
              <div className="mt-2 space-y-2">
                {session.instruction_candidates.map((item, i) => (
                  <div key={`${item.source_file}-${i}`} className="bg-gray-950 rounded p-2 text-xs">
                    <div className="text-gray-300 whitespace-pre-wrap">{item.text}</div>
                    <div className="text-gray-600 mt-1 break-all">{item.source_file}</div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>

        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Process Tree</h3>
          <ProcessTree tree={session.root_process} />
          {session.active_commands?.length > 0 && (
            <div className="mt-4">
              <div className="text-xs text-gray-500 mb-1">Active Commands</div>
              <div className="space-y-1">
                {session.active_commands.map((cmd, i) => (
                  <div key={i} className="font-mono text-xs text-gray-300 break-all">{cmd}</div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Project Status</h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <Info label="Branch" value={session.project_status?.git_branch || '-'} />
            <Info label="Dirty Files" value={String(session.project_status?.git_dirty_files_count ?? 0)} />
            <Info label="Tests Running" value={(session.project_status?.test_processes || []).length ? 'yes' : 'no'} />
            <Info label="Servers Running" value={(session.project_status?.server_processes || []).length ? 'yes' : 'no'} />
          </div>
          <FileList title="Changed Files" files={session.project_status?.git_changed_files || []} />
          <FileList title="Recent Modified Files" files={session.project_status?.recent_modified_files || []} />
          <FileList title="Error Hints" files={session.error_hints || []} tone="red" />
        </section>

        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4 lg:col-span-2">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Live Logs</h3>
          <pre className="max-h-80 overflow-auto bg-gray-950 rounded p-3 text-xs text-gray-300 whitespace-pre-wrap">
            {(session.recent_logs || []).join('\n') || 'No recent logs found'}
          </pre>
        </section>

        <section className="bg-gray-900 rounded-lg border border-gray-800 p-4 lg:col-span-2">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-3">Activity Timeline</h3>
          <div className="space-y-2">
            {(session.timeline || []).map((item, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <div className="text-gray-500 w-44 shrink-0">{new Date(item.timestamp).toLocaleString()}</div>
                <div className="text-gray-200">{item.label}</div>
                <div className="text-gray-600">{item.source}</div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-gray-200 truncate">{value}</div>
    </div>
  )
}

function FileList({ title, files, tone = 'gray' }: { title: string; files: string[]; tone?: 'gray' | 'red' }) {
  if (!files.length) return null
  const color = tone === 'red' ? 'text-red-300' : 'text-gray-300'
  return (
    <div className="mt-4">
      <div className="text-xs text-gray-500 mb-1">{title}</div>
      <div className="space-y-1">
        {files.slice(0, 10).map((file, i) => (
          <div key={i} className={`text-xs break-all ${color}`}>{file}</div>
        ))}
      </div>
    </div>
  )
}
