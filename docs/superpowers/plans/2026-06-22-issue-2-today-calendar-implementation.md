# Today Calendar Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/today` 从“只看今天”改成可切换任意日期的台账工作台，支持月历查看、日期切换、空态反馈，以及在当前页直接把模板加入选中日期。

**Architecture:** 后端补一个按日期范围聚合的日历摘要接口，并让奖励汇总接口支持可选日期参数；前端在 `useTodayBoard` 统一管理选中日期、可见月份、任务列表、日历标记和快速加任务数据；页面拆成“月历 + 当日摘要 + 当日任务 + 快速加任务”四块，所有刷新动作都围绕选中日期重新拉取，避免本地拼状态。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React 18, Vitest, Testing Library

---

## File Structure

**Backend ownership**
- Modify: `backend/app/schemas/task_reward.py`
  - 新增日历摘要响应模型
- Modify: `backend/app/services/task_reward_service.py`
  - 增加日期范围聚合查询，并让奖励汇总支持按查询日期返回
- Modify: `backend/app/api/task_reward.py`
  - 为 `/api/rewards/summary` 增加可选 `date` 参数
  - 新增 `/api/daily-tasks/calendar`
- Modify: `backend/tests/test_task_reward_service.py`
  - 覆盖日历摘要聚合与日期汇总行为
- Modify: `backend/tests/test_public_api.py`
  - 覆盖私有接口的日历摘要和日期汇总查询

**Frontend ownership**
- Modify: `frontend/src/api/client.js`
  - 增加日历摘要请求，并让 `fetchRewardSummary` 支持日期参数
- Modify: `frontend/src/api/client.test.js`
  - 覆盖新 query string 拼装
- Add: `frontend/src/utils/calendar.js`
  - 本地日期解析、月份网格、月切换工具
- Add: `frontend/src/utils/calendar.test.js`
  - 锁定月历日期计算
- Add: `frontend/src/components/TaskCalendar.jsx`
  - 渲染月份切换、日期网格、任务标记
- Add: `frontend/src/components/TaskQuickAddPanel.jsx`
  - 在当前页列出可直接加入选中日期的启用模板
- Modify: `frontend/src/components/TaskSummaryCards.jsx`
  - 把“今日已赚”文案改成与选中日期匹配
- Modify: `frontend/src/hooks/useTodayBoard.js`
  - 收口选中日期、月历摘要、模板拉取、加任务与刷新逻辑
- Modify: `frontend/src/pages/Today.jsx`
  - 组合新组件并呈现选中日期上下文
- Modify: `frontend/src/pages/Today.test.jsx`
  - 覆盖日期切换、空态、快速加任务、日历标记
- Modify: `frontend/src/App.test.jsx`
  - 同步新增 API mocks
- Modify: `frontend/src/styles.css`
  - 补充月历与快速加任务面板样式

**Verification**
- Run: `cd backend && AUTH_DATABASE_URL=sqlite:///./test.db /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest backend/tests/test_task_reward_service.py backend/tests/test_public_api.py`
- Run: `cd frontend && npm test -- --run src/api/client.test.js src/utils/calendar.test.js src/pages/Today.test.jsx src/App.test.jsx`
- Run: `cd frontend && npm test -- --run`
- Run: `cd frontend && npm run build`
- Run: `cd backend && AUTH_DATABASE_URL=sqlite:///./test.db /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest`

### Task 1: 先补后端日期接口能力和回归测试

**Files:**
- Modify: `backend/app/schemas/task_reward.py`
- Modify: `backend/app/services/task_reward_service.py`
- Modify: `backend/app/api/task_reward.py`
- Modify: `backend/tests/test_task_reward_service.py`
- Modify: `backend/tests/test_public_api.py`

- [ ] **Step 1: 写服务层失败测试，定义日期范围内的任务标记摘要**

```python
def test_list_daily_task_calendar_returns_dates_with_task_counts(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    _, template = _create_project_and_template(service, user)
    service.create_daily_task(... date=date(2026, 6, 20), ...)
    completed_task = service.create_daily_task(... date=date(2026, 6, 22), ...)
    service.complete_daily_task(completed_task.id, user=user)

    summary = service.list_daily_task_calendar(
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        user=user,
    )

    assert summary == [
        {"date": date(2026, 6, 20), "task_count": 1, "completed_count": 0},
        {"date": date(2026, 6, 22), "task_count": 1, "completed_count": 1},
    ]
```

