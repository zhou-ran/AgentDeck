import { useEffect, useRef, useState, useCallback } from 'react'
import type { Task, DiscoveredSession, ScanMeta, SystemMetrics } from '../types'
import { getAuthToken } from '../api/client'

export function useSSE() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [discovered, setDiscovered] = useState<DiscoveredSession[]>([])
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null)
  const [scanMeta, setScanMeta] = useState<ScanMeta | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const esRef = useRef<EventSource | null>(null)
  const retryRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    const token = getAuthToken()
    const eventUrl = token ? `/api/events?token=${encodeURIComponent(token)}` : '/api/events'
    const es = new EventSource(eventUrl)
    esRef.current = es

    es.addEventListener('update', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.tasks && Array.isArray(data.tasks)) {
          setTasks(data.tasks)
          setDiscovered(data.discovered || [])
          if (data.system) {
            setSystemMetrics(data.system)
          }
          if (data.scan) {
            setScanMeta(data.scan)
          }
        } else if (Array.isArray(data)) {
          setTasks(data)
        }
      } catch (err) {
        console.warn('Failed to parse SSE update', err)
      }
    })

    es.onopen = () => {
      setConnected(true)
      setError('')
    }
    es.onerror = () => {
      setConnected(false)
      setError(token ? 'Connection lost or token rejected.' : 'Connection lost. Add ?token=... when accessing over LAN.')
      es.close()
      retryRef.current = window.setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (retryRef.current !== null) {
        window.clearTimeout(retryRef.current)
      }
      esRef.current?.close()
    }
  }, [connect])

  return { tasks, discovered, systemMetrics, scanMeta, connected, error }
}
