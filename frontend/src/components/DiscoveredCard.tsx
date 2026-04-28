import { useState } from 'react'
import type { DiscoveredSession } from '../types'
import { api } from '../api/client'

export function DiscoveredCard({ session }: { session: DiscoveredSession }) {
  const [importing, setImporting] = useState(false)
  const [importName, setImportName] = useState('')
  const [error, setError] = useState('')

  const root = session.root_process
  const cmdDisplay = root.cmdline.length > 0
    ? root.cmdline.slice(0, 3).join(' ')
    : root.name

  const handleImport = async () => {
    if (!importName.trim()) return
    setImporting(true)
    setError('')
    try {
      await api.importPid(root.pid, importName.trim())
      setImportName('')
      // SSE will pick up the new task
    } catch (e: any) {
      setError(e.message || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl border-l-4 border-purple-600 p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="px-1.5 py-0.5 bg-purple-900 text-purple-300 rounded text-[10px] font-mono">
            {session.agent_type}
          </span>
          <span className="text-xs text-gray-500">{session.all_pids.length} process{session.all_pids.length > 1 ? 'es' : ''}</span>
        </div>
        <span className="text-[10px] text-gray-600 font-mono">{session.session_id}</span>
      </div>

      <div className="space-y-1 text-xs text-gray-400 mb-3">
        <div className="truncate">
          <span className="text-gray-500">cmd:</span>{' '}
          <span className="font-mono">{cmdDisplay}</span>
        </div>
        <div className="flex gap-4">
          <span>
            <span className="text-gray-500">cwd:</span>{' '}
            <span className="truncate inline-block max-w-[200px] align-bottom">{session.cwd || 'unknown'}</span>
          </span>
          <span>
            <span className="text-gray-500">pid:</span> {root.pid}
          </span>
          <span>
            <span className="text-gray-500">user:</span> {root.user || '-'}
          </span>
          <span>
            <span className="text-gray-500">elapsed:</span> {root.elapsed}
          </span>
        </div>
        {(root.cpu_percent > 0 || root.memory_percent > 0) && (
          <div className="flex gap-4">
            <span>
              <span className="text-gray-500">cpu:</span> {root.cpu_percent.toFixed(1)}%
            </span>
            <span>
              <span className="text-gray-500">mem:</span> {root.memory_percent.toFixed(1)}%
            </span>
          </div>
        )}
      </div>

      {/* Import controls */}
      <div className="border-t border-gray-800 pt-3">
        <div className="flex gap-2">
          <input
            value={importName}
            onChange={(e) => setImportName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleImport()}
            placeholder="task name..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-gray-500"
          />
          <button
            onClick={handleImport}
            disabled={importing || !importName.trim()}
            className="px-3 py-1 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded text-xs"
          >
            Import
          </button>
        </div>
        {error && <div className="text-red-400 text-[10px] mt-1">{error}</div>}
      </div>
    </div>
  )
}
