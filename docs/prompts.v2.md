重构目标定

> **从“进程列表”升级为“项目维度的 Agent Live Session 面板”。**

## 重构 Prompt：把 import 模式改成自动 Agent 任务识别

```text
你现在接手一个本地 Agent Foreman / Agent Monitor 项目。当前实现偏弱，需要重构。

我的核心需求不是手动 import 任务，而是：

1. 自动发现本机正在运行的 coding agent
   - Codex
   - kimi-code
   - Claude Code
   - aider
   - gemini
   - 以及它们启动的子进程，例如 node、python、pytest、npm、pnpm、uv、Rscript、git 等

2. 不需要我手动 import PID
   - dashboard 默认就应该显示所有正在运行的 agent session
   - 每个 session 自动归类成一个“任务”
   - 任务卡片应该以项目为中心，而不是以 PID 为中心

3. 自动从 cwd 提炼项目名
   - 例如：
     /data/zhouran/agents/projects/01.PreCancerAtlas_A
     应该显示：
     01.PreCancerAtlas_A
   - 如果路径符合 worktree 命名，也可以额外显示：
     Project: PreCancerAtlas
     Workspace: A
   - 如果 cwd 是：
     /data/zhouran/agents/projects/03.GBMAgeing_B
     显示：
     03.GBMAgeing_B
   - 不要让我自己看一长串 cwd 来判断任务是谁

4. 自动识别“这个 agent 当前在做什么”
   - 不只是显示 command
   - 要尽可能从以下来源推断当前活动：
     a. agent 进程命令行
     b. 子进程命令行
     c. 最近日志
     d. git 状态
     e. 当前活跃文件
     f. 最近修改文件
     g. 项目目录中的 agent 记录文件，例如 .codex、.claude、.kimi、.agent、logs、transcript 等，如果存在
   - dashboard 应该显示类似：
     “正在运行 pytest”
     “正在执行 git diff”
     “正在修改 README.md / src/api.py”
     “最近在分析文献检索模块”
     “可能在等待用户输入”
     “最近 5 分钟无日志更新，可能 idle”

5. 我希望看到我给 agent 的原始指令 / 当前任务目标
   - 如果 agent 本身有 transcript / session log / history 文件，应该自动扫描并提取最近一条用户指令
   - 对 Codex / Claude Code / kimi-code 分别做适配
   - 如果无法准确获取，也要在 UI 中显示：
     “未找到原始指令”
   - 不能瞎编
   - 可以从日志里用启发式提取：
     User:
     Human:
     Prompt:
     Task:
     Instruction:
     > 用户指令
     等模式
   - 提取结果需要标注来源，例如：
     source: ~/.codex/sessions/xxx.log
     source: project/.claude/xxx.jsonl
     source: agent log tail
     source: process args
   - 如果有多个候选，显示最新的，并允许展开查看候选

6. 我希望直接看到项目运行状态
   每个项目任务卡至少显示：
   - 项目名
   - cwd 简短路径
   - agent 类型：codex / kimi-code / claude / aider / unknown
   - PID
   - 子进程数量
   - 当前活动 current_activity
   - 原始用户指令 user_instruction，如果可获取
   - 运行时长
   - CPU / MEM
   - 日志最后更新时间
   - git dirty 状态
   - 最近修改文件
   - 是否有测试在跑
   - 是否有报错迹象
   - 状态：
     running
     busy
     testing
     editing
     waiting
     idle
     completed
     failed
     unknown

7. UI 不要以 “Import PID” 为主
   - import 可以保留为高级功能，但不应该是主要路径
   - 首页默认就是 “Live Agent Sessions”
   - 自动显示所有 agent
   - 可以有一个 “Managed Tasks” 区域，但不是必须
   - 重点是自动发现、自动识别、自动聚合

请基于以上要求重构项目。
```

---

## 更具体的技术实现 Prompt

