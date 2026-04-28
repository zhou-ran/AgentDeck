import { useEffect, useRef } from 'react'

export function LogViewer({ lines, height = '300px' }: { lines: string[]; height?: string }) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  return (
    <div
      className="bg-gray-900 rounded-lg border border-gray-700 overflow-auto font-mono text-xs leading-relaxed"
      style={{ maxHeight: height }}
    >
      <div className="p-3">
        {lines.length === 0 ? (
          <span className="text-gray-500">No log output</span>
        ) : (
          lines.map((line, i) => {
            const isError = /error|traceback|failed|fatal|exception/i.test(line)
            const isWarning = /warn/i.test(line)
            return (
              <div
                key={i}
                className={`whitespace-pre-wrap break-all ${
                  isError ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-gray-300'
                }`}
              >
                {line}
              </div>
            )
          })
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
