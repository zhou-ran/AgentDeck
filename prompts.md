
---

## Prompt 1：总体需求设计

```text
你是一个资深全栈工程师。请帮我设计并实现一个“本地 Coding Agent 监控面板”，运行在 Linux 服务器上，通过局域网网页访问。

背景：
我在一台 Linux 机器上同时运行多个 coding agent，例如 codex、claude、aider、gemini、node/python 子进程、pytest、npm test、git、Rscript 等。我现在需要频繁切换 terminal 才能知道每个 agent 在做什么。我希望有一个本地网页 dashboard，统一显示所有 agent 的任务流程、当前状态、运行命令、日志输出、资源占用和是否完成。

参考理念：
参考 agent-foreman 的工作流思想：每个 agent 任务都应该有结构化状态文件、progress log、当前 feature、acceptance criteria、handoff/progress 记录。不要只是做一个进程监控器，而是做一个“Agent Foreman / Agent Supervisor”式的本地监控系统。

目标：
实现一个局域网可访问的网页，例如：
http://<server-ip>:8787

核心功能：
1. 自动发现正在运行的 agent 进程
   - 匹配关键字：codex, claude, aider, gemini, node, python, uv, npm, pnpm, bun, git, pytest, Rscript
   - 显示 PID、PPID、USER、STAT、ETIME、CPU%、MEM%、完整命令、工作目录 cwd
   - 显示父子进程树，能看出 agent 正在调用 git / pytest / npm / python / Rscript 等子进程

2. 任务状态识别
   - running：进程仍在运行且日志/CPU/子进程活跃
   - idle：进程存在但 CPU 低、日志长时间未更新
   - waiting_input：疑似等待输入
   - completed：进程结束，并且日志中出现完成标记，或者 exit code 为 0
   - failed：进程结束且 exit code 非 0，或者日志中出现 error/failed/traceback
   - unknown：无法判断

3. 日志管理
   - 约定所有 agent 日志放在 ~/agent_logs/
   - 每个任务一个 log 文件，例如 precancer_A.log
   - dashboard 可以 tail 最新日志
   - 显示最后 50 行日志
   - 显示日志最后更新时间、大小、最近是否更新
   - 支持通过 task_id 关联进程和日志文件

4. 结构化任务文件
   - 在 ~/.agent_foreman_local/tasks/ 下保存任务状态
   - 每个任务一个 JSON 或 YAML 文件
   - 字段包括：
     task_id
     name
     project_dir
     command
     pid
     status
     started_at
     ended_at
     last_log_update
     acceptance_criteria
     current_step
     progress_notes
     exit_code
     tags

5. 网页 UI
   - 首页显示所有任务卡片
   - 每个卡片显示：
     name
     status
     project_dir
     command
     elapsed time
     CPU/MEM
     network/disk 简要指标，如果不好实现可以先留接口
     current_step
     last log lines
   - 状态颜色：
     running 绿色
     idle 黄色
     waiting_input 橙色
     failed 红色
     completed 蓝色/灰色
   - 支持点击任务进入详情页
   - 详情页显示完整元数据、进程树、日志 tail、progress notes、acceptance criteria

6. 实时更新
   - 使用 WebSocket 或 SSE
   - 前端每 1-2 秒刷新状态
   - 不要每次整页刷新

7. 启动 agent 的包装命令
   - 实现一个命令行工具：
     agentctl start <name> --dir <project_dir> -- <command...>
   - 它负责：
     创建 task JSON
     启动进程
     将 stdout/stderr 写入 ~/agent_logs/<task_id>.log
     保存 PID
     记录 started_at
   - 实现：
     agentctl list
     agentctl status
     agentctl stop <task_id>
     agentctl tail <task_id>
   - dashboard 读取这些任务文件和进程状态

8. 安全要求
   - 默认只监听 127.0.0.1
   - 如果配置 --host 0.0.0.0 才允许局域网访问
   - 提供简单 token 认证
   - 不要暴露任意 shell 执行接口
   - stop 只能停止由 agentctl 启动并记录的任务
   - 不要允许网页直接执行任意命令
   - 日志读取限制在 ~/agent_logs 和 ~/.agent_foreman_local/tasks 内

9. 技术栈优先级
   - 后端：Python FastAPI
   - 前端：React + Vite + Tailwind
   - 实时通信：SSE 或 WebSocket
   - 进程信息：psutil
   - 进程树：psutil.Process(pid).children(recursive=True)
   - 日志 tail：Python 实现
   - 配置文件：~/.agent_foreman_local/config.yaml

请先输出：
1. 项目结构
2. 数据模型
3. API 设计
4. 状态判断逻辑
5. 安全边界
6. 分阶段实现计划

然后开始实现 MVP。
MVP 要求：
- agentctl 可以 start/list/stop/tail
- dashboard 可以显示任务列表和详情
- 可以实时刷新状态
- 可以显示日志最后 50 行
- 可以显示进程树
- 可以在局域网访问
```

