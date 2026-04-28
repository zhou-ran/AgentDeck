import type { ProcessInfo } from '../types'

function TreeNode({ proc, depth = 0 }: { proc: ProcessInfo; depth?: number }) {
  return (
    <div>
      <div
        className="flex items-center gap-2 py-0.5 hover:bg-gray-800 rounded px-2"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        <span className="text-gray-500 text-xs w-16">{depth > 0 ? '├─' : ''}PID {proc.pid}</span>
        <span className="text-cyan-400 font-medium text-sm">{proc.name}</span>
        <span className="text-gray-400 text-xs truncate flex-1">{proc.cmdline.join(' ')}</span>
        <span className="text-gray-500 text-xs">{proc.cpu_percent.toFixed(1)}% cpu</span>
        <span className="text-gray-500 text-xs">{proc.memory_percent.toFixed(1)}% mem</span>
        <span className="text-gray-500 text-xs">{proc.elapsed}</span>
      </div>
      {proc.children.map((child) => (
        <TreeNode key={child.pid} proc={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export function ProcessTree({ tree }: { tree: ProcessInfo | null }) {
  if (!tree) {
    return <div className="text-gray-500 text-sm p-4">No process tree available</div>
  }
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-2 overflow-auto text-sm">
      <TreeNode proc={tree} />
    </div>
  )
}
