# Today Reopen Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `/today` 页面补齐“撤销已完成”交互，让用户可以在当前列表中把误完成的任务恢复为未完成，并同步刷新奖励汇总。

**Architecture:** 继续复用后端现有 `reopen_daily_task` HTTP 能力，不新增后端业务规则；前端把完成与撤销统一收口到 `useTodayBoard`，由列表组件按任务状态渲染对称操作；页面刷新仍通过重新拉取当日任务和奖励汇总实现，保持和现有完成流程一致。

**Tech Stack:** FastAPI API, React 18, Vitest, Testing Library

---

## File Structure

**Frontend ownership**
- Modify: `frontend/src/api/client.js`
  - 新增 `reopenDailyTask`
- Modify: `frontend/src/api/client.test.js`
  - 覆盖 reopen 请求方法与路径
- Modify: `frontend/src/hooks/useTodayBoard.js`
  - 统一管理完成/撤销中的请求状态与刷新逻辑
- Modify: `frontend/src/components/DailyTaskList.jsx`
  - 为已完成任务渲染撤销按钮与处理中状态
- Modify: `frontend/src/pages/Today.jsx`
  - 透传撤销动作与状态
- Modify: `frontend/src/pages/Today.test.jsx`
  - 覆盖撤销成功、奖励汇总刷新、失败反馈
- Modify: `frontend/src/App.test.jsx`
  - 同步 API mock，避免集成测试 mock 断裂

**Verification**
- Run: `cd frontend && npm test -- --run src/api/client.test.js src/pages/Today.test.jsx src/App.test.jsx`
- Run: `cd frontend && npm test -- --run`
- Run: `cd backend && /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest`

### Task 1: 先写 API 与 Today 页测试，锁定 reopen 行为

**Files:**
- Modify: `frontend/src/api/client.test.js`
- Modify: `frontend/src/pages/Today.test.jsx`
- Modify: `frontend/src/App.test.jsx`
- Test: `frontend/src/api/client.test.js`
- Test: `frontend/src/pages/Today.test.jsx`

- [x] **Step 1: 为 client 测试补上 reopen 场景**

```javascript
test("reopens a completed task with POST request", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ id: 1, status: "pending" }),
  });

  await reopenDailyTask(1);

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/daily-tasks/1/reopen",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
    })
  );
});
```

- [x] **Step 2: 为 Today 页面写失败测试，定义已完成任务显示撤销入口**

```javascript
test("shows reopen action for completed tasks", async () => {
  fetchDailyTasksMock.mockResolvedValue([
    { ...task, status: "completed", actual_duration_minutes: 28, completed_at: "2026-06-21T10:00:00Z" },
  ]);

  render(<TodayPage />);

  expect(await screen.findByRole("button", { name: "撤销完成" })).toBeInTheDocument();
});
```

- [x] **Step 3: 为 Today 页面写失败测试，定义撤销成功后列表和奖励汇总刷新**

```javascript
test("reopens a task and refreshes board", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([{ ...task, status: "completed", actual_duration_minutes: 28, completed_at: "2026-06-21T10:00:00Z" }])
    .mockResolvedValueOnce([task]);
  fetchRewardSummaryMock
    .mockResolvedValueOnce({ current_balance: 2000, today_earned: 2000 })
    .mockResolvedValueOnce({ current_balance: 0, today_earned: 0 });
  reopenDailyTaskMock.mockResolvedValue({ ...task, status: "pending", actual_duration_minutes: null, completed_at: null });

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "撤销完成" }));

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "完成" })).toBeInTheDocument();
  });
});
```

- [x] **Step 4: 为 Today 页面写失败测试，定义撤销失败时保留错误提示**

```javascript
test("shows error when reopen fails", async () => {
  fetchDailyTasksMock.mockResolvedValue([
    { ...task, status: "completed", actual_duration_minutes: 28, completed_at: "2026-06-21T10:00:00Z" },
  ]);
  reopenDailyTaskMock.mockRejectedValue(new Error("撤销失败"));

  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "撤销完成" }));

  expect(await screen.findByText("撤销失败")).toBeInTheDocument();
});
```