---

## Prompt 2：让它先做 MVP，不要一上来过度工程

```text
请基于上面的设计实现 MVP。不要过度工程化，先做一个可运行版本。

MVP 范围：
1. 后端 FastAPI
   - GET /api/tasks
   - GET /api/tasks/{task_id}
   - GET /api/tasks/{task_id}/logs?lines=50
   - GET /api/tasks/{task_id}/process-tree
   - POST /api/tasks/{task_id}/stop
   - GET /api/events 使用 SSE 推送任务状态

2. CLI：agentctl
   - agentctl start <name> --dir <project_dir> -- <command...>
   - agentctl list
   - agentctl stop <task_id>
   - agentctl tail <task_id>
   - agentctl status <task_id>

3. 前端
   - React + Vite
   - 任务列表页面
   - 任务详情页面
   - 每 2 秒更新一次或使用 SSE
   - 显示状态、PID、运行时间、cwd、CPU、MEM、命令、日志尾部、进程树

4. 文件约定
   - ~/.agent_foreman_local/tasks/*.json
   - ~/agent_logs/*.log

5. 状态判断
   - 如果 PID 存在：running / idle
   - 如果 PID 不存在且 exit_code == 0：completed
   - 如果 PID 不存在且 exit_code != 0：failed
   - 如果 PID 存在但 CPU 低且日志 5 分钟没更新：idle
   - 如果日志包含 “Traceback”, “ERROR”, “Failed”, “Exception”：标记 has_error_hint=true

6. 安全
   - 默认 host=127.0.0.1
   - dashboard 启动参数支持 --host 0.0.0.0
   - token 认证可以先用环境变量 AGENT_FOREMAN_TOKEN
   - 不允许网页提交任意命令
   - stop 只能 stop task json 里记录的 PID

请直接创建完整项目代码，包括：
- README.md
- backend app
- frontend app
- agentctl CLI
- 安装说明
- 启动说明
- 示例命令

验收标准：
- 我可以运行 `agentctl start test --dir /tmp -- bash -c "for i in {1..100}; do echo step $i; sleep 1; done"`
- 打开网页能看到 test 任务
- 能看到日志实时增长
- 能看到进程树
- 任务结束后状态变 completed
```

---

## Prompt 3：让它把“任务流程”做成 agent-foreman 风格

```text
现在请把 MVP 升级成真正的 Agent Foreman 风格任务流程管理。

新增结构化任务字段：
- goal：任务目标
- feature：当前 feature
- acceptance_criteria：验收标准数组
- plan：步骤数组，每一步包含 id/title/status/notes
- current_step_id
- progress_log：结构化进展记录
- handoff_notes：用于下次会话接手的说明
- changed_files：agent 修改过的文件列表
- risk_notes：风险、阻塞、潜在问题
- final_summary：完成后总结

新增 CLI：
- agentctl init <name> --dir <project_dir> --goal "..."`
- agentctl set-plan <task_id> plan.md
- agentctl note <task_id> "..."
- agentctl step <task_id> <step_id> --status running|done|blocked
- agentctl complete <task_id> --summary "..."
- agentctl fail <task_id> --reason "..."
- agentctl handoff <task_id>

新增 UI：
1. 任务详情页顶部显示：
   - goal
   - feature
   - acceptance criteria
   - current step
   - status

