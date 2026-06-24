# Direct Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/today` 支持直接创建、完成、删除独立任务，并把这条能力同步扩展到后端 API、MCP 和相关客户端，同时保持现有模板任务链路兼容。

**Architecture:** 继续复用现有 `daily_tasks` 主模型和 `create_daily_task` 业务语义，通过允许 `task_template_id` / `project_id` 为空来表达独立任务。后端在 service 层统一承载“模板任务 vs 独立任务”的创建与删除规则，API、MCP 和前端只负责参数模式与界面表达。删除已完成独立任务时保留历史账本流水，通过解绑旧流水并按净额补一条 `delete:` 调整流水来维持账本正确性。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Vitest, React

---

## File Map

### Backend

- Modify: `backend/app/models/daily_task.py`
  - 允许 `project_id` / `task_template_id` 为空，并为后续独立任务删除保留模型层入口。
- Create: `backend/alembic/versions/0006_allow_direct_daily_tasks.py`
  - 把 `daily_tasks.project_id` / `task_template_id` 改成可空，并调整模板任务唯一约束。
- Modify: `backend/app/schemas/task_reward.py`
  - 扩展 `DailyTaskCreate` 为两种创建模式可表达的 schema，允许返回的 `DailyTaskRead.project_id` / `task_template_id` 为可空。
- Modify: `backend/app/services/task_reward_service.py`
  - 实现独立任务创建、模板/独立任务二选一校验、独立任务删除、账本净额冲回和流水解绑逻辑。
- Modify: `backend/app/api/task_reward.py`
  - 接通扩展后的创建接口，并新增 `DELETE /api/daily-tasks/{task_id}`。
- Modify: `backend/app/api/mcp.py`
  - 扩展 MCP `create_daily_task` 参数 schema，并新增 `delete_daily_task`。

### Backend Tests

- Modify: `backend/tests/test_task_reward_service.py`
  - 增加独立任务创建、删除、账本修正、模板任务删除拒绝等服务层测试。
- Modify: `backend/tests/test_public_api.py`
  - 增加 HTTP API 独立任务创建/删除、返回可空字段与模板任务删除拒绝测试。
- Modify: `backend/tests/test_mcp_api.py`
  - 增加 MCP 独立任务创建和删除测试。

### Frontend

- Modify: `frontend/src/api/client.js`
  - 允许 `createDailyTask` 发送独立任务模式参数，并新增 `deleteDailyTask`。
- Modify: `frontend/src/hooks/useTodayBoard.js`
  - 增加直接添加独立任务与删除独立任务状态流。
- Modify: `frontend/src/components/TaskQuickAddPanel.jsx`
  - 在现有模板快速加入面板顶部加入直接添加独立任务表单。
- Modify: `frontend/src/components/DailyTaskList.jsx`
  - 根据独立任务来源显示标签与删除按钮。
- Modify: `frontend/src/pages/Today.test.jsx`
  - 覆盖直接添加独立任务、空模板场景、删除按钮和删除成功刷新。

### Client Script

- Modify: `skills/reward-todo/scripts/rewardtools.py`
  - 扩展 `tasks-add` 支持独立任务模式，并新增 `tasks-delete`。

## Task 1: Add failing backend tests for direct-task service behavior

**Files:**
- Modify: `backend/tests/test_task_reward_service.py`

- [ ] **Step 1: Add a failing test for creating a direct task without template/project**

```python
def test_create_direct_daily_task_without_template_or_project(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)

    task = service.create_daily_task(
        user=user,
        name="临时复盘",
        date=date(2026, 6, 20),
        estimated_duration_minutes=20,
        reward_amount=0,
    )

    assert task.project_id is None
    assert task.task_template_id is None
    assert task.name_snapshot == "临时复盘"
    assert task.estimated_duration_minutes_snapshot == 20
    assert task.reward_amount_snapshot == 0
```

- [ ] **Step 2: Add a failing test for mixed create payload rejection**

```python
def test_create_daily_task_rejects_mixed_template_and_direct_fields(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    _, template = _create_project_and_template(service, user)

    with pytest.raises(ValueError, match="日任务创建参数无效"):
        service.create_daily_task(
            user=user,
            task_template_id=template.id,
            name="混合任务",
            date=date(2026, 6, 20),
            estimated_duration_minutes=30,
            reward_amount=1000,
        )
```

- [ ] **Step 3: Add a failing test for deleting a completed direct task with ledger adjustment**