- [ ] **Step 2: 写接口测试，定义 `/api/daily-tasks/calendar` 与按日期奖励汇总**

```python
calendar_response = client.get(
    "/api/daily-tasks/calendar",
    params={"start": "2026-06-01", "end": "2026-06-30"},
)
assert calendar_response.json() == [
    {"date": "2026-06-20", "task_count": 1, "completed_count": 0}
]

summary_response = client.get("/api/rewards/summary", params={"date": "2026-06-20"})
assert summary_response.json()["today_earned"] == 8
```

- [ ] **Step 3: 用最小实现补日期参数和日历摘要接口**

```python
class DailyTaskCalendarDayRead(BaseModel):
    date: date
    task_count: int
    completed_count: int


@router.get("/daily-tasks/calendar", response_model=list[DailyTaskCalendarDayRead])
def get_daily_task_calendar(...):
    ...


@router.get("/rewards/summary", response_model=RewardSummaryRead)
def reward_summary(
    date: Optional[datetime.date] = Query(default=None),
    ...
):
    return service.get_reward_summary(user=user, date=date)
```

- [ ] **Step 4: 跑后端定向测试，确认新接口和旧语义同时转绿**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar && AUTH_DATABASE_URL=sqlite:///./test.db /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest backend/tests/test_task_reward_service.py backend/tests/test_public_api.py`
Expected: 新增日期接口测试通过，既有 API 回归不坏

### Task 2: 先写前端测试和日期工具，锁定日历工作台行为

**Files:**
- Modify: `frontend/src/api/client.test.js`
- Add: `frontend/src/utils/calendar.test.js`
- Modify: `frontend/src/pages/Today.test.jsx`
- Modify: `frontend/src/App.test.jsx`

- [ ] **Step 1: 为 client 测试补日期 query 和日历摘要请求**

```javascript
test("fetches reward summary for a selected date", async () => {
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
  await fetchRewardSummary("2026-06-20");
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/rewards/summary?date=2026-06-20",
    expect.any(Object)
  );
});
```

- [ ] **Step 2: 为 calendar util 写失败测试，定义月历网格和月份切换**

```javascript
test("builds a monday-first calendar grid for the visible month", () => {
  const days = buildCalendarDays("2026-06-20");
  expect(days).toHaveLength(35);
  expect(days[0].date).toBe("2026-06-01");
  expect(days.at(-1).date).toBe("2026-07-05");
});
```

- [ ] **Step 3: 为 Today 页面写失败测试，定义日期切换、空态和快速加任务**

```javascript
test("switches selected date and reloads tasks", async () => {
  render(<TodayPage />);
  fireEvent.click(await screen.findByRole("button", { name: "2026-06-22" }));
  await waitFor(() => {
    expect(fetchDailyTasksMock).toHaveBeenLastCalledWith("2026-06-22");
    expect(fetchRewardSummaryMock).toHaveBeenLastCalledWith("2026-06-22");
  });
});

test("adds a template to the selected date and refreshes the board", async () => {
  fireEvent.click(await screen.findByRole("button", { name: "加入 2026-06-22：跑步 30 分钟" }));
  await waitFor(() => {
    expect(createDailyTaskMock).toHaveBeenCalledWith(
      expect.objectContaining({ date: "2026-06-22", task_template_id: 1 })
    );
  });
});
```

- [ ] **Step 4: 跑前端定向测试，确认当前为红灯**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar/frontend && npm test -- --run src/api/client.test.js src/utils/calendar.test.js src/pages/Today.test.jsx src/App.test.jsx`
Expected: 至少包含缺少 calendar util、Today 页面缺少日期切换或快速加任务入口的失败

### Task 3: 实现月历工作台和当前页快速加任务

**Files:**
- Add: `frontend/src/utils/calendar.js`
- Add: `frontend/src/components/TaskCalendar.jsx`
- Add: `frontend/src/components/TaskQuickAddPanel.jsx`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/components/TaskSummaryCards.jsx`
- Modify: `frontend/src/hooks/useTodayBoard.js`
- Modify: `frontend/src/pages/Today.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 增加日期工具和 API 封装**

```javascript
export function fetchRewardSummary(date) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return request(`/rewards/summary${query}`);
}

