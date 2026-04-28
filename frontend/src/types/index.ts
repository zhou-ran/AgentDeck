export type TaskStatus = 'running' | 'idle' | 'waiting_input' | 'completed' | 'failed' | 'unknown'

export interface PlanStep {
  id: string
  title: string
  status: 'pending' | 'running' | 'done' | 'blocked'
  notes: string
}

export interface ProgressLogEntry {
  timestamp: string
  message: string
  step_id?: string
}

export interface Task {
  task_id: string
  name: string
  project_dir: string
  command: string
  pid: number | null
  status: TaskStatus
  started_at: string
  ended_at: string | null
  last_log_update: string | null

  // Structured task fields
  goal: string
  feature: string
  acceptance_criteria: string[]
  plan: PlanStep[]
  current_step_id: string | null
  progress_log: ProgressLogEntry[]
  handoff_notes: string
  changed_files: string[]
  risk_notes: string
  final_summary: string

  // Legacy
  exit_code: number | null
  has_error_hint: boolean
  tags: string[]
  log_size?: number
  log_mtime?: number
}

export interface ProcessInfo {
  pid: number
  ppid: number
  name: string
  cmdline: string[]
  cwd: string
  user: string
  status: string
  cpu_percent: number
  memory_percent: number
  create_time: number
  elapsed: string
  children: ProcessInfo[]
}

export interface LogResponse {
  task_id: string
  lines: string[]
  size: number
  last_modified: number
}
