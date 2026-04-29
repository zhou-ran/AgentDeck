import type { Task, ProcessInfo, DiscoveredSession, LogResponse, Rule } from '../types'

const BASE = '/api'
const TOKEN_STORAGE_KEY = 'agentdeck.token'

export function getAuthToken(): string {
  try {
    const queryToken = new URLSearchParams(window.location.search).get('token')
    if (queryToken) {
      localStorage.setItem(TOKEN_STORAGE_KEY, queryToken)
      return queryToken
    }
    return localStorage.getItem(TOKEN_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

export function authHeaders(): HeadersInit {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function mergeHeaders(init?: RequestInit): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(init?.headers || {}),
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: mergeHeaders(init),
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
    fetch(`${BASE}/tasks/${id}`, { method: 'DELETE', headers: authHeaders() }),

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

  discover: (includeIgnored = false) =>
    fetchJson<{ count: number; sessions: DiscoveredSession[] }>(`/discover?include_ignored=${includeIgnored ? 'true' : 'false'}`),

  listPins: () => fetchJson<{ version: number; rules: Rule[] }>('/pins'),
  createPin: (body: { type: string; value: string; note?: string }) =>
    fetchJson<Rule>('/pins', { method: 'POST', body: JSON.stringify(body) }),
  deletePin: (id: string) =>
    fetch(`${BASE}/pins/${id}`, { method: 'DELETE', headers: authHeaders() }),

  listIgnored: (includeInactive = false) =>
    fetchJson<{ version: number; rules: Rule[] }>(`/ignored?include_inactive=${includeInactive ? 'true' : 'false'}`),
  createIgnored: (body: { type: string; value: string; note?: string }) =>
    fetchJson<Rule>('/ignored', { method: 'POST', body: JSON.stringify(body) }),
  deleteIgnored: (id: string) =>
    fetch(`${BASE}/ignored/${id}`, { method: 'DELETE', headers: authHeaders() }),
  restoreIgnored: (id: string) =>
    fetchJson<{ ok: boolean }>(`/ignored/${id}/restore`, { method: 'POST' }),

  pinSession: (id: string) => fetchJson<Rule>(`/sessions/${id}/pin`, { method: 'POST' }),
  unpinSession: (id: string) => fetchJson<{ ok: boolean; removed: boolean }>(`/sessions/${id}/unpin`, { method: 'POST' }),
  ignoreSession: (id: string) => fetchJson<Rule>(`/sessions/${id}/ignore`, { method: 'POST' }),
  unignoreSession: (id: string) => fetchJson<{ ok: boolean; restored: boolean }>(`/sessions/${id}/unignore`, { method: 'POST' }),
}
