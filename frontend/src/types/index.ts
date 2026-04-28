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

export interface ResourceMetrics {
  cpu_percent: number
  memory_percent: number
  rss_mb: number
  vms_mb: number
  child_count: number
  open_files: number
  read_bytes: number
  write_bytes: number
  status: string
}

export interface CpuMemSample {
  ts: number
  cpu: number
  mem: number
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

  // Resource monitoring (live, from SSE)
  resources?: ResourceMetrics | null
  cpu_mem_history?: CpuMemSample[]
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

export interface DiscoveredSession {
  session_id: string
  cwd: string
  root_process: ProcessInfo
  all_pids: number[]
  agent_type: string
}

export interface LogResponse {
  task_id: string
  lines: string[]
  size: number
  last_modified: number
}

export interface DiskUsage {
  path: string
  total_gb: number
  used_gb: number
  percent: number
}

export interface NetInterface {
  name: string
  rx_mbps: number
  tx_mbps: number
}

export interface SystemMetrics {
  cpu_percent: number
  mem_total_gb: number
  mem_used_gb: number
  mem_percent: number
  disk_usages: DiskUsage[]
  net_interfaces: NetInterface[]
}

export interface SSEData {
  tasks: Task[]
  discovered: DiscoveredSession[]
  system: SystemMetrics
}