```text
请实现一个自动发现和识别 coding agent session 的 scanner。

核心设计：

一、Agent Session 自动发现

扫描所有进程，匹配 agent root process：

agent_patterns:
- codex
- kimi
- kimi-code
- claude
- claude-code
- aider
- gemini

注意：
- node/python/bash 可能是 agent 的子进程，但不要直接当作 root agent
- 如果 node/python 的父进程链里有 codex/claude/kimi-code，则归入对应 agent session
- 如果发现 pytest/npm/git/Rscript 是某个 agent 的子进程，则显示为该 agent 当前活动

实现函数：
scan_agent_sessions() -> List[AgentSession]

AgentSession 字段：
- session_id
- agent_type
- root_pid
- root_cmd
- user
- cwd
- project_name
- short_cwd
- started_at
- elapsed
- status
- current_activity
- user_instruction
- instruction_source
- child_processes
- active_commands
- cpu_percent
- memory_percent
- log_candidates
- recent_logs
- git_status
- recent_changed_files
- error_hints
- confidence

二、项目名提炼

实现：
derive_project_name(cwd: str) -> ProjectNameInfo

规则：
1. 默认取 cwd basename
2. 如果 basename 形如：
   01.PreCancerAtlas_A
   03.GBMAgeing_B
   则解析：
   display_name = "01.PreCancerAtlas_A"
   base_project = "PreCancerAtlas"
   workspace = "A"
3. 如果路径包含 /projects/，优先取 /projects/ 后面的第一层目录
4. 如果 cwd 是子目录，例如：
   /data/zhouran/agents/projects/01.PreCancerAtlas_A/src/module
   应该向上寻找 git root
   如果是 git repo，项目名取 git root basename
5. short_cwd 显示成：
   ~/agents/projects/01.PreCancerAtlas_A
   或
   .../projects/01.PreCancerAtlas_A

三、当前活动识别 current_activity

根据子进程和最近日志综合判断。

优先级：
1. 如果有 pytest 子进程：
   current_activity = "Running tests: pytest ..."
   status = "testing"
2. 如果有 npm/pnpm/yarn test：
   current_activity = "Running frontend tests"
   status = "testing"
3. 如果有 git diff/status/add/commit：
   current_activity = "Inspecting or modifying git state"
4. 如果有 python/Rscript/bash 子进程：
   current_activity = "Running script: <short command>"
5. 如果有 rg/ripgrep/find/grep：
   current_activity = "Searching codebase"
6. 如果最近修改文件在 60 秒内变化：
   current_activity = "Editing files: <top files>"
   status = "editing"
7. 如果日志在 60 秒内更新：
   current_activity = 从最近日志摘要提取
   status = "busy"
8. 如果进程存在但 CPU 低、无子进程、日志 5 分钟没更新：
   current_activity = "No recent activity; possibly waiting or idle"
   status = "idle"
9. 如果进程不存在：
   根据 exit_code / error_hints 判断 completed 或 failed

四、原始用户指令提取

实现：
extract_user_instruction(session: AgentSession) -> InstructionInfo

必须是 best-effort，不允许瞎编。

来源优先级：
1. agent 自带 session/transcript 文件
2. 项目目录里的日志文件
3. ~/agent_logs 里的相关日志
4. 进程命令行参数
5. 不确定则返回 None

适配路径候选：

Codex:
- ~/.codex/
- ~/.codex/sessions/
- ~/.codex/logs/
- project/.codex/
- project/.codex/sessions/
- project/.codex/logs/

Claude Code:
- ~/.claude/
- ~/.claude/projects/
- project/.claude/
- project/.claude/logs/

Kimi Code:
- ~/.kimi/
- ~/.kimi-code/
- project/.kimi/
- project/.kimi-code/

通用：
- ~/agent_logs/
- project/logs/
- project/.agent/
- project/.agent_foreman/
- project/AGENT_LOG.md
- project/progress.md

提取模式：
- "User:"
- "Human:"
- "Prompt:"
- "Task:"
- "Instruction:"
- "用户:"
- "用户指令:"
- "目标:"
- JSONL 中的 role=user
- JSON 中的 {"role": "user", "content": "..."}
- Markdown 中的 ## User / ## Task / ## Goal

返回：
- text
- source_file
- source_type
- timestamp
- confidence

如果找不到：
text = null
confidence = 0
UI 显示 “未找到原始指令”

五、项目运行状态识别

实现：
get_project_runtime_status(project_dir)

显示：
- git_branch
- git_dirty_files_count
- git_changed_files
- recent_modified_files，最近 10 个
- test_processes
- server_processes，例如 vite/uvicorn/streamlit/jupyter/rstudio-server
- error_hints，从日志中提取 ERROR/Traceback/Exception/Failed
- last_activity_time

只允许运行只读命令：
- git rev-parse --show-toplevel
- git branch --show-current
- git status --short
- git diff --name-only
禁止执行任意 shell 命令。
所有 subprocess 必须 shell=False。
必须设置 timeout。
```

---

## UI 重构 Prompt

