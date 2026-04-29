import type { ProcessInfo } from '../types'

function command(proc: ProcessInfo): string {
  const text = proc.cmdline?.join(' ') || proc.name || ''
  return text.length > 180 ? `${text.slice(0, 179)}...` : text
}

function linesFor(proc: ProcessInfo, prefix = '', isLast = true, isRoot = true): string[] {
  const connector = isRoot ? '' : isLast ? '`-' : '|-'
  const label = `${proc.name || 'proc'}(${proc.pid}) ${command(proc)} [cpu=${proc.cpu_percent.toFixed(1)} mem=${proc.memory_percent.toFixed(1)} ${proc.elapsed}]`
  const lines = [`${prefix}${connector}${label}`]
  const childPrefix = isRoot ? '' : `${prefix}${isLast ? '  ' : '| '}`
  proc.children.forEach((child, index) => {
    lines.push(...linesFor(child, childPrefix, index === proc.children.length - 1, false))
  })
  return lines
}

export function ProcessTree({ tree }: { tree: ProcessInfo | null }) {
  if (!tree) {
    return <pre className="border border-gray-800 bg-gray-950 p-3 font-mono text-xs text-gray-600">no process tree available</pre>
  }
  return (
    <pre className="overflow-auto border border-gray-800 bg-gray-950 p-3 font-mono text-xs leading-relaxed text-gray-400">
      {linesFor(tree).join('\n')}
    </pre>
  )
}
