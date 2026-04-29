# AgentStatus 代码审查报告

> 分支：`main`  
> 时间：2026-04-29  
> 提交：`e7188f7` Production polish: CLI rename, Makefile, UI filters, systemd, tests

---

## 1. 项目概述

**AgentStatus**（PyPI 名 `agentstatus`）是一个本地编码代理监控工具，提供：
- **CLI** (`agent-foreman-local` / `agentctl`)：启动、停止、追踪任务
- **Web Dashboard**：React 19 + FastAPI + SSE 实时推送
- **进程自动发现**：基于 `psutil` 扫描已知代理关键词
- **计划与交接**：支持任务计划步骤、进度笔记、交接文本生成

### 技术栈

| 层 | 技术 | 文件数 |
|---|---|---|
| 后端 | Python 3.11+, FastAPI, click, psutil, Pydantic | 17 |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS | ~17 |
| 测试 | pytest | 5 文件，76 用例 |

---

## 2. 亮点（做得好的地方）

### 2.1 安全优先的设计

- **默认绑定 127.0.0.1**，LAN 访问需显式 `--host 0.0.0.0` + Bearer Token
- **路径穿越防护**：`is_safe_project_dir` / `is_safe_log_path` 拒绝 `..`、符号链接、敏感目录（`/etc`, `/proc` 等）
- **PID 核查再杀进程**：`verify_pid_for_task` 比对命令行和 CWD，防止误杀/ PID 复用攻击
- **只读 Git 白名单**：`ALLOWED_GIT_COMMANDS = {"status", "diff", "log", "show"}`，禁止危险操作
- **速率限制**：滑动窗口内存限流器（120 req/60s）
- **原子写**：`atomic_write` 使用临时文件 + `os.replace`，防止 JSON 状态文件写坏
- **CSP / CORS / Security Headers**：生产环境有完整的安全头中间件

### 2.2 架构清晰

- API / 业务逻辑 / 扫描 / 安全 / CLI 分层明确，模块职责单一
- `models.py` 中 Pydantic 模型定义完整，前后端类型可对照
- 进程状态采用**读取时推断**（`enrich_task`），没有额外的后台守护线程，简单可靠

### 2.3 用户体验细节

- SSE 每 2 秒推送任务列表 + 系统指标 + 自动发现的代理会话，前端实时刷新
- CPU/MEM 历史使用环形缓冲区（`deque(maxlen=35)`），前端渲染 SparkLine SVG 迷你图
- `handoff` 命令生成 Markdown 格式的交接文档，包含计划进度、变更文件、风险点
- 支持 `import-pid` 将已运行的进程纳入管理，无需重启
- `make install` / `make dev` / `systemd` 用户服务一键安装，部署体验流畅

### 2.4 测试质量

- `conftest.py` 的 `isolated_config` (autouse)  fixture 非常到位：所有测试在临时目录运行，零污染
- 参数化测试覆盖了 `task_id` 正则的 6 种合法和 8 种非法输入
- 负面测试充分：路径穿越、符号链接、权限错误、文件缺失、原子写失败清理

---

## 3. 代码缺陷（Bug / 隐患）

### 3.1 已确认的代码问题