export function fetchDailyTaskCalendar(start, end) {
  return request(
    `/daily-tasks/calendar?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  );
}
```

- [ ] **Step 2: 在 Today hook 中统一管理选中日期、可见月份和刷新**

```javascript
const [selectedDate, setSelectedDate] = useState(formatLocalDate());
const [visibleMonth, setVisibleMonth] = useState(formatLocalDate());
const [calendarDays, setCalendarDays] = useState([]);
const [quickAddTemplates, setQuickAddTemplates] = useState([]);

const loadBoard = useCallback(async (targetDate = selectedDate, monthDate = visibleMonth) => {
  ...
  const [tasksData, summaryData, calendarData, projectsData, templatesData] = await Promise.all([
    fetchDailyTasks(targetDate),
    fetchRewardSummary(targetDate),
    fetchDailyTaskCalendar(monthStart, monthEnd),
    fetchProjects(),
    fetchTaskTemplates(),
  ]);
  ...
}, [selectedDate, visibleMonth]);
```

- [ ] **Step 3: 实现 `TaskCalendar` 和 `TaskQuickAddPanel`**

```javascript
<TaskCalendar
  selectedDate={selectedDate}
  visibleMonth={visibleMonth}
  days={buildCalendarDays(visibleMonth)}
  markersByDate={calendarMarkers}
  onSelectDate={selectDate}
  onChangeMonth={setVisibleMonth}
/>

<TaskQuickAddPanel
  selectedDate={selectedDate}
  templates={quickAddTemplates}
  addingTemplateId={addingTemplateId}
  onAddTemplate={addTemplateToSelectedDate}
/>
```

- [ ] **Step 4: 让添加任务刷新当前日期任务和月份标记**

```javascript
await createDailyTask({ date: selectedDate, ... });
await loadBoard(selectedDate, visibleMonth);
```

- [ ] **Step 5: 跑前端定向测试，确认行为转绿**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar/frontend && npm test -- --run src/api/client.test.js src/utils/calendar.test.js src/pages/Today.test.jsx src/App.test.jsx`
Expected: 日期切换、空态、日历标记、快速加任务测试通过

### Task 4: 全量验证并提交 issue #2 分支

**Files:**
- Modify: `docs/superpowers/plans/2026-06-22-issue-2-today-calendar-implementation.md`

- [ ] **Step 1: 运行完整前端测试**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar/frontend && npm test -- --run`
Expected: 全部通过

- [ ] **Step 2: 运行前端构建**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar/frontend && npm run build`
Expected: build 成功

- [ ] **Step 3: 运行完整后端测试**

Run: `cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar/backend && AUTH_DATABASE_URL=sqlite:///./test.db /Users/wuzhuoyi/Desktop/code/reward-todo/backend/.venv/bin/pytest`
Expected: 全部通过

- [ ] **Step 4: 提交 issue #2 改动**

```bash
cd /Users/wuzhuoyi/.config/superpowers/worktrees/reward-todo/codex-issue-2-today-calendar
git add backend/app/schemas/task_reward.py backend/app/services/task_reward_service.py backend/app/api/task_reward.py backend/tests/test_task_reward_service.py backend/tests/test_public_api.py frontend/src/api/client.js frontend/src/api/client.test.js frontend/src/utils/calendar.js frontend/src/utils/calendar.test.js frontend/src/components/TaskCalendar.jsx frontend/src/components/TaskQuickAddPanel.jsx frontend/src/components/TaskSummaryCards.jsx frontend/src/hooks/useTodayBoard.js frontend/src/pages/Today.jsx frontend/src/pages/Today.test.jsx frontend/src/App.test.jsx frontend/src/styles.css docs/superpowers/plans/2026-06-22-issue-2-today-calendar-implementation.md
git commit -m "feat: add calendar workspace for daily tasks"
```