- [x] **Step 5: 运行定向前端测试，确认当前为红灯**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-1-reopen-today-task/frontend && npm test -- --run src/api/client.test.js src/pages/Today.test.jsx src/App.test.jsx`
Expected: 至少包含 `reopenDailyTask` 未定义或页面缺少撤销按钮的失败

### Task 2: 实现 reopen API、状态管理和列表交互

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/hooks/useTodayBoard.js`
- Modify: `frontend/src/components/DailyTaskList.jsx`
- Modify: `frontend/src/pages/Today.jsx`

- [x] **Step 1: 在 client 中补齐 reopen API**

```javascript
export async function reopenDailyTask(taskId) {
  return request(`/daily-tasks/${taskId}/reopen`, {
    method: "POST",
  });
}
```

- [x] **Step 2: 在 Today hook 中统一完成与撤销中的任务状态**

```javascript
const [pendingTaskId, setPendingTaskId] = useState(null);

const reopenTask = useCallback(async (taskId) => {
  setPendingTaskId(taskId);
  setError(null);
  try {
    await reopenDailyTask(taskId);
    await loadBoard();
  } catch (reopenError) {
    setError(getErrorMessage(reopenError, "撤销失败，请稍后再试。"));
    throw reopenError;
  } finally {
    setPendingTaskId(null);
  }
}, [loadBoard]);
```

Implementation note: 可以把原 `finishingTaskId` 重命名成更中性的 `pendingTaskId`，避免完成与撤销各维护一套状态。

- [x] **Step 3: 在列表组件中为已完成任务渲染撤销入口**

```javascript
{isCompleted ? (
  <button
    className="ghost-button"
    onClick={() => void onReopenTask(task.id)}
    disabled={pendingTaskId !== null}
  >
    {isSubmitting ? "撤销中..." : "撤销完成"}
  </button>
) : (
  <button className="primary-button" ...>
    完成
  </button>
)}
```

Implementation note: 保留已完成状态 pill；撤销后依赖 `loadBoard()` 回到未完成视图，不在组件内手工拼接假状态。

- [x] **Step 4: 在页面组件中透传撤销动作与统一中的状态**

```javascript
const { tasks, summary, loading, error, pendingTaskId, finishTask, reopenTask } =
  useTodayBoard();

<DailyTaskList
  tasks={tasks}
  pendingTaskId={pendingTaskId}
  onFinishTask={finishTask}
  onReopenTask={reopenTask}
/>
```

- [x] **Step 5: 运行定向前端测试，确认行为转绿**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-1-reopen-today-task/frontend && npm test -- --run src/api/client.test.js src/pages/Today.test.jsx src/App.test.jsx`
Expected: reopen 相关测试通过，原有 Today / App 用例无回归

### Task 3: 全量验证并提交 issue #1 分支

**Files:**
- Modify: `docs/superpowers/plans/2026-06-22-issue-1-today-reopen-implementation.md`

- [x] **Step 1: 运行完整前端测试**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-1-reopen-today-task/frontend && npm test -- --run`
Expected: 全部通过

- [x] **Step 2: 运行完整后端测试，确认前端改动未影响既有链路**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-1-reopen-today-task/backend && AUTH_DATABASE_URL=sqlite:///./test.db /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest`
Expected: 全部通过

- [x] **Step 3: 更新计划勾选并提交**

```bash
cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-1-reopen-today-task
git add frontend/src/api/client.js frontend/src/api/client.test.js frontend/src/hooks/useTodayBoard.js frontend/src/components/DailyTaskList.jsx frontend/src/pages/Today.jsx frontend/src/pages/Today.test.jsx frontend/src/App.test.jsx docs/superpowers/plans/2026-06-22-issue-1-today-reopen-implementation.md
git commit -m "feat: allow reopening completed today tasks"
```
