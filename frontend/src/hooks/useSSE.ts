import { useEffect, useRef, useState, useCallback } from 'react'
import type { Task, DiscoveredSession, SystemMetrics } from '../types'

export function useSSE() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [discovered, setDiscovered] = useState<DiscoveredSession[]>([])
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null)
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    const es = new EventSource('/api/events')
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
        } else if (Array.isArray(data)) {
          setTasks(data)
        }
      } catch {}
    })

    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      es.close()
      setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
    }
  }, [connect])

  return { tasks, discovered, systemMetrics, connected }
}
