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
      className="mono overflow-auto rounded-2xl border border-[var(--border)] bg-black/[0.035] text-xs leading-relaxed dark:bg-white/[0.055]"
      style={{ maxHeight: height }}
    >
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-[var(--surface-strong)] px-3 py-2 backdrop-blur-xl">
        <span className="text-[11px] font-medium text-muted">Console</span>
        <input
          type="search"
          aria-label="Filter logs"
          placeholder="Filter logs"
          className="ml-auto w-36 rounded-full border border-[var(--border)] bg-white/60 px-2.5 py-1 text-[11px] text-app outline-none placeholder:text-[var(--muted)] focus:border-[var(--blue)] dark:bg-white/10"
          readOnly
        />
      </div>
      <div className="p-3">
        {lines.length === 0 ? (
          <div className="py-8 text-center">
            <div className="text-sm font-medium text-app">No logs yet</div>
            <div className="mt-1 text-xs text-muted">Logs will appear once this task starts producing output.</div>
          </div>
        ) : (
          lines.map((line, i) => {
            const safeLine = redact(line)
            const isError = /error|traceback|failed|fatal|exception/i.test(safeLine)
            const isWarning = /warn/i.test(safeLine)
            return (
              <div
                key={i}
                className={`flex gap-2 whitespace-pre-wrap break-all rounded-md px-1.5 py-0.5 ${
                  isError ? 'bg-red-500/[0.06] text-red-700 dark:text-red-300' : isWarning ? 'bg-orange-500/[0.06] text-orange-700 dark:text-orange-300' : 'text-muted-strong'
                }`}
              >
                <span className="shrink-0 select-none text-muted">{String(i + 1).padStart(3, '0')}</span>
                <span>{safeLine}</span>
              </div>
            )
          })
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
