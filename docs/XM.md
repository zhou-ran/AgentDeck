# AgentStatus 项目 Review 报告

> Review Date: 2026-04-29 | Branch: main | Commit: e7188f7

---

## 1. 项目概览

| 项 | 值 |
|---|---|
| 名称 | AgentStatus (agent-foreman-local) |
| 定位 | 本地 coding agent 监控 Dashboard + CLI 工具 |
| 后端 | Python 3.11+, FastAPI, psutil, click, uvicorn |
| 前端 | React 19, TypeScript, Vite, Tailwind CSS |
| 通信 | SSE (server-sent events), 2s 推送间隔 |
| 存储 | JSON 文件 (无数据库) |
| 后端代码量 | ~3,353 行 Python (含测试) |
| 前端代码量 | ~1,311 行 TypeScript/TSX |
| 测试 | 76 个, 全部通过 (0.28s) |

## 2. 架构评估

### 2.1 整体架构: 8/10

```
CLI (click) ──► task_manager ──► JSON files
                    │
FastAPI app ────────┤
    ├── /api/tasks   (CRUD + plan/step/handoff)
    ├── /api/discover (auto-scan agent processes)
    ├── /api/events   (SSE stream)
    └── static/       (Vite build output)
```

**优点:**
- 分层清晰: models → task_manager → API → CLI, 各层职责单一
- 无外部数据库依赖, 部署简单, 适合单机场景
- SSE 推送替代 polling, 实时性好且开销低
- 前后端分离开发 (`make dev` 同时启动 vite + uvicorn), 构建后合并为单进程

**不足:**
- JSON 文件存储无并发写保护 (仅靠 atomic_write 保证单次写入原子性, 但多个 CLI 进程同时操作同一 task 会丢失更新)
- SSE 每 2s 全量推送所有 task 数据, task 数量增长后会有带宽压力 (应改为增量 diff)
- `_history` 全局 dict 作为进程内 CPU/MEM 历史缓存, 重启丢失

### 2.2 模块划分: 9/10

模块拆分合理, 每个文件行数适中:

| 文件 | 行数 | 职责 |
|------|------|------|
| `cli.py` | 636 | CLI 命令定义 (最大文件, 可接受) |
| `process_scanner.py` | 381 | psutil 进程扫描 + 资源采集 |
| `task_manager.py` | 365 | Task CRUD + 业务逻辑 |
| `security.py` | 260 | 安全工具集 |
| `api/tasks.py` | 225 | REST API 路由 |
| `models.py` | 161 | Pydantic 数据模型 |
| `state_machine.py` | 53 | 状态推断逻辑 |

---

## 3. 代码质量评估

### 3.1 后端代码: 8/10

**做得好的地方:**
- 类型标注完整 (全程使用 `Optional`, `tuple[bool, str]` 等)
- Pydantic model 设计合理, `model_dump_json` / `model_validate_json` 序列化一致
- 异常处理覆盖全面: psutil 的 `NoSuchProcess`, `AccessDenied`, `ZombieProcess` 都有 catch
- `as_dict(attrs=[...])` 白名单读取进程属性, 安全意识好

**需要改进的地方:**

1. **`config.py` 每次调用都重新读 YAML 文件** (L28-L33). `load_config()` 无缓存, 高频调用 (如 SSE 每 2s) 会重复磁盘 I/O. 建议加 TTL 缓存或启动时加载一次.

2. **`task_manager.list_tasks()` 每次遍历目录 + 读所有 JSON + enrich** (L124-L134). 当 task 数量大时性能差. `enrich_task()` 会调用 psutil 获取每个 task 的 CPU/MEM, N 个 task 就是 N 次 psutil 系统调用.

3. **`api/sse.py` L65 `discover_sessions()` 每 2s 全量扫描所有进程**. `psutil.process_iter()` 遍历整个 /proc, 在进程多的服务器上开销大. 建议降低频率 (10-30s) 或做增量.

4. **`cli.py` L43 重复 import**: `from backend.security import is_safe_project_dir, verify_pid_for_task, verify_pid_for_task` — `verify_pid_for_task` 被 import 了两次.

5. **`state_machine.py` `_log_tail()` 读整个文件再截取最后 N 行** (L13-L17). 大日志文件会很慢. `log_manager.py` 有高效的反向 seek 实现, 但 state_machine 没有复用.

6. **`api/tasks.py` L115 `task.status = "completed"` 类型错误**. `task.status` 应该赋值 `TaskStatus.completed` 枚举值, 而非字符串. 虽然 Pydantic 的 `model_dump` 可能兼容, 但语义不正确.

### 3.2 前端代码: 8/10

**做得好的地方:**
- 组件拆分合理, 单一职责 (TaskCard, TaskDetail, FilterBar, etc.)
- `useSSE` hook 自动重连机制 (3s 延迟)
- SparkLine 组件纯 SVG 实现, 无额外依赖
- TypeScript 类型定义与后端 Pydantic model 一一对应

