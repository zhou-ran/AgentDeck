import type { Task, ProcessInfo, DiscoveredSession, LogResponse } from '../types'

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
    goal?: string
    feature?: string
    acceptance_criteria?: string[]
    tags?: string[]
  }) => fetchJson<Task>('/tasks', { method: 'POST', body: JSON.stringify(body) }),

  deleteTask: (id: string) =>
    fetch(`${BASE}/tasks/${id}`, { method: 'DELETE' }),

  stopTask: (id: string) => fetchJson<Task>(`/tasks/${id}/stop`, { method: 'POST' }),

  importPlan: (id: string, steps: { id: string; title: string }[]) =>
    fetchJson<Task>(`/tasks/${id}/plan`, {
      method: 'POST',
      body: JSON.stringify({ steps }),
    }),

  updateStep: (id: string, stepId: string, status: string, notes?: string) =>
    fetchJson<Task>(`/tasks/${id}/steps/${stepId}`, {
      method: 'PUT',
      body: JSON.stringify({ status, notes: notes || '' }),
    }),

  addNote: (id: string, note: string, stepId?: string) =>
    fetchJson<Task>(`/tasks/${id}/notes`, {
      method: 'POST',
      body: JSON.stringify({ note, step_id: stepId }),
    }),

  completeTask: (id: string, summary: string) =>
    fetchJson<Task>(`/tasks/${id}/complete`, {
      method: 'POST',
      body: JSON.stringify({ summary }),
    }),

  failTask: (id: string, reason: string) =>
    fetchJson<Task>(`/tasks/${id}/fail`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  updateHandoff: (id: string, notes: string) =>
    fetchJson<{ status: string }>(`/tasks/${id}/handoff`, {
      method: 'PUT',
      body: JSON.stringify({ note: notes }),
    }),

  getHandoff: (id: string) =>
    fetchJson<{ task_id: string; handoff_text: string }>(`/tasks/${id}/handoff`),

  getLog: (id: string, lines = 50) =>
    fetchJson<LogResponse>(`/tasks/${id}/logs?lines=${lines}`),

  getProcessTree: (id: string) => fetchJson<ProcessInfo>(`/tasks/${id}/process-tree`),

  discover: () => fetchJson<{ count: number; sessions: DiscoveredSession[] }>('/discover'),

  importPid: (pid: number, name: string) =>
    fetchJson<Task>('/import-pid', {
      method: 'POST',
      body: JSON.stringify({ pid, name }),
    }),
}
