# AgentDeck Git Push 操作指南 ⚠️

> **必读**：在执行 `git push` 之前，请完整阅读本指南并完成底部的确认清单。

---

## 1. 本次变更摘要

- **项目名称**：AgentStatus → AgentDeck
- **CLI 命令**：`agent-foreman-local` → `agentdeck`；`agentctl` 保留为兼容别名
- **配置目录**：`~/.agent_foreman_local` → `~/.agentdeck`
- **PyPI/包名**：`agentstatus` → `agentdeck`
- **前端包名**：`agentstatus-frontend` → `agentdeck-frontend`
- **本地文档**：`docs/` 与 `CLAUDE.md` 已从当前 git 跟踪中排除，并加入 `.gitignore`

---

## 2. 敏感信息检查结果

### 2.1 未发现严重敏感信息 ✅
- 未检测到硬编码的 API Key、Password、Token、私钥或证书文件。
- 代码中的 Token 逻辑为运行时动态生成（`secrets.token_urlsafe`），无硬编码凭证。

### 2.2 发现低风险敏感信息 ⚠️
- **docs/ 目录中的设计文档** 包含本地文件路径信息，例如：
  - `/data/zhouran/agents/projects/01.PreCancerAtlas_A`
  - 个人工作目录结构和项目名称
- **docs/ 中的 prompts 文件** 包含内部设计思路与需求描述。
- **git 提交历史中的作者信息** 包含邮箱（`ranzhou1005@gmail.com`）。

### 2.3 已采取的脱敏措施
- `docs/` 与 `CLAUDE.md` 已从当前 git 索引中移除（`git rm --cached -r docs/ CLAUDE.md`）。
- `docs/` 与 `CLAUDE.md` 已加入 `.gitignore`，未来不会被意外提交。
- 旧 build 产物已清理，前端已重新构建并更新到 `backend/static/`。

---

## 3. 剩余风险与可选清理

### 风险：git 历史中仍保留本地文档内容
虽然 `docs/` 与 `CLAUDE.md` 已从**当前工作树**的跟踪中移除，但由于 Git 的历史回溯机制，这些文件仍然存在于**历史提交记录**中。推送到公共仓库后，任何人仍可通过 `git log --all --full-history -- docs/ CLAUDE.md` 查看历史版本。

### 可选方案 A：接受当前状态（推荐，如果 docs 内容不涉密）
如果本地路径和项目设计文档不属于高度敏感信息，可直接 push。`.gitignore` 已确保未来不再跟踪 `docs/` 与 `CLAUDE.md`。

### 可选方案 B：彻底清除历史中的 docs（如果要求严格脱敏）
若需从**整个 git 历史**中抹除 docs 目录，需重写历史。操作前请确保已备份仓库。

```bash
# 方法：使用 git-filter-repo（需先安装）
# pip install git-filter-repo
# 然后执行：
git filter-repo --path docs/ --path CLAUDE.md --invert-paths

# 或使用 BFG Repo-Cleaner：
# java -jar bfg.jar --delete-folders docs
# git reflog expire --expire=now --all
# git gc --prune=now --aggressive
```

> ⚠️ **警告**：重写历史会改变所有 commit hash，若本仓库已有协作分支或标签，此操作具有破坏性。

---

## 4. 最终确认清单

在运行 `git push` 之前，请逐项勾选确认：

- [ ] 我已阅读本指南并理解剩余风险。
- [ ] 我确认 `docs/` 与 `CLAUDE.md` 的历史内容可以保留在 git 历史中，或我已执行历史重写。
- [ ] 我确认代码中无硬编码的密码、API Key、Token 等凭证。
- [ ] 我已检查 `.gitignore` 确保不需要的文件（`docs/`、`CLAUDE.md`、`tmp/`、`node_modules/`、`__pycache__/` 等）未被跟踪。
- [ ] 我确认远程仓库地址正确：`git@github.com:zhou-ran/AgentDeck.git`
- [ ] 我拥有该 GitHub 仓库的 SSH 写入权限。

---

## 5. 推荐的 push 命令

确认以上清单后，执行：

```bash
# 若尚未添加远程仓库
git remote add origin git@github.com:zhou-ran/AgentDeck.git

# 确保在 main 分支
git branch -M main

# 推送（首次需 -u 设置上游）
git push -u origin main
```

---

## 6. 推送后验证

```bash
# 检查远程分支
git branch -vv

# 检查 GitHub 仓库文件列表（不应包含 docs/）
# 访问：https://github.com/zhou-ran/AgentDeck
```

---

*本指南由 AgentDeck 重命名与推送前的安全检查流程生成。*
*生成时间：2026-04-29*
