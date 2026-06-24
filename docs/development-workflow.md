# 开发工作流

这份仓库使用单人开发的轻量 Git 流程，核心只有一条：不要直接在 `main` 上开发。

- `main` 只做同步远端、查看状态、更新基线。
- 日常开发一律放到 feature branch。
- `git worktree` 是可选项，不是默认要求。

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
- 临时 stash 一堆未完成改动长期挂着

如果 `git pull --ff-only` 失败，先停下来查分叉原因，不要改成普通 `git pull` 硬拉。

## 新功能开发

单人开发默认这样做就够了：

```bash
git switch main
git fetch origin --prune
git pull --ff-only origin main
git switch -c <branch-name>
```

例如：

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/today-copy-tweak
```

然后就在这个分支里写代码、跑测试、提交。

## 合回 `main`

功能完成后，回到 `main` 合并：

```bash
git switch main
git pull --ff-only origin main
git merge --ff-only <branch-name>
git branch -d <branch-name>
```

如果 `git merge --ff-only` 失败，说明 `main` 已经前进，先把你的 feature branch 同步到最新 `main`，再继续处理。

## 什么时候才需要 worktree

大多数单人开发场景不需要 `git worktree`。

只有在下面这些情况，才建议使用：

- 你要并行处理两个以上任务，而且不想来回 stash / 切分支
- 你需要同时保留两个独立运行中的工作目录
- 某个任务会生成很多本地环境产物，你不想污染当前工作目录

需要时再创建：

```bash
git fetch origin --prune
git worktree add ~/.config/superpowers/worktrees/reward-todo/<branch-name> -b <branch-name> origin/main
```

不需要时，完全可以只用普通 feature branch。

## 功能分支收尾

如果你使用的是普通 feature branch，到这里其实已经结束了。

如果你使用了 worktree，合并后再做清理：

```bash
git worktree remove ~/.config/superpowers/worktrees/reward-todo/<branch-name>
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
- `git worktree list` 里如果出现 `prunable`，说明有陈旧 worktree 记录；只有你确实在使用 worktree 时才需要关心它。

## 这套规则的目标

核心不是“命令更漂亮”，而是把两类问题直接挡掉：

- 本地 `main` 混入未提交改动，影响后续开发和拉取
- `main` 在不知情的情况下与 `origin/main` 分叉