| # | 位置 | 问题 | 严重度 |
|---|---|---|---|
| 1 | `backend/cli.py:43` | `verify_pid_for_task` **重复 import** | 🔴 低 |
| 2 | `backend/process_scanner.py:330-346` | 磁盘使用去重逻辑错误：`seen_mounts` 跟踪的是 `project_dirs` 字符串而非实际挂载点。若两个项目目录在同一文件系统，磁盘用量会被**重复计算** | 🟡 中 |
| 3 | `backend/state_machine.py:12-17` | `_log_tail` 读取**整个日志文件**再取最后 50 行。与 `log_manager.py` 的高效 chunked seek 形成鲜明对比，大日志（GB 级）会严重拖慢状态推断 | 🟡 中 |
| 4 | `frontend/src/api/client.ts` | API 请求**未携带 `Authorization: Bearer` 头**。后端 auth 中间件在非 localhost 下要求 Token，导致前端在 LAN 部署场景直接 **401 不可用** | 🔴 高 |
| 5 | `frontend/src/hooks/useSSE.ts:27` | `catch {}` 静默吞掉 SSE JSON 解析错误，排障困难 | 🟡 中 |
| 6 | `frontend/src/components/TaskDetail.tsx:15-36` | 3 秒轮询 `api.getTask` 与父级 SSE 推送存在**竞争条件**：轮询返回的旧数据可能覆盖 SSE 的新数据 | 🟡 中 |
| 7 | `frontend/src/components/TaskDetail.tsx` | 组件卸载时， inflight 的 `Promise.all` 仍可能调用 `setState`，无 abort controller / mounted flag | 🟡 中 |
| 8 | `frontend/package.json` | `react-router-dom` 列为依赖但**项目中零引用**，是死依赖 | 🟢 低 |
| 9 | `backend/main.py` | CORS `allow_origins` 硬编码 `127.0.0.1:9797`、`localhost:9797`，若用户自定义端口则浏览器 CORS 失败 | 🟡 中 |
| 10 | `backend/api/sse.py` | 直接导入 `task_manager._log_path` 和 `process_scanner` 的私有 `_history`、`_prev_net`，破坏模块封装 | 🟢 低 |
| 11 | `backend/task_manager.py:332-338` | `import_pid` 内部局部导入 `get_process_info`，应为模块顶部导入 | 🟢 低 |

### 3.2 潜在运行时问题

- **日志句柄未显式关闭**：`cli.py:start` 中 `open(log_path, "w")` 传递给 `subprocess.Popen`，虽然子进程继承不算泄漏，但父进程侧无显式关闭，略为脆弱
- **无进程收割**：僵尸进程或孤儿进程若未被 `enrich_task` 读取到，会长期以旧状态留在列表中（纯读取驱动架构的固有限制）
- **`tail -f` 不支持日志轮转**：CLI 的 `tail --follow` 是简单的 `sleep(0.3)` 轮询，日志文件被 rotate 后不会自动跟踪新文件
- **RateLimiter 内存无限增长**：`_requests` dict 只在 `cleanup()` 时修剪，但 `cleanup` 从未被调用（FastAPI 生命周期未接入）

---

## 4. 测试覆盖分析

### 4.1 已覆盖模块（较充分）

| 模块 | 测试文件 | 覆盖要点 |
|---|---|---|
| `security.py` | `test_security.py` | task_id 正则、路径安全、原子写、note 清洗、速率限制 |
| `task_manager.py` | `test_task_store.py` | CRUD、plan/steps、progress notes、complete/fail、handoff |
| `state_machine.py` | `test_state_machine.py` | 状态推断、error hint 检测 |
| `log_manager.py` | `test_log_tail.py` | tail、size、mtime |
| `process_scanner.py` | `test_process_scanner.py` | `is_process_alive`、`_format_elapsed` |

**当前状态：76 / 76 测试通过 ✅**

### 4.2 未覆盖模块（重大缺口）

| 模块 | 大小 | 影响 |
|---|---|---|
| `backend/api/tasks.py` | ~7 KB | **核心 REST API**：创建、停止、tail、notes、logs、process-tree 端点 — **零测试** |
| `backend/api/processes.py` | ~1.4 KB | 自动发现端点 — **零测试** |
| `backend/api/sse.py` | ~3 KB | SSE 流 — **零测试** |
| `backend/api/auth.py` | ~1.1 KB | Token 认证、localhost 绕过 — **零测试** |
| `backend/main.py` | ~4 KB | FastAPI 工厂、CORS、静态文件、安全头 — **零测试** |
| `backend/cli.py` | ~21 KB | **最大文件**，全部 CLI 命令 — **零测试** |
| `backend/config.py` | ~1.8 KB | YAML 解析、Token 生成 — **零测试** |
| `backend/git_utils.py` | ~3.4 KB | Git 变更检测 — **零测试** |
| `backend/systemd.py` | ~3.2 KB | systemd 服务安装 — **零测试** |

