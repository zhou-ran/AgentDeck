# AgentStatus 自动发现重构计划

## Summary

将当前以 `Tasks / Import PID` 为主的监控器，重构为默认展示 `Live Agent Sessions` 的本地 Coding Agent Foreman。核心目标是按项目聚合正在运行的 Codex、Claude Code、kimi-code、aider、gemini 等 agent，显示当前活动、原始用户指令、项目状态、进程树、日志和资源占用。

## Key Changes

- 扩展后端数据模型：新增 `AgentSession`、`ProjectNameInfo`、`InstructionInfo`、`ProjectRuntimeStatus`、`ActivityTimelineItem`，并扩展状态枚举为 `busy/testing/editing/searching/git_ops/running_script/waiting/idle/completed/failed/unknown`。
- 重构 scanner：`scan_agent_sessions()` 以 root agent 进程为单位发现 session，node/python/bash 等仅作为 agent 子进程归入 session。
- 增加项目名提炼：支持 cwd、git root、`/projects/<name>`、`01.PreCancerAtlas_A` 工作区格式，生成面向 UI 的短路径。
- 增加活动识别：根据测试、git、搜索、脚本、文件修改、日志、CPU 和等待提示推断 `current_activity`、`status`、`status_reason`。
- 增加用户指令提取：扫描 Codex/Claude/kimi 项目级和用户级 session/log/transcript 文件、`~/agent_logs`、进程参数；找不到时显示“未找到原始指令”，不臆测。
- 增加项目运行状态：只读 git 状态、dirty 文件、最近修改文件、测试/服务进程、错误提示和最后活动时间。
- 保留 `import-pid` 作为高级功能，新增 `agentctl run` 用于稳定记录 instruction、日志和 task metadata。

## API / UI Changes

- `/api/discover` 和 SSE 的 `discovered` 返回增强后的 live session schema。
- 首页标题改为 `Local Coding Agent Foreman`，主区域改为 `Live Agent Sessions`。
- session 卡片突出项目名、agent 类型、状态、workspace、运行时长、current_activity、user_instruction、git dirty、最近文件、测试/错误提示、PID/children/CPU/MEM。
- 新增 session 详情页，包含 Overview、User Instruction、Process Tree、Project Status、Live Logs、Activity Timeline。
- Managed Tasks 保留在次要区域；Import PID API 保留但不再作为首页主流程。

## Test Plan

- 后端测试覆盖项目名提炼、activity inference、instruction extraction、状态推断和原有 API/task/security 行为。
- 前端运行 TypeScript + Vite build，验证新类型、session 卡片和详情页可编译。
- 保持安全约束：不使用 sudo/ptrace，不读取 `/proc/<pid>/environ`，git 命令使用白名单、`shell=False`、timeout，日志以纯文本渲染。