```python
def test_delete_completed_direct_daily_task_rebalances_ledger_and_unlinks_history(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    task = service.create_daily_task(
        user=user,
        name="临时复盘",
        date=date(2026, 6, 20),
        estimated_duration_minutes=20,
        reward_amount=1200,
    )
    service.complete_daily_task(task.id, user=user, actual_duration_minutes=18)

    service.delete_daily_task(task.id, user=user)

    ledger = service.list_reward_ledger(20, user=user)
    assert [item.amount for item in ledger[:2]] == [-1200, 1200]
    assert ledger[0].reason == "delete:临时复盘"
    assert ledger[0].daily_task_id is None
    assert ledger[1].daily_task_id is None
    assert service.list_daily_tasks(date(2026, 6, 20), user=user) == []
```

- [ ] **Step 4: Add a failing test for rejecting deletion of template-derived tasks**

```python
def test_delete_daily_task_rejects_template_task(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    _, template = _create_project_and_template(service, user)
    task = service.create_daily_task(
        user=user,
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )

    with pytest.raises(ValueError, match="只有独立任务支持删除"):
        service.delete_daily_task(task.id, user=user)
```

- [ ] **Step 5: Run service tests to verify failure**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_task_reward_service.py -q`
Expected: FAIL with missing `name` support and missing `delete_daily_task`

## Task 2: Implement backend direct-task model, service, schema, and migration

**Files:**
- Modify: `backend/app/models/daily_task.py`
- Create: `backend/alembic/versions/0006_allow_direct_daily_tasks.py`
- Modify: `backend/app/schemas/task_reward.py`
- Modify: `backend/app/services/task_reward_service.py`

- [ ] **Step 1: Update the SQLAlchemy daily task model to allow null project/template IDs**

```python
class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("task_projects.id"), nullable=True)
    task_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("task_templates.id"),
        nullable=True,
    )