### 4.3 关键测试缺口说明

- **无 API/HTTP 集成测试**：`httpx` 已列为 dev 依赖但未被使用。应使用 `fastapi.testclient.TestClient` 覆盖所有端点，尤其是认证流程和 PID 操作
- **无 CLI 测试**：click 提供 `CliRunner`，可对所有命令做单元测试（尤其是 `start`、`stop`、`discover`、`import-pid`）
- **无 async 测试**：`log_manager.tail_log`（async generator）和 `sse.py` 需要 `pytest-asyncio`
- **RateLimiter 滑动窗口过期未测**：只测了限流触发，未验证窗口到期后自动放行

---

## 5. 前端架构评估

### 5.1 状态管理

- **零外部状态库**，纯 React `useState` / `useMemo`
- SSE 作为单一真实数据源向下传递，数据流单向，理解成本低
- 副作用：缺少全局缓存失效机制，每次操作后需手动刷新或依赖 SSE 延迟推送

### 5.2 数据获取双轨制

| 模式 | 用途 | 问题 |
|---|---|---|
| SSE `/api/events` | 任务列表、系统指标、发现会话 | 实时，但 2s 间隔 |
| REST 轮询 | TaskDetail 的 logs / process-tree / task | 3s 间隔，与 SSE 重叠冗余 |

**建议**：TaskDetail 的 `task` 数据可直接来自 SSE，无需 3s 轮询；logs 和 process-tree 可保留轮询或改为 SSE 子频道

### 5.3 健壮性

- **无 Error Boundary**：任何组件抛异常会导致整棵树卸载
- **无 Loading 状态**：数据加载期间显示空白/"No tasks yet"
- **无 ARIA / 焦点管理**：视图切换后焦点未重置，可访问性不足

---

## 6. 建议与优先级

### P0（尽快修复）

1. **前端 API client 添加 Bearer Token**：从 `localStorage` 或 URL query 读取 token，附加到所有请求头，否则 LAN 部署不可用
2. **修复磁盘使用去重 bug**：`seen_mounts` 应记录 `psutil.disk_usage(d).device` 或实际挂载点
3. **修复 `_log_tail` 性能问题**：复用 `log_manager.get_log_tail` 的 chunked seek 实现

### P1（近期优化）

4. **增加 FastAPI 集成测试**：用 `TestClient` 覆盖所有 `/api/*` 端点，重点测试 auth 和 task 生命周期
5. **增加 CLI 单元测试**：用 `click.testing.CliRunner` 覆盖 `start`、`stop`、`tail`、`discover` 等核心命令
6. **消除 TaskDetail 竞争条件**：使用 `AbortController` 或 `mounted` 标志，并考虑让 `taskData` 以 SSE 为准、仅轮询 logs/process-tree
7. **接入 RateLimiter cleanup**：在 FastAPI lifespan 中定时调用 `api_rate_limiter.cleanup()`，防止内存泄漏
8. **移除 react-router-dom 死依赖**

### P2（长期改进）

9. **增加 React Error Boundary** + Loading skeletons
10. **支持日志轮转**：`tail -f` 检测 inode 变化并重新打开文件
11. **CORS 动态配置**：从后端配置读取实际绑定端口，避免硬编码
12. **模块化 SSE**：将 log metadata 和 history 的获取封装到公开 API，避免跨模块访问私有变量

---

## 7. 总体评价

AgentStatus 是一个**设计用心、安全考虑周全、部署体验流畅**的本地监控工具。后端模块划分合理，安全机制（路径检查、PID 核查、原子写、Token 认证）层层到位；前端 SSE 实时推送 + SparkLine 历史图提供了良好的可视化体验。

主要短板在于**测试覆盖不均衡**：底层工具函数测试充分，但 API 层、CLI、配置加载、Git 集成等核心业务路径完全缺乏自动化验证。此外前端在认证头、竞争条件、错误处理上有若干可用性和健壮性问题。

**综合评级：B+** — 架构优良、安全扎实，补齐 API/CLI 测试并修复前端 Token 和竞争条件后可到 A。
