import type { Task, ProcessInfo, LogResponse } from '../types'

const BASE = '/api'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json()
}

export const api = {
  listTasks: () => fetchJson<Task[]>('/tasks'),

  getTask: (id: string) => fetchJson<Task>(`/tasks/${id}`),

  createTask: (body: {
    task_id: string
    name: string
    project_dir: string
    command: string
    acceptance_criteria?: string
    tags?: string[]
  }) => fetchJson<Task>('/tasks', { method: 'POST', body: JSON.stringify(body) }),

  deleteTask: (id: string) =>
    fetch(`${BASE}/tasks/${id}`, { method: 'DELETE' }),

  stopTask: (id: string) => fetchJson<Task>(`/tasks/${id}/stop`, { method: 'POST' }),

  addNote: (id: string, note: string) =>
    fetchJson<Task>(`/tasks/${id}/notes`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),

  getLog: (id: string, lines = 50) =>
    fetchJson<LogResponse>(`/tasks/${id}/logs?lines=${lines}`),

  getProcessTree: (id: string) => fetchJson<ProcessInfo>(`/tasks/${id}/process-tree`),

  discover: () => fetchJson<{ count: number; processes: ProcessInfo[] }>('/discover'),
}
