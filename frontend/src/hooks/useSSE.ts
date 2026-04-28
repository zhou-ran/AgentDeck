import { useEffect, useRef, useState, useCallback } from 'react'
import type { Task } from '../types'

export function useSSE() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    const es = new EventSource('/api/events')
    esRef.current = es

    es.addEventListener('update', (e) => {
      try {
        const data = JSON.parse(e.data)
        setTasks(data)
      } catch {}
    })

    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      es.close()
      // Reconnect after 3s
      setTimeout(connect, 3000)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
    }
  }, [connect])

  return { tasks, connected }
}
