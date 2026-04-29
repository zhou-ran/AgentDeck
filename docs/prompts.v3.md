请参考 tmp/agent-foreman-main.zip 项目，重构我们自己的本地 Coding Agent 监控面板。

注意：我不是要照搬远程 SSH 管理功能。我只需要本地/局域网的 agent 监工台。

请完全借鉴 agent-foreman 的优秀设计：
1. 卡片式 dashboard
2. 状态分组
3. Codex / Claude Code session 文件解析
4. heartbeat_ts 判断活跃度
5. recent_output / pending_items / last_user_message 展示
6. 静默后台刷新，不要整页闪烁
7. 一眼看出哪个 agent 在工作、哪个在等输入、哪个可能摸鱼
8. 中文化、有趣但清晰的 UI 风格

但必须删除或不实现：
1. 远程 SSH 主机管理
2. SSH 密码/密钥管理
3. credentials.enc.json
4. master password
5. 浏览器向远程终端发话
6. ptrace / TIOCSTI 注入
7. 修改 kernel.yama.ptrace_scope
8. macOS 远程登录支持
9. 任意命令执行接口

项目目标：
做一个 agent-foreman-local，本地运行，通过局域网网页查看本机所有 coding agent 的实时状态。

核心要求：

一、自动发现 agent
默认扫描本机进程，不需要 import PID。
支持：
- codex
- claude
- claude-code
- kimi
- kimi-code
- aider
- gemini

发现 agent root process 后，自动收集：
- PID
- PPID
- USER
- cwd
- command
- started_at
- elapsed
- CPU%
- MEM%
- 子进程树

二、自动按项目聚合
不要让我看长 cwd。
从 cwd/git root 提炼项目名。

例如：
/data/zhouran/agents/projects/01.PreCancerAtlas_A
显示：
01.PreCancerAtlas_A

如果路径是：
/data/zhouran/agents/projects/01.PreCancerAtlas_A/src/module
要向上找到 git root，项目名仍然是：
01.PreCancerAtlas_A

三、借鉴 agent-foreman 的 session 解析
实现或迁移：
- parse_codex_session()
- parse_claude_session()
- session matching
- heartbeat_ts
- recent_output
- pending_items
- last_user_message
- source_file

并新增 kimi-code 支持：
候选路径：
- ~/.kimi/
- ~/.kimi-code/
- project/.kimi/
- project/.kimi-code/
- ~/agent_logs/

四、首页默认显示 Live Agent Sessions
不要以 import 为主。
每个 agent session 一张卡片。

卡片核心字段：
- 项目名
- agent 类型：Codex / Claude / Kimi / Aider / Gemini
- 状态
- 当前活动 current_activity
- 用户原始指令 last_user_message / user_instruction
- 最近输出 recent_output
- 待办 pending_items
- cwd 简短路径
- branch
- git dirty 文件数量
- 最近修改文件
- 是否正在跑测试
- 是否有错误提示
- PID
- CPU / MEM
- elapsed
- heartbeat age

五、状态分组借鉴 agent-foreman，但增强
保留类似：
- Needs Input
- Working
- Slacking

但内部状态更细：
- needs_input
- testing
- editing
- searching
- git_ops
- running_script
- busy
- idle
- stale
- error_hint
- unknown

判断规则：
1. recent_output 命中问题/确认/需要输入模式 => needs_input
2. 子进程包含 pytest / npm test / pnpm test => testing
3. 子进程包含 rg / grep / find / fd => searching
4. 子进程包含 git => git_ops
5. 子进程包含 python / Rscript / bash / node => running_script
6. 最近 60 秒项目文件有修改 => editing
7. heartbeat 120 秒内更新 => busy
8. heartbeat 超过 15 分钟未更新 => stale
9. CPU 很低、无子进程、无日志更新 => idle
10. 日志包含 Traceback / ERROR / Failed / Exception / permission denied / quota exceeded => error_hint

每个状态必须带 status_reason。

六、当前活动 current_activity
不要只显示 command。
要显示人能看懂的话，例如：
- 正在跑 pytest
- 正在执行 git status
- 正在搜索代码库
- 正在修改 src/api.py
- 最近在输出：xxx
- 可能在等待用户确认
- 15 分钟无新输出，可能空闲

七、项目状态
只允许执行安全的只读命令：
- git rev-parse --show-toplevel
- git branch --show-current
- git status --short
- git diff --name-only

要求：
- shell=False
- timeout
- cwd 必须在 project_dir 里
- 不允许网页执行任意 shell

八、日志与指令提取
尽量从这些来源提取 user_instruction：
- Codex session jsonl
- Claude project jsonl
- kimi-code session/log
- ~/agent_logs
- project/.codex
- project/.claude
- project/.kimi
- project/logs

如果找不到，显示：
未找到原始指令

不能瞎编。
必须显示 source_file 和 confidence。

九、UI 改造
借鉴 agent-foreman 的卡片式 dashboard 和中文风格，但删掉：
- 管工地
- 新增工地
- SSH host form
- 发话 textarea
- master password 相关提示

首页结构：
1. 顶部标题：本地牛马监工台 / Local Agent Foreman
2. Summary cards：
   - 全部 agent
   - 等输入
   - 正在工作
   - 正在测试
   - 疑似摸鱼/idle
   - 有错误
3. 搜索/过滤：
   - 按项目
   - 按 agent 类型
   - 按状态
4. Live Agent Sessions：
   - 按状态分组
   - 每张卡片以项目名为主，不以 PID 为主

详情页或 details 展开区显示：
- cwd
- command
- process tree
- session file
- last_user_message
- recent_output
- pending_items
- git status
- recent files
- logs tail

十、安全要求
必须满足：
- 默认监听 127.0.0.1
- 如果 --host 0.0.0.0，必须要求 token
- 不读取 /proc/<pid>/environ
- 不使用 ptrace
- 不建议修改 ptrace_scope
- 不要求 sudo
- 不保存 SSH 密码
- 没有远程 SSH 功能
- 日志以 text 渲染，防 XSS
- API 只读为主
- stop/kill 功能默认不做，后续再考虑

十一、优先实现顺序
第一阶段：
- 删除/禁用远程 SSH 和凭据管理
- 保留本地 agent 扫描
- 迁移 Codex / Claude session 解析
- UI 能展示本机 Codex / Claude

第二阶段：
- 加 kimi-code 识别
- 加 cwd 项目名提炼
- 加 current_activity
- 加 git status / recent files

第三阶段：
- UI 打磨成项目卡片
- 加状态分组
- 加 details 展开区
- 加 token 认证

请先输出：
1. 从 agent-foreman 借鉴哪些模块
2. 删除哪些模块
3. 新的数据模型
4. 新 API 设计
5. 新 UI 结构
6. 实施步骤

然后开始改代码。
