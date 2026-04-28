export type TaskStatus = 'running' | 'idle' | 'waiting_input' | 'completed' | 'failed' | 'unknown'

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
  acceptance_criteria: string
  current_step: string
  progress_notes: string[]
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