2. 中间显示：
   - plan checklist
   - 每一步状态
   - progress timeline
   - handoff notes

3. 底部显示：
   - live logs
   - process tree
   - changed files
   - risk notes

实现 changed_files：
- 如果 project_dir 是 git 仓库，调用只读命令：
  git status --short
  git diff --name-only
- 不要在后端执行危险命令
- 只允许在 task.project_dir 下执行 git status/diff 这类白名单命令

验收标准：
- 我能用 agentctl init 创建一个有目标和验收标准的任务
- 我能在网页看到 plan 和 current step
- agent 运行过程中可以追加 progress note
- handoff 页面能生成一段可以复制给下一个 agent 的交接文本
```

---

## Prompt 4：让它加“自动识别现有 agent 进程”

```text
现在新增“自动发现模式”，用于监控不是通过 agentctl 启动的现有 coding agent。

需求：
1. 扫描系统进程，匹配：
   codex, claude, aider, gemini, node, python, uv, npm, pnpm, bun, pytest, Rscript
2. 自动发现进程的：
   PID
   PPID
   USER
   command
   cwd
   start time
   cpu_percent
   memory_percent
   children
3. 尝试按 cwd 聚合：
   - 同一个项目目录下的 agent 和子进程归为一个 discovered session
4. UI 单独显示一个 “Discovered Agents” 区域
5. 对 discovered agent 只允许查看，不允许 stop，除非用户显式 import
6. 新增：
   agentctl import-pid <pid> --name <name>
   将现有 PID 转为受管理 task，但要明确标记 imported=true
7. 对自动发现的 agent，如果 cwd 无法读取，显示 unknown
8. 不使用 ptrace，不修改 /proc/sys/kernel/yama/ptrace_scope
9. 只读取 /proc 和 psutil 能读到的信息，权限不足就显示 permission_denied

验收标准：
- 不通过 agentctl 启动的 codex/claude 也能在网页中看到
- 能看到它在哪个 cwd
- 能看到它的子进程
- 可以 import 成正式 task
```

---

## Prompt 5：让它加网络、磁盘、资源占用

```text
请给 dashboard 增加资源观测能力。

功能：
1. 每个 task 显示：
   - CPU%
   - MEM%
   - RSS memory
   - number of child processes
   - open file count
   - read_bytes/write_bytes，如果 psutil 支持
   - network 暂时不要求按进程精确，先显示全局网卡速度

2. 系统总览卡片：
   - total CPU
   - total memory
   - disk usage of project dirs
   - network rx/tx per second by interface

3. 对每个 task，显示最近 60 秒 CPU/MEM 历史
   - 后端维护内存 ring buffer
   - 前端画简单折线图

4. 如果可以安全实现，读取 /proc/<pid>/io 显示 read_bytes/write_bytes
   - 权限不足时 graceful fallback

5. 不要要求 sudo
6. 不要使用 ptrace
7. 不要执行 nethogs/iftop 这类需要 root 的命令
8. 可以在 README 中说明：如果需要更精确的 per-process network，需要额外权限或 eBPF，但 MVP 不做

验收标准：
- dashboard 可以看到每个 task 的 CPU/MEM 变化
- 可以看到系统网卡总速率
- 不需要 sudo 即可运行
```

---

## Prompt 6：安全加固 Prompt

```text
请对当前项目做一次安全加固。我的场景是局域网访问，但机器上可能有 API key、SSH key、科研数据和多个用户，所以不能做危险设计。

必须满足：
1. 默认只监听 127.0.0.1
2. 如果监听 0.0.0.0，启动时打印醒目的安全提醒
3. Web UI 必须 token 认证
4. token 来源：
   - 环境变量 AGENT_FOREMAN_TOKEN
   - 或 ~/.agent_foreman_local/config.yaml
5. 不允许网页执行任意 shell 命令
6. 不允许网页修改任意文件
7. 日志读取只能在允许目录：
   - ~/agent_logs
   - ~/.agent_foreman_local
8. project_dir 必须是真实目录，不能是 symlink 到敏感目录
9. stop 只能停止 task JSON 中记录的 PID
10. stop 前检查：
   - PID 仍然存在
   - PID command 与 task.command 有基本匹配
   - PID cwd 与 task.project_dir 匹配或是其子目录
