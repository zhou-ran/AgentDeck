/**
 * Format byte count to human-readable string.
 */
export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  if (bytes >= 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024)
    return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

/**
 * Format elapsed time between two ISO date strings.
 */
export function elapsed(started: string, ended: string | null): string {
  const start = new Date(started).getTime()
  const end = ended ? new Date(ended).getTime() : Date.now()
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m${secs % 60}s`
  return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}m`
}

/**
 * Format bytes as transfer rate (MB/s or KB/s).
 */
export function formatBytesRate(mbps: number): string {
  if (mbps >= 1) return `${mbps.toFixed(1)} MB/s`
  return `${(mbps * 1024).toFixed(0)} KB/s`
}