```

- [ ] **Step 2: Add Alembic migration for nullable direct-task fields and template-only uniqueness**

```python
def upgrade() -> None:
    op.drop_constraint("uq_daily_task_template_date", "daily_tasks", type_="unique")
    op.alter_column("daily_tasks", "project_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("daily_tasks", "task_template_id", existing_type=sa.Integer(), nullable=True)
    op.create_index(
        "ix_daily_tasks_template_date_unique",
        "daily_tasks",
        ["date", "task_template_id"],
        unique=True,
        postgresql_where=sa.text("task_template_id IS NOT NULL"),
    )
```

- [ ] **Step 3: Expand Pydantic schemas for create-mode switching and nullable reads**

```python
class DailyTaskCreate(BaseModel):
    date: date
    task_template_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    estimated_duration_minutes: int = Field(ge=1, le=1440)
    reward_amount: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_mode(self):
        has_template = self.task_template_id is not None
        has_name = self.name is not None and self.name.strip() != ""
        if has_template == has_name:
            raise ValueError("日任务创建参数无效")
        return self


class DailyTaskRead(BaseModel):
    id: int
    date: date
    project_id: Optional[int]
    task_template_id: Optional[int]
```

- [ ] **Step 4: Implement direct-task creation and deletion in service layer**

```python
def create_daily_task(
    self,
    date: datetime.date,
    estimated_duration_minutes: int,
    reward_amount: int,
    user: User,
    task_template_id: Optional[int] = None,
    name: Optional[str] = None,
) -> DailyTask:
    if task_template_id is not None and name is not None:
        raise ValueError("日任务创建参数无效")
    if task_template_id is None and name is None:
        raise ValueError("日任务创建参数无效")

    if task_template_id is not None:
        template = self._get_template(task_template_id, user=user)
        if not template.is_active:
            raise ValueError("模板已停用")
        task = DailyTask(
            date=date,
            user_id=user.id,
            project_id=template.project_id,
            task_template_id=template.id,
            name_snapshot=template.name,
            estimated_duration_minutes_snapshot=estimated_duration_minutes,
            reward_amount_snapshot=reward_amount,
            status="pending",
        )
    else:
        task = DailyTask(
            date=date,
            user_id=user.id,
            project_id=None,
            task_template_id=None,
            name_snapshot=self._normalize_required_name(name or "", "任务名称不能为空"),
            estimated_duration_minutes_snapshot=estimated_duration_minutes,
            reward_amount_snapshot=reward_amount,
            status="pending",
        )
    self.session.add(task)
    try:
        self.session.commit()
    except IntegrityError:
        self.session.rollback()
        raise ValueError("当日任务已存在")
    self.session.refresh(task)
    return task

def delete_daily_task(self, task_id: int, user: User) -> None:
    task = self._get_daily_task(task_id, user=user)
    if task.task_template_id is not None:
        raise ValueError("只有独立任务支持删除")

    task_balance = int(
        self.session.scalar(
            select(func.coalesce(func.sum(RewardLedger.amount), 0)).where(
                RewardLedger.daily_task_id == task.id,
                RewardLedger.user_id == user.id,
            )
        )
        or 0
    )
    if task_balance > 0:
        self.session.add(
            RewardLedger(
                user_id=user.id,
                entry_type="adjust",
                amount=-task_balance,
                reason=f"delete:{task.name_snapshot}",
                daily_task_id=None,
            )
        )

    self.session.execute(
        update(RewardLedger)
        .where(RewardLedger.daily_task_id == task.id, RewardLedger.user_id == user.id)
        .values(daily_task_id=None)
    )
    self.session.delete(task)
    self.session.commit()
```

- [ ] **Step 5: Run service tests to verify pass**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_task_reward_service.py -q`
Expected: PASS

- [ ] **Step 6: Commit backend model/service work**

```bash
git add backend/app/models/daily_task.py backend/alembic/versions/0006_allow_direct_daily_tasks.py backend/app/schemas/task_reward.py backend/app/services/task_reward_service.py backend/tests/test_task_reward_service.py
git commit -m "feat: support direct daily tasks in service layer"
```

## Task 3: Add failing HTTP API tests for direct task create/delete

**Files:**
- Modify: `backend/tests/test_public_api.py`

- [ ] **Step 1: Add a failing API test for creating a direct task**

```python
def test_create_direct_daily_task_via_api(client, db_session) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/daily-tasks",
        json={
            "date": "2026-06-22",
            "name": "临时复盘",
            "estimated_duration_minutes": 20,
            "reward_amount": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["task_template_id"] is None
    assert response.json()["project_id"] is None
```

- [ ] **Step 2: Add a failing API test for deleting a direct task**

```python
def test_delete_direct_daily_task_via_api(client, db_session) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    service = TaskRewardService(db_session)
    task = service.create_daily_task(
        user=user,
        name="临时复盘",
        date=date(2026, 6, 22),
        estimated_duration_minutes=20,
        reward_amount=0,
    )

    response = client.delete(f"/api/daily-tasks/{task.id}")

    assert response.status_code == 204
```

- [ ] **Step 3: Add a failing API test for rejecting template task deletion**

```python
def test_delete_template_daily_task_via_api_rejected(client, db_session) -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"username": "reward", "password": "super-secret"},
    )
    assert login_response.status_code == 200
    user = db_session.scalar(select(User).where(User.username == "reward"))
    assert user is not None
    _, _, _, task = _seed_data(db_session, user=user)

    response = client.delete(f"/api/daily-tasks/{task.id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "只有独立任务支持删除"
```

- [ ] **Step 4: Run public API tests to verify failure**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_public_api.py -q`
Expected: FAIL with missing DELETE route or schema mismatch

## Task 4: Implement HTTP API create/delete support

**Files:**
- Modify: `backend/app/api/task_reward.py`
- Modify: `backend/tests/test_public_api.py`

- [ ] **Step 1: Wire the expanded create schema through the existing POST route**

```python
@router.post("/daily-tasks", response_model=DailyTaskRead)
def create_daily_task(
    payload: DailyTaskCreate,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        return service.create_daily_task(user=user, **payload.model_dump())
    except ValueError as exc:
        _raise_http_error(exc)
```

- [ ] **Step 2: Add DELETE route for direct-task deletion**

```python
@router.delete("/daily-tasks/{task_id}", status_code=204)
def delete_daily_task(
    task_id: int,
    authenticated: tuple[User, str] = Depends(require_authenticated_user),
    service: TaskRewardService = Depends(get_task_reward_service),
):
    user, _ = authenticated
    try:
        service.delete_daily_task(task_id, user=user)
    except ValueError as exc:
        _raise_http_error(exc)
```

- [ ] **Step 3: Run public API tests to verify pass**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_public_api.py -q`
Expected: PASS

- [ ] **Step 4: Commit HTTP API work**

```bash
git add backend/app/api/task_reward.py backend/tests/test_public_api.py
git commit -m "feat: add direct daily task api routes"
```

## Task 5: Add failing MCP and tool-script tests/spec coverage

**Files:**
- Modify: `backend/tests/test_mcp_api.py`
- Modify: `skills/reward-todo/scripts/rewardtools.py`

- [ ] **Step 1: Add a failing MCP test for direct task creation**

```python
def test_mcp_create_direct_daily_task(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-direct-task",
    )

    response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "date": "2026-06-20",
                "name": "临时复盘",
                "estimated_duration_minutes": 20,
                "reward_amount": 0,
            },
        },
        request_id=20,
    )

    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"]["task_template_id"] is None
```

- [ ] **Step 2: Add a failing MCP test for deleting a direct task**

```python
def test_mcp_delete_direct_daily_task(client) -> None:
    token = _create_mcp_token(
        client,
        username="reward",
        password="super-secret",
        name="bootstrap-mcp-delete-task",
    )
    create_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={
            "name": "create_daily_task",
            "arguments": {
                "date": "2026-06-20",
                "name": "临时复盘",
                "estimated_duration_minutes": 20,
                "reward_amount": 0,
            },
        },
        request_id=21,
    )
    task_id = create_response.json()["result"]["structuredContent"]["id"]

    delete_response = _mcp_call(
        client,
        token,
        "tools/call",
        params={"name": "delete_daily_task", "arguments": {"task_id": task_id}},
        request_id=22,
    )

    assert delete_response.status_code == 200
```

- [ ] **Step 3: Extend the CLI command table for direct add/delete**

```python
"tasks-add": {
    "description": "Create a daily task from a template or directly.",
    "method": "POST",
    "path": "/daily-tasks",
    "params": [
        {"flag": "--date", "api_name": "date", "kind": "body", "required": True},
        {"flag": "--template-id", "api_name": "task_template_id", "kind": "body", "type": "int"},
        {"flag": "--name", "api_name": "name", "kind": "body"},
        {"flag": "--duration", "api_name": "estimated_duration_minutes", "kind": "body", "type": "int", "required": True},
        {"flag": "--reward", "api_name": "reward_amount", "kind": "body", "type": "int", "required": True},
    ],
},
"tasks-delete": {
    "description": "Delete a direct daily task.",
    "method": "DELETE",
    "path": "/daily-tasks/{task_id}",
    "params": [
        {"flag": "--task-id", "api_name": "task_id", "kind": "path", "type": "int", "required": True},
    ],
},
```

- [ ] **Step 4: Run MCP tests to verify failure**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_mcp_api.py -q`
Expected: FAIL with MCP schema or tool handler missing `name`/`delete_daily_task`

## Task 6: Implement MCP and script support for direct tasks

**Files:**
- Modify: `backend/app/api/mcp.py`
- Modify: `backend/tests/test_mcp_api.py`
- Modify: `skills/reward-todo/scripts/rewardtools.py`

- [ ] **Step 1: Update MCP tool descriptors for direct task create/delete**

```python
_tool_descriptor(
    "create_daily_task",
    "Create a daily task from an existing template or directly.",
    {
        "type": "object",
        "properties": {
            "task_template_id": {"type": "integer"},
            "name": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "estimated_duration_minutes": {"type": "integer"},
            "reward_amount": {"type": "integer"},
        },
        "required": ["date", "estimated_duration_minutes", "reward_amount"],
    },
    {"type": "object"},
)
```

- [ ] **Step 2: Implement MCP handler branches for direct task create/delete**

```python
if tool_name == "create_daily_task":
    if "date" not in arguments:
        return _invalid_params(request_id, "Missing required argument: date")
    if "estimated_duration_minutes" not in arguments:
        return _invalid_params(request_id, "Missing required argument: estimated_duration_minutes")
    if "reward_amount" not in arguments:
        return _invalid_params(request_id, "Missing required argument: reward_amount")
    target_date, invalid_response = _parse_date_argument(request_id, arguments.get("date"), "date")
    if invalid_response is not None:
        return invalid_response
    task_template_id = None
    if arguments.get("task_template_id") is not None:
        task_template_id, invalid_response = _parse_int_argument(
            request_id,
            arguments.get("task_template_id"),
            "task_template_id",
        )
        if invalid_response is not None:
            return invalid_response
    estimated_duration, invalid_response = _parse_int_argument(
        request_id,
        arguments.get("estimated_duration_minutes"),
        "estimated_duration_minutes",
    )
    if invalid_response is not None:
        return invalid_response
    reward_amount, invalid_response = _parse_int_argument(
        request_id,
        arguments.get("reward_amount"),
        "reward_amount",
    )
    if invalid_response is not None:
        return invalid_response
    result = DailyTaskRead.model_validate(
        service.create_daily_task(
            user=_user,
            task_template_id=task_template_id,
            name=arguments.get("name"),
            date=target_date,
            estimated_duration_minutes=estimated_duration,
            reward_amount=reward_amount,
        )
    ).model_dump()

if tool_name == "delete_daily_task":
    if "task_id" not in arguments:
        return _invalid_params(request_id, "Missing required argument: task_id")
    task_id, invalid_response = _parse_int_argument(request_id, arguments.get("task_id"), "task_id")
    if invalid_response is not None:
        return invalid_response
    service.delete_daily_task(task_id, user=_user)
    return _jsonrpc_result(request_id, _text_result({"ok": True}))
```

- [ ] **Step 3: Run MCP tests to verify pass**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_mcp_api.py -q`
Expected: PASS

- [ ] **Step 4: Commit MCP/script work**

```bash
git add backend/app/api/mcp.py backend/tests/test_mcp_api.py skills/reward-todo/scripts/rewardtools.py
git commit -m "feat: expose direct daily tasks via mcp and tools"
```

## Task 7: Add failing frontend tests for direct-task UI

**Files:**
- Modify: `frontend/src/pages/Today.test.jsx`

- [ ] **Step 1: Add a failing test for rendering the direct-task form without templates**

```jsx
test("shows direct task form even when no templates exist", async () => {
  fetchTaskTemplatesMock.mockResolvedValue([]);

  render(<TodayPage />);

  expect(await screen.findByLabelText("任务名称")).toBeInTheDocument();
  expect(screen.getByText("当前没有可直接加入台账的启用模板。")).toBeInTheDocument();
});
```

- [ ] **Step 2: Add a failing test for creating a direct task with empty reward**

```jsx
test("creates a direct task for the selected date with empty reward treated as zero", async () => {
  fetchDailyTasksMock
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([
      {
        ...selectedDateTask,
        id: 5,
        task_template_id: null,
        project_id: null,
        name_snapshot: "临时复盘",
        estimated_duration_minutes_snapshot: 20,
        reward_amount_snapshot: 0,
      },
    ]);
  render(<TodayPage />);

  fireEvent.click(await screen.findByRole("button", { name: "选择 2026-06-22" }));
  fireEvent.change(screen.getByLabelText("任务名称"), { target: { value: "临时复盘" } });
  fireEvent.change(screen.getByLabelText("预计时长（分钟）"), { target: { value: "20" } });
  fireEvent.click(screen.getByRole("button", { name: "直接添加任务" }));

  await waitFor(() => {
    expect(createDailyTaskMock).toHaveBeenCalledWith({
      date: "2026-06-22",
      name: "临时复盘",
      estimated_duration_minutes: 20,
      reward_amount: 0,
    });
  });
});
```

- [ ] **Step 3: Add a failing test for delete controls on direct tasks only**

```jsx
test("shows delete button only for direct tasks", async () => {
  fetchDailyTasksMock.mockResolvedValue([
    task,
    {
      ...selectedDateTask,
      id: 9,
      task_template_id: null,
      project_id: null,
      name_snapshot: "临时复盘",
    },
  ]);

  render(<TodayPage />);

  expect(await screen.findByText("临时复盘")).toBeInTheDocument();
  expect(screen.getByText("独立任务")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "删除 临时复盘" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "删除 跑步 30 分钟" })).not.toBeInTheDocument();
});
```

- [ ] **Step 4: Run Today page tests to verify failure**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Today.test.jsx`
Expected: FAIL with missing form fields or delete controls

## Task 8: Implement frontend direct-task form and delete flow

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/hooks/useTodayBoard.js`
- Modify: `frontend/src/components/TaskQuickAddPanel.jsx`
- Modify: `frontend/src/components/DailyTaskList.jsx`
- Modify: `frontend/src/pages/Today.test.jsx`

- [ ] **Step 1: Add delete API client helper**

```javascript
export async function deleteDailyTask(taskId) {
  return request(`/daily-tasks/${taskId}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 2: Extend Today hook with direct add and delete flows**

```javascript
const addDirectTaskToSelectedDate = useCallback(async (payload) => {
  setError(null);
  try {
    await createDailyTask({
      date: selectedDateRef.current,
      name: payload.name,
      estimated_duration_minutes: payload.estimatedDurationMinutes,
      reward_amount: payload.rewardAmount ?? 0,
    });
    await loadBoard(selectedDateRef.current, visibleMonthRef.current);
  } catch (submitError) {
    setError(getErrorMessage(submitError, "添加任务失败，请稍后重试。"));
    throw submitError;
  }
}, [loadBoard]);

const deleteDirectTaskFromSelectedDate = useCallback(async (taskId) => {
  setPendingTaskId(taskId);
  setError(null);
  try {
    await deleteDailyTask(taskId);
    await loadBoard(selectedDateRef.current, visibleMonthRef.current);
  } catch (deleteError) {
    setError(getErrorMessage(deleteError, "删除任务失败，请稍后重试。"));
    throw deleteError;
  } finally {
    setPendingTaskId(null);
  }
}, [loadBoard]);
```

- [ ] **Step 3: Implement direct-task form UI in quick-add panel**

```jsx
<div className="form-stack">
  <label>
    <span>任务名称</span>
    <input
      type="text"
      value={directTaskName}
      onChange={(event) => setDirectTaskName(event.target.value)}
      placeholder="例如：临时复盘"
      disabled={submittingDirectTask}
    />
  </label>
  <label>
    <span>预计时长（分钟）</span>
    <input
      type="number"
      min="1"
      value={directTaskDuration}
      onChange={(event) => setDirectTaskDuration(event.target.value)}
      placeholder="20"
      disabled={submittingDirectTask}
    />
  </label>
  <label>
    <span>奖励金额（元）</span>
    <input
      type="number"
      min="0"
      step="0.01"
      value={directTaskReward}
      onChange={(event) => setDirectTaskReward(event.target.value)}
      placeholder="0.00"
      disabled={submittingDirectTask}
    />
  </label>
  <p className="empty-copy">留空按 ¥0.00 处理</p>
  <button
    type="button"
    className="primary-button"
    disabled={submittingDirectTask}
    onClick={() => void handleDirectTaskSubmit()}
  >
    {submittingDirectTask ? "添加中..." : "直接添加任务"}
  </button>
</div>
```

- [ ] **Step 4: Implement direct-task tag and delete button in daily task list**

```jsx
const isDirectTask = task.task_template_id === null;
const actionMessage =
  task.status === "completed"
    ? `确认删除已完成任务「${task.name_snapshot}」吗？删除后会扣回已发放奖励。`
    : `确认删除任务「${task.name_snapshot}」吗？`;

{isDirectTask ? <span className="status-pill">独立任务</span> : null}
{isDirectTask ? (
  <button
    className="ghost-button"
    aria-label={`删除 ${task.name_snapshot}`}
    onClick={() => {
      const message =
        task.status === "completed"
          ? `确认删除已完成任务「${task.name_snapshot}」吗？删除后会扣回已发放奖励。`
          : `确认删除任务「${task.name_snapshot}」吗？`;
      if (window.confirm(message)) {
        void onDeleteTask(task.id).catch(() => {});
      }
    }}
    disabled={pendingTaskId !== null}
  >
    {isSubmitting ? "删除中..." : "删除"}
  </button>
) : null}
```

- [ ] **Step 5: Run Today page tests to verify pass**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Today.test.jsx`
Expected: PASS

- [ ] **Step 6: Commit frontend work**

```bash
git add frontend/src/api/client.js frontend/src/hooks/useTodayBoard.js frontend/src/components/TaskQuickAddPanel.jsx frontend/src/components/DailyTaskList.jsx frontend/src/pages/Today.test.jsx
git commit -m "feat: add direct tasks to today page"
```

## Task 9: Run focused verification and final regression

**Files:**
- Verify only

- [ ] **Step 1: Run backend service/API/MCP test suite**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && ./.venv/bin/pytest tests/test_task_reward_service.py tests/test_public_api.py tests/test_mcp_api.py -q`
Expected: PASS

- [ ] **Step 2: Run frontend Today-page tests**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Today.test.jsx`
Expected: PASS

- [ ] **Step 3: Run full frontend test suite if focused tests passed**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run`
Expected: PASS

- [ ] **Step 4: Check git status before handoff**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && git status --short`
Expected: only intended implementation files modified

- [ ] **Step 5: Commit final verification-only adjustments if needed**

```bash
git add -A
git commit -m "test: cover direct daily task workflow"
```