```text
请重构前端 UI。当前 UI 不要再强调 import PID，而是默认展示自动发现的 Live Agent Sessions。

首页布局：

标题：
Local Coding Agent Foreman

顶部系统概览：
- 当前发现的 agent 数量
- busy/testing/editing/idle/failed 数量
- 总 CPU/MEM
- 最近活跃项目
- 最后扫描时间

主区域：
Live Agent Sessions

每个 session 用一张卡片显示：

第一行：
[状态徽章] [agent 类型 icon/name] [项目名] [workspace] [运行时长]

第二行：
当前活动：
current_activity

第三行：
用户指令：
user_instruction 的一行摘要
如果没有：
“未找到原始指令”

第四行：
项目状态：
- branch
- dirty files count
- recent changed files
- test running yes/no
- error hints yes/no

第五行：
资源：
- PID
- children count
- CPU
- MEM
- last log update

按钮：
- 查看详情
- 查看日志
- 查看进程树
- 打开 handoff
- 复制项目路径

详情页：

1. Overview
- project_name
- agent_type
- cwd
- root_pid
- root_cmd
- started_at
- elapsed
- status
- current_activity

2. User Instruction
- extracted instruction
- source
- confidence
- candidate instructions 可展开

3. Process Tree
- root agent
- child processes
- active commands
- 高亮 pytest/git/npm/python/Rscript

4. Project Status
- git branch
- git status
- changed files
- recent modified files
- running tests
- running servers

5. Live Logs
- 自动刷新
- 默认显示最后 100 行
- 错误行高亮，但以 text 渲染，不能 innerHTML

6. Activity Timeline
- 根据日志更新时间、文件修改时间、子进程变化生成时间线
- 例如：
  10:12 started codex
  10:15 searching codebase
  10:18 editing src/api.py
  10:21 running pytest
  10:24 idle

UI 要求：
- 我不想看到一堆长 PID 列表
- 我想一眼知道哪个项目的哪个 agent 正在干什么
- 项目名比 PID 更重要
- current_activity 和 user_instruction 是最重要字段
```

---

## 状态判断逻辑 Prompt

```text
请实现 status inference，不要只用 running/idle。

状态枚举：
- busy：agent 活跃，但无法细分
- testing：正在跑测试
- editing：最近有文件修改
- searching：正在 grep/rg/find
- git_ops：正在执行 git 操作
- running_script：正在跑 python/R/bash/node 脚本
- waiting：可能等待用户输入
- idle：进程存在但最近无活动
- completed：进程结束且无错误
- failed：发现错误或异常
- unknown：无法判断

判断规则：

testing:
- 子进程命令包含 pytest
- 或 npm test / pnpm test / yarn test
- 或日志最近包含 running tests / pytest / test session starts

editing:
- 最近 60 秒 project_dir 内有文件 mtime 更新
- 排除 .git, node_modules, __pycache__, .venv, logs

searching:
- 子进程包含 rg, grep, find, fd

git_ops:
- 子进程包含 git
- 并显示具体 git 子命令

running_script:
- 子进程包含 python, Rscript, bash, node
- 且不是 agent 自身

waiting:
- 进程 CPU < 1%
- 没有活跃子进程
- 日志最近包含：
  waiting for input
  approve?
  continue?
  confirm
  permission
  需要确认
  是否继续
  y/n

idle:
- 进程存在
- CPU < 1%
- 无活跃子进程
- 日志超过 5 分钟未更新
- 最近文件未修改

busy:
- 进程存在
- CPU > 3%
- 或日志 60 秒内更新
- 但无法归类为 testing/editing/searching/git_ops

failed:
- 日志最近包含：
  Traceback
  ERROR
  Exception
  Failed
  failed
  command not found
  permission denied
  quota exceeded
  API error
  rate limit
  认证失败

completed:
- 受管理任务进程结束且 exit_code=0
- 自动发现任务如果进程消失，不要强行显示 completed，显示 disappeared unless 有历史 task 记录

所有状态都要带 reason：
status_reason = "pytest child process detected"
status_reason = "log updated 12s ago"
status_reason = "no CPU/log/file activity for 8m"
```

---

## 关键补充：你想要“我问的指令是什么”，必须承认限制

这一点要在 prompt 里写清楚，否则 coding agent 容易瞎做：