**需要改进的地方:**

1. **`useSSE.ts` L27 `catch {}` 空 catch**. JSON parse 失败时静默吞掉错误, 调试困难. 至少应 `console.warn`.

2. **`TaskDetail.tsx` L29 3s 轮询 + SSE 双重数据源**. 组件内部用 `setInterval(load, 3000)` 拉取 log/tree/freshTask, 同时 SSE 也在推送 task 数据. 两套数据流可能导致 UI 闪烁或数据不一致.

3. **`Dashboard.tsx` L20-L22 选中 task 时直接 return, 丢失整个 Dashboard 状态** (filter, search). 返回时需重新操作 filter. 建议用路由或 overlay 模式.

4. **`client.ts` fetchJson 未传递 auth token**. API 层加了 `require_token()` 依赖, 但前端 `fetchJson` 没有加 `Authorization` header. 非 localhost 访问会 401. (localhost 被豁免所以当前可用, 但 LAN 场景会断)

5. **无错误边界 (Error Boundary)**. 任何组件渲染异常会导致整个白屏.

### 3.3 测试覆盖: 7/10

| 测试文件 | 用例数 | 覆盖模块 |
|----------|--------|----------|
| test_task_store.py | 19 | task_manager CRUD, plan, handoff |
| test_security.py | 16 | path validation, task_id, atomic_write, rate limiter |
| test_state_machine.py | 11 | status inference, error detection |
| test_log_tail.py | 8 | log reading, size, mtime |
| test_process_scanner.py | 5 | PID alive check, elapsed format |
| **总计** | **76** | |

**缺失的测试:**
- 无 API 层测试 (FastAPI TestClient)
- 无 SSE 端点测试
- 无 CLI 集成测试 (click.testing.CliRunner)
- 无前端测试 (无 vitest/jest 配置)
- `process_scanner.discover_sessions()` / `discover_agent_processes()` 未测试
- `git_utils.py` 未测试
- `systemd.py` 未测试

---

## 4. 安全评估: 9/10

安全方面做得**非常好**, 有独立的 `SECURITY.md` 威胁模型文档.

### 已实施的安全措施

| 措施 | 状态 | 说明 |
|------|------|------|
| 默认绑定 localhost | ✅ | `127.0.0.1`, 非 localhost 打印警告 |
| Token 认证 | ✅ | Bearer token, 非 localhost 强制 |
| CORS 限制 | ✅ | 仅允许 localhost origin |
| 安全响应头 | ✅ | CSP, X-Frame-Options, X-Content-Type-Options 等 |
| Path traversal 防护 | ✅ | task_id 正则 + path validation |
| Symlink 检测 | ✅ | project_dir 拒绝 symlink |
| 敏感目录拦截 | ✅ | /etc, /proc, /sys, /dev, /boot, /root |
| PID 验证 | ✅ | kill 前检查 command + CWD |
| 环境变量保护 | ✅ | 不读 /proc/pid/environ |
| 原子写入 | ✅ | temp file + os.replace |
| 输入清理 | ✅ | note 截断 + null byte 过滤 |
| Rate limiting | ✅ | 120 req/min per IP |

### 残留风险

1. **Localhost 无认证**: 共享服务器上任何本地用户可访问 dashboard. 建议支持 Unix socket + 文件权限.
2. **Token 明文存储**: `config.yaml` 中 token 未加密. 建议支持 keyring 或 env-only 模式.
3. **Rate limiter 内存泄漏**: `RateLimiter._requests` 字典只在 `cleanup()` 时清理, 但没有定时调用 `cleanup()`. 长期运行会积累大量 stale key.
4. **CSP `unsafe-inline`**: script-src 和 style-src 允许 inline, 削弱了 XSS 防护. (Vite 默认 inline style, 实际限制较大)

---

## 5. 功能完整度评估

### 5.1 核心功能: 9/10

| 功能 | 状态 | 说明 |
|------|------|------|
| 启动 agent 任务 | ✅ | `start` 命令, subprocess + 日志重定向 |
| 任务列表/详情 | ✅ | CLI + Web UI |
| 进程树可视化 | ✅ | 递归展示父子进程 |
| 实时日志 | ✅ | LogViewer + error 高亮 |
| CPU/MEM 监控 | ✅ | 进程级 + 系统级, SparkLine 图表 |
| 状态自动推断 | ✅ | running/idle/completed/failed |
| Plan/Step 管理 | ✅ | import plan, update step status |
| 任务 Handoff | ✅ | 生成 handoff markdown 文本 |
| 进程自动发现 | ✅ | 扫描 codex/claude/aider/gemini 等 |
| Import PID | ✅ | 导入已有进程为 managed task |
| systemd 服务 | ✅ | 生成 + 安装 user service |
| 状态过滤/搜索 | ✅ | FilterBar 多维过滤 |
| 系统概览 | ✅ | CPU/MEM/Disk/Network 指标 |

