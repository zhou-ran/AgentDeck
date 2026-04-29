import { useEffect, useRef } from 'react'

function redact(line: string): string {
  return line
    .replace(/\bsk-[A-Za-z0-9_-]{12,}\b/g, 'sk-...[redacted]')
    .replace(/\b(api[_-]?key\s*=\s*)[^\s]+/gi, '$1[redacted]')
    .replace(/\b(authorization\s*:\s*bearer\s+)[^\s]+/gi, '$1[redacted]')
}

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
            const safeLine = redact(line)
            const isError = /error|traceback|failed|fatal|exception/i.test(safeLine)
            const isWarning = /warn/i.test(safeLine)
            return (
              <div
                key={i}
                className={`whitespace-pre-wrap break-all ${
                  isError ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-gray-300'
                }`}
              >
                {safeLine}
              </div>
            )
          })
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
