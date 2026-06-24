# AGENTS.md

本文件约束在本仓库内工作的 AI agent 的默认行为。

## 回复语言

- 默认使用中文回复。

## 删除文件

- 需要删除文件时，必须先征求用户同意。

## Git 工作流硬规则

- `main` 是只读同步分支，不是日常开发分支。
- 禁止在 `main` 上直接修改代码、提交 commit、长期保留未提交改动。
- 开始任何实现类任务前，必须先确认自己当前不在脏的 `main` 工作区上开发。
- 日常开发必须在 feature branch 上进行。
- 默认先从当前最新的 `main` 或 `origin/main` 切出 feature branch，再开始改动。
- `git worktree` 是可选工具，只在需要并行处理多个任务或隔离运行环境时再使用。
- 只有在以下场景才允许停留在 `main`：同步远端、查看状态、做只读检查、更新基线。

## 开工前检查

开始改动前，agent 必须先执行并检查这组命令：

```bash
git status --short --branch
git fetch origin --prune
git rev-list --left-right --count main...origin/main
```

必须满足：

- 当前要么不在 `main`，要么 `main` 工作区完全干净
- 如果当前在 `main`，则本地 `main` 不得领先或落后 `origin/main`

如果不满足这些条件，先整理工作区或切到新的 feature branch，再继续。

## `main` 上允许的操作

如果当前位于主工作区的 `main`，只允许执行这组同步命令：

```bash
git switch main
git fetch origin --prune
git pull --ff-only origin main
git status --short --branch
```

- 如果 `git pull --ff-only` 失败，不要改用普通 `git pull`、`merge` 或其他会制造分叉的方式硬拉。
- 遇到分叉或脏状态，先向用户说明，再处理。

## 实现任务的默认起手式

除非用户明确要求直接在当前分支操作，否则实现任务默认按下面顺序开始：

1. 同步 `origin/main`
2. 创建 feature branch
3. 在 feature branch 中进行修改和验证

如果任务需要并行开发多个分支、保留多个运行中的工作目录，或避免不同任务之间互相污染，再考虑为 feature branch 创建独立 worktree。

建议遵循的详细操作见 [`docs/development-workflow.md`](/Users/wuzhuoyi/Desktop/code/reward-todo/docs/development-workflow.md)。