11. 不保存 API key、环境变量完整内容
12. 不展示 /proc/<pid>/environ
13. 不使用 ptrace
14. 不建议用户设置 kernel.yama.ptrace_scope=0
15. 前端避免 XSS：
   - 日志作为 text 显示，不作为 HTML 注入
16. API 加 rate limit 或基本防刷保护
17. 写入 task json 用 atomic write，避免损坏

请输出：
- 安全威胁模型
- 已修复的问题
- 代码修改
- README 中的安全说明
```

---

## Prompt 7：最终打磨 Prompt

```text
请把这个项目打磨成我长期使用的本地工具。

要求：
1. 一键安装：
   - make install
   - 或 pipx install .
2. 一键启动：
   - agent-foreman-local serve --host 127.0.0.1 --port 8787
3. 开发模式：
   - make dev
4. 生产模式：
   - 使用 uvicorn
5. systemd user service：
   - 生成 ~/.config/systemd/user/agent-foreman-local.service
   - 支持开机自启
6. README 给出完整用法：
   - 启动 dashboard
   - 启动 agent
   - 查看日志
   - 停止任务
   - 导入已有 PID
   - 局域网访问
   - token 配置
7. UI 优化：
   - 任务卡片紧凑
   - 支持按 status 过滤
   - 支持按 project 搜索
   - 支持只看 running
   - 支持复制 handoff notes
8. 增加测试：
   - task store
   - process scanner
   - log tail
   - status inference
   - path safety
9. 增加 demo：
   - scripts/demo_long_task.sh
   - scripts/demo_fail_task.sh

最终验收：
- 我能在服务器上启动网页
- 手机或另一台电脑在同一局域网输入 server-ip:8787 可以查看
- 能看到多个 agent 的状态、日志、进程树和任务流程
- 不需要切换 terminal
- 不需要 sudo
- 不暴露任意命令执行能力
```

---

## 我建议你给 coding agent 的第一条最终版

你可以直接从这条开始：

```text
请实现一个本地局域网 Coding Agent 监控网页，项目名叫 agent-foreman-local。

它参考 agent-foreman 的思想：用结构化任务文件、progress log、acceptance criteria、handoff notes 管理 AI coding agent 的执行过程。它不是单纯的 ps/top，而是一个本地 Agent Supervisor。

技术栈：
- Backend: Python FastAPI + psutil
- Frontend: React + Vite + Tailwind
- CLI: Python Typer
- Storage: ~/.agent_foreman_local/tasks/*.json
- Logs: ~/agent_logs/*.log
- Realtime: SSE

核心命令：
- agentctl start <name> --dir <project_dir> -- <command...>
- agentctl list
- agentctl status <task_id>
- agentctl tail <task_id>
- agentctl stop <task_id>
- agentctl import-pid <pid> --name <name>
- agent-foreman-local serve --host 127.0.0.1 --port 8787

网页功能：
- 任务列表
- 任务详情
- live log tail
- process tree
- CPU/MEM/elapsed time
- cwd/command/PID/PPID
- plan checklist
- progress timeline
- handoff notes
- discovered agents 区域，用于显示不是通过 agentctl 启动的 codex/claude/aider 等进程

安全要求：
- 默认只监听 127.0.0.1
- 局域网访问必须显式 --host 0.0.0.0
- token 认证
- 不允许网页执行任意 shell
- stop 只能停止 agentctl 管理的 PID
- 不读取 /proc/<pid>/environ
- 不使用 ptrace
- 不要求 sudo
- 日志只读取 ~/agent_logs 和 ~/.agent_foreman_local 内文件

请先输出架构设计、数据模型、API 设计、项目结构、实现计划，然后实现 MVP。MVP 必须能运行，并给出 README 和 demo。
```

这个方向比单纯 `tmux + btop + nethogs` 更适合你的长期需求：它能把“进程是否还活着”和“agent 任务到底推进到哪一步”合并到一个局域网网页里。

[1]: https://github.com/mylukin/agent-foreman?utm_source=chatgpt.com "mylukin/agent-foreman"

