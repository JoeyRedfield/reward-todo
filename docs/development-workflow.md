# 开发工作流

这份仓库建议把 `main` 视为只读同步分支。

- `main` 只做同步远端、查看状态、更新基线。
- 日常开发一律放到 feature branch。
- 推荐每个 feature branch 使用独立 worktree，避免把实验性改动带回主工作区。

## 一次性本地配置

首次进入仓库时，先确认本地 Git 策略：

```bash
git config pull.ff only
git config fetch.prune true
```

含义：

- `git pull` 只允许 fast-forward；如果本地 `main` 已经偏离远端，会直接报错，不会悄悄制造 merge commit。
- `git fetch` 时自动清理远端已经删除的引用，减少脏状态。

## `main` 的使用规则

在主工作区内，`main` 只做下面这组动作：

```bash
git switch main
git fetch origin --prune
git pull --ff-only origin main
git status --short --branch
```

不要在 `main` 上直接：

- 写代码
- 提交 commit
- 合并其他分支
- 临时 stash 一堆未完成改动长期挂着

如果 `git pull --ff-only` 失败，先停下来查分叉原因，不要改成普通 `git pull` 硬拉。

## 新功能开发

推荐从最新的 `origin/main` 创建独立 worktree：

```bash
git fetch origin --prune
git worktree add ~/.config/superpowers/worktrees/reward-todo/<branch-name> -b <branch-name> origin/main
```

例如：

```bash
git worktree add ~/.config/superpowers/worktrees/reward-todo/codex/issue-3-foo -b codex/issue-3-foo origin/main
```

进入该目录后再安装依赖、启动服务、写代码、跑测试。

如果你不想用 worktree，至少也要保证：

- 从最新 `origin/main` 切出 feature branch
- 不在 `main` 上直接开发

## 功能分支收尾

功能分支合并后，回到主工作区同步 `main`：

```bash
git switch main
git fetch origin --prune
git pull --ff-only origin main
```

如果对应 worktree 已不再需要，再执行清理：

```bash
git worktree remove ~/.config/superpowers/worktrees/reward-todo/<branch-name>
git branch -d <branch-name>
git worktree prune
```

## 快速自检

当你怀疑工作区又脏了，先看这三条：

```bash
git status --short --branch
git rev-list --left-right --count main...origin/main
git worktree list
```

判断方式：

- `git status --short --branch` 只有 `## main...origin/main`，说明主工作区没有未提交改动。
- `git rev-list --left-right --count main...origin/main` 返回 `0 0`，说明本地 `main` 和远端没有分叉。
- `git worktree list` 里如果出现 `prunable`，说明有陈旧 worktree 记录，执行 `git worktree prune`。

## 这套规则的目标

核心不是“命令更漂亮”，而是把两类问题直接挡掉：

- 本地 `main` 混入未提交改动，影响后续开发和拉取
- `main` 在不知情的情况下与 `origin/main` 分叉
