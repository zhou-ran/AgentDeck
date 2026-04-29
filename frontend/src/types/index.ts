export type TaskStatus =
  | 'running'
  | 'busy'
  | 'needs_input'
  | 'testing'
  | 'editing'
  | 'searching'
  | 'git_ops'
  | 'running_script'
  | 'waiting'
  | 'idle'
  | 'stale'
  | 'error_hint'
  | 'waiting_input'
  | 'completed'
  | 'failed'
  | 'unknown'

export type SessionStatus =
  | 'needs_input'
  | 'testing'
  | 'editing'
  | 'searching'
  | 'git_ops'
  | 'running_script'
  | 'busy'
  | 'idle'
  | 'stale'
  | 'error_hint'
  | 'unknown'

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

export interface ProjectNameInfo {
  name: string
  short_cwd: string
  git_root: string | null
  git_branch: string | null
}

export interface InstructionInfo {
  text: string
  source: string
  source_file: string
  confidence: number
}

export interface ProjectRuntimeStatus {
  dirty_files: string[]
  has_uncommitted: boolean
  has_untracked: boolean
  test_status: string
  branch: string
  recent_files: string[]
}

export interface AgentDetectionResult {
  agent_type: string
  confidence: number
  reason: string
  evidence: string[]
}

export interface ForegroundAgentInfo {
  pid: number | null
  cmd: string
  tty: string | null
  is_interactive: boolean
  waiting_input: boolean
  alive: boolean
  last_activity_ts: number | null
  last_tool: string
  last_message_summary: string
  status: string
}

export interface BackgroundJob {
  pid: number
  ppid: number
  cmd: string
  job_type: string
  status: string
  elapsed_sec: number | null
  cpu: number
  mem: number
  cwd: string
  summary: string
  is_long_running: boolean
  detected_from: string
}

export interface GitStatusDetail {
  branch: string
  dirty_count: number
  changed_files: string[]
  staged_count: number
  unstaged_count: number
  untracked_count: number
  is_repo: boolean
  command_failed: boolean
}

export interface ResourceUsage {
  cpu_percent: number
  memory_percent: number
  rss_mb: number
  children_count: number
}

export interface Rule {
  id: string
  type: string
  value: string
  created_at: string
  note: string
  active: boolean
}

export interface ActivityTimelineItem {
  ts: number
  event: string
  detail: string
}

export interface ConversationMessage {
  role: string
  text: string
  ts: number | null
  source: string
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

  // Enriched fields
  status_reason: string
  current_activity: string
  agent_type: string
  project_name: string
  short_cwd: string
  user_instruction: string
  instruction_source: string

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
  tty?: string | null
  status: string
  cpu_percent: number
  memory_percent: number
  create_time: number
  elapsed: string
  children: ProcessInfo[]
}

export interface DiscoveredSession {
  session_id: string
  project_key: string
  cwd: string
  root_process: ProcessInfo
  all_pids: number[]
  agent_type: string
  agent_confidence: number
  agent_detection_reason: string
  agent_detection_evidence: string[]
  root_pid: number | null
  root_cmd: string
  user: string
  tty: string | null
  is_interactive: boolean
  started_at: string | null
  elapsed_sec: number | null

  // Enriched fields
  project_name: ProjectNameInfo
  project: string
  project_root: string
  short_cwd: string
  session_title: string | null
  display_name: string
  status: string
  status_group: string
  status_dot: string
  status_reason: string
  current_activity: string
  user_instruction: string
  instruction_source: string | null
  instruction_confidence: number
  instruction: InstructionInfo
  child_processes: ProcessInfo[]
  active_commands: string[]
  foreground: ForegroundAgentInfo
  background_jobs: BackgroundJob[]

  // Heartbeat
  heartbeat_ts: number | null
  heartbeat_age_sec: number | null

  // Session file data
  recent_output: string
  pending_items: string[]
  last_user_message: string
  conversation: ConversationMessage[]
  source_file: string
  confidence: number

  // Resource metrics
  cpu_percent: number
  memory_percent: number

  // Project status
  project_status: ProjectRuntimeStatus
  git_status: string
  git_status_detail: GitStatusDetail
  error_hints: string[]
  recent_files: string[]
  resource_usage: ResourceUsage
  is_pinned: boolean
  is_ignored: boolean
  tags: string[]

  // Timeline
  timeline: ActivityTimelineItem[]

  // Logs
  recent_logs: string[]
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

export interface ScanMeta {
  hostname: string
  last_scan_time: number
  scan_interval: number
  discovery_ttl: number
  active_sessions_count: number
}

export interface SSEData {
  tasks: Task[]
  discovered: DiscoveredSession[]
  system: SystemMetrics
  scan: ScanMeta
}