### 5.2 缺失 / 可增强

1. **无任务编辑功能**: 创建后无法修改 name, goal, command 等
2. **无批量操作**: 无法批量 stop/complete 多个 task
3. **无历史趋势**: CPU/MEM history 仅保留 60s, 无持久化长期趋势
4. **无通知机制**: task 完成/失败时无 webhook/email/桌面通知
5. **无日志搜索**: LogViewer 仅展示, 无 grep/filter 功能
6. **无导出功能**: 无法导出 task 报告 (JSON/CSV)
7. **无多用户支持**: 单用户设计, 无法区分不同用户的 task
8. **无 Docker 部署**: 无 Dockerfile

---

## 6. 工程实践评估

### 6.1 构建与部署: 8/10

- `Makefile` 提供完整工作流 (install, dev, test, build-frontend, clean)
- `pyproject.toml` 规范, 入口点定义清晰
- Vite build 输出到 `backend/static/`, FastAPI 直接 serve, 单进程部署
- systemd user service 支持开机自启

### 6.2 文档: 8/10

- `CLAUDE.md`: 完整的架构文档 + 命令参考 (给 AI agent 看的)
- `SECURITY.md`: 详细威胁模型 + 已修复问题清单
- `README.md`: 存在 (未详细 review)
- `config.example.yaml`: 配置示例

### 6.3 Git 历史: 8/10

8 个 commit, 消息清晰:
```
e7188f7 Production polish: CLI rename, Makefile, UI filters, systemd, tests
4dc69a2 Security hardening: localhost default, token auth, path validation, PID verification
ae5ce55 feat: auto-discover existing agent processes
e70d89b merge: dev into main
6efc96d docs: update CLAUDE.md with new CLI commands and architecture
9f1ceab feat: upgrade to Agent Foreman style task workflow management
8c279d4 feat: AgentStatus MVP — agent supervisor dashboard
2da672c Initial commit: AgentStatus project
```

---

## 7. 关键问题清单 (按优先级)

### P0 — 必须修复

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| 1 | `task.status = "completed"` 类型错误 | `api/tasks.py:115` | 应为 `TaskStatus.completed` |
| 2 | Rate limiter 无自动 cleanup | `security.py:250` | `_requests` 字典只增不清, 长期内存泄漏 |

### P1 — 强烈建议

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| 3 | `config.load_config()` 无缓存 | `config.py:28` | 每次调用读磁盘, SSE 高频触发 |
| 4 | `state_machine._log_tail()` 读全文件 | `state_machine.py:13` | 大日志性能差, 应复用 `log_manager.get_log_tail` |
| 5 | SSE `discover_sessions()` 每 2s 全量扫描 | `api/sse.py:65` | 降频或增量 |
| 6 | 前端未传递 auth token | `frontend/src/api/client.ts` | LAN 场景会 401 |
| 7 | `cli.py` 重复 import | `cli.py:43` | `verify_pid_for_task` 重复 |
| 8 | SSE catch 空吞错误 | `frontend/src/hooks/useSSE.ts:27` | 至少 console.warn |

### P2 — 改善建议

| # | 问题 | 说明 |
|---|------|------|
| 9 | SSE 全量推送 → 增量 diff | task 数量增长后带宽压力 |
| 10 | 无 API 层测试 | FastAPI TestClient 覆盖 |
| 11 | 无前端测试 | vitest 配置 |
| 12 | TaskDetail 双重数据源 (polling + SSE) | 统一为 SSE 单一数据源 |
| 13 | Dashboard 选中 task 丢失 filter 状态 | 改用 overlay/route |
| 14 | 无 Error Boundary | 组件异常导致白屏 |
| 15 | 无 Docker 部署 | 添加 Dockerfile |

---

## 8. 总评

| 维度 | 评分 (1-10) | 说明 |
|------|-------------|------|
| 架构设计 | 8 | 分层清晰, 技术选型合理 |
| 代码质量 | 8 | 类型安全, 异常处理完善 |
| 安全性 | 9 | 威胁模型完整, 防护措施到位 |
| 功能完整度 | 9 | 核心功能齐全, 覆盖 agent 监控全流程 |
| 测试覆盖 | 7 | 后端单元测试扎实, 缺 API/前端测试 |
| 文档 | 8 | CLAUDE.md + SECURITY.md 质量高 |
| 工程实践 | 8 | Makefile, pyproject.toml, systemd 完整 |
| **综合** | **8.1** | 生产可用的单机 agent 监控工具 |

### 一句话总结

一个完成度很高的本地 agent 监控工具, 安全意识突出 (有独立威胁模型文档), 代码结构清晰, 核心功能齐全. 主要短板在测试覆盖 (缺 API/前端测试) 和性能优化 (SSE 全量推送, config 无缓存). 作为单机小规模使用已经足够, 向多用户/大规模演进需要引入数据库和增量推送.