```text
关于 user_instruction 的限制：

不要假装总能获取用户原始指令。

如果 agent 没有把会话保存到文件，普通 Linux 进程扫描无法直接知道用户刚刚在 TUI 里输入了什么。

因此实现必须分层：
1. 能从官方 session/transcript/log 文件提取则显示
2. 能从 ~/agent_logs 提取则显示
3. 能从命令行参数提取则显示
4. 都不行则显示 “未找到原始指令”
5. 不允许根据当前代码修改内容臆测用户指令

如果要长期稳定显示用户指令，建议提供 wrapper：
agentctl start --instruction "..." --dir ... -- codex

但自动发现模式仍然必须尽力从已有文件中提取。
```

---

## 建议新增一个“可选增强”：Agent Wrapper，但不是必须 import

你不想 import 是对的，但为了**稳定知道原始指令**，最好让系统支持“自动包装启动”。不是 import，而是以后可以这样启动：

```bash
agentctl run codex \
  --name precancer_A \
  --dir /data/zhouran/agents/projects/01.PreCancerAtlas_A \
  --instruction "完善 Scholar literature 模块，并跑通测试" \
  -- codex
```

对应 prompt：

```text
请新增 agentctl run 命令，但不要把它作为唯一使用方式。

目标：
- 自动发现模式仍然是默认
- agentctl run 是增强模式，用来稳定记录 user_instruction、goal、日志和 exit_code

命令：
agentctl run <agent_type> \
  --name <name> \
  --dir <project_dir> \
  --instruction "<我给 agent 的原始任务>" \
  -- <command...>

它做：
1. 创建 task json
2. 记录 instruction
3. 启动 codex/claude/kimi-code
4. stdout/stderr 写入 ~/agent_logs/<task_id>.log
5. dashboard 自动把这个 task 和进程合并显示

注意：
这不是 import。
这是“启动时自动登记”。
UI 中仍然以 Live Agent Sessions 为主。
```

---

## 最终你可以直接发给本地 agent 的完整短版

```text
当前版本写得不好，请重构。

我的真实需求是一个“自动发现的本地 Coding Agent Foreman”，不是手动 import PID 的进程监控器。

必须改成：

1. 默认自动发现所有正在运行的 Codex、kimi-code、Claude Code、aider、gemini agent。
2. 不需要我 import。首页默认显示 Live Agent Sessions。
3. 每个 session 自动按 cwd/git root 聚合成一个项目任务。
4. 自动把 cwd 提炼成项目名，例如 /data/zhouran/agents/projects/01.PreCancerAtlas_A 显示为 01.PreCancerAtlas_A，而不是让我看长路径。
5. 每张任务卡最重要的信息是：
   - 项目名
   - agent 类型
   - 当前活动 current_activity
   - 我给 agent 的原始指令 user_instruction，如果能提取
   - 项目运行状态
   - git dirty 状态
   - 最近修改文件
   - 是否在跑测试
   - 是否有错误
   - CPU/MEM/运行时长
6. 自动识别当前 agent 具体在做什么：
   - pytest/npm test => testing
   - git => git_ops
   - rg/grep/find => searching
   - python/Rscript/bash/node => running_script
   - 最近文件修改 => editing
   - 日志更新但无法分类 => busy
   - 长时间无 CPU/日志/文件变化 => idle
   - 日志有 Traceback/ERROR/Failed/Exception => failed hint
7. 尽可能提取我给 agent 的原始指令：
   - 扫描 Codex / Claude Code / kimi-code 的 session、transcript、logs 文件
   - 扫描项目目录 .codex、.claude、.kimi、logs
   - 扫描 ~/agent_logs
   - 支持 JSONL role=user
   - 支持 User/Human/Prompt/Task/Instruction/用户指令 等模式
   - 必须显示 source 和 confidence
   - 找不到就显示“未找到原始指令”，不能瞎编
8. 详情页显示：
   - Overview
   - User Instruction
   - Current Activity
   - Process Tree
   - Project Status
   - Git Status
   - Recent Changed Files
   - Live Logs
   - Activity Timeline
9. import-pid 可以保留为高级功能，但不能作为主流程。
10. 新增可选 agentctl run，用于以后稳定记录 instruction，但自动发现仍然必须可用。
11. 安全要求：
   - 不使用 ptrace
   - 不要求 sudo
   - 不读取 /proc/<pid>/environ
   - 不允许网页执行任意 shell
   - git 命令必须白名单、shell=False、timeout
   - 日志以 text 渲染，避免 XSS
   - 默认 127.0.0.1，局域网访问必须显式 --host 0.0.0.0 + token

请先重构数据模型和 scanner，然后重构 API 和 UI。重点不是 PID，而是“哪个项目的哪个 agent 正在做什么，我最初让它做什么，现在项目状态如何”。
```

---

