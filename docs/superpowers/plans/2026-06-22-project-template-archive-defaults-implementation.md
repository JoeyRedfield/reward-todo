# Project Template Archive Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `/projects` 页面补齐项目/模板的删除恢复能力，并让模板默认时长和默认奖励在留空时回退到系统默认值。

**Architecture:** 后端继续复用 `TaskProject.status` 和 `TaskTemplate.is_active` 表达可恢复删除，不新增专用删除路由；前端在 `useProjectsBoard` 统一收口删除、恢复、重新选中与刷新逻辑；表单默认值兜底仅在前端提交层生效，后端继续保持数值校验不变。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React 18, Vitest, Testing Library

---

## File Structure

**Backend ownership**
- Modify: `backend/app/services/task_reward_service.py`
  - 继续承载项目、模板、今日任务的状态规则
- Modify: `backend/app/api/task_reward.py`
  - 复用已有更新接口，不新增删除专用路由
- Modify: `backend/tests/test_task_reward_service.py`
  - 增补删除/恢复与恢复后可再次使用模板的服务层测试

**Frontend ownership**
- Modify: `frontend/src/api/client.js`
  - 新增 `updateTaskTemplate`
- Modify: `frontend/src/hooks/useProjectsBoard.js`
  - 增补项目/模板删除恢复、默认值兜底、重新选中逻辑
- Modify: `frontend/src/components/ProjectTemplatePanel.jsx`
  - 增补分组展示、删除恢复按钮、确认动作、默认值提示
- Modify: `frontend/src/pages/Projects.test.jsx`
  - 覆盖项目/模板删除恢复与默认值兜底的回归测试
- Modify: `frontend/src/App.test.jsx`
  - 同步 mock 导出，避免页面测试与应用集成测试断裂

**Verification**
- Run: `cd backend && pytest backend/tests/test_task_reward_service.py -q`
- Run: `cd frontend && npm test -- --run frontend/src/pages/Projects.test.jsx`
- Run: `cd frontend && npm test -- --run frontend/src/App.test.jsx`

### Task 1: 补齐后端删除恢复语义的服务层测试

**Files:**
- Modify: `backend/tests/test_task_reward_service.py`
- Test: `backend/tests/test_task_reward_service.py`

- [ ] **Step 1: 写失败测试，定义项目可以归档再恢复**

```python
def test_update_project_can_archive_and_restore(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    project = service.create_project(name="健身", user=user)

    archived = service.update_project(project.id, user=user, status="archived")
    restored = service.update_project(project.id, user=user, status="active")

    assert archived.status == "archived"
    assert restored.status == "active"
```

- [ ] **Step 2: 运行单测，确认当前行为未被完整覆盖**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_task_reward_service.py::test_update_project_can_archive_and_restore -q`  
Expected: `ERROR: not found` 或测试缺失导致未收集，证明新场景尚未覆盖

- [ ] **Step 3: 写失败测试，定义模板可以停用后恢复并恢复使用**

```python
def test_template_can_be_restored_and_used_to_create_daily_task(db_session) -> None:
    service = TaskRewardService(db_session)
    user = _create_user(db_session)
    _, template = _create_project_and_template(service, user)

    service.update_task_template(template.id, user=user, is_active=False)
    with pytest.raises(ValueError, match="模板已停用"):
        service.create_daily_task(
            user=user,
            task_template_id=template.id,
            date=date(2026, 6, 20),
            estimated_duration_minutes=30,
            reward_amount=2000,
        )

    restored = service.update_task_template(template.id, user=user, is_active=True)
    task = service.create_daily_task(
        user=user,
        task_template_id=template.id,
        date=date(2026, 6, 20),
        estimated_duration_minutes=30,
        reward_amount=2000,
    )

    assert restored.is_active is True
    assert task.task_template_id == template.id
```

- [ ] **Step 4: 运行单测，确认恢复使用场景在当前代码下红灯**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_task_reward_service.py::test_template_can_be_restored_and_used_to_create_daily_task -q`  
Expected: 当前如果无测试则未收集；若实现缺口存在则 FAIL

- [ ] **Step 5: 用最小实现补清晰约束，不新增路由**

```python
def update_project(
    self,
    project_id: int,
    user: User,
    **changes: object,
) -> TaskProject:
    project = self._get_project(project_id, user=user)
    for key, value in changes.items():
        if value is not None and hasattr(project, key):
            setattr(project, key, value)
    self.session.commit()
    self.session.refresh(project)
    return project


def update_task_template(
    self,
    template_id: int,
    user: User,
    **changes: object,
) -> TaskTemplate:
    template = self._get_template(template_id, user=user)
    for key, value in changes.items():
        if value is not None and hasattr(template, key):
            setattr(template, key, value)
    self.session.commit()
    self.session.refresh(template)
    return template
```

Implementation note: 如果这两段已经满足测试，保持服务层代码不重构，只补测试即可；不要为了“体现改动”制造无意义重写。

- [ ] **Step 6: 运行整个服务层测试文件，确认绿灯**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_task_reward_service.py -q`  
Expected: 全部通过，新增归档/恢复场景通过

- [ ] **Step 7: 提交后端测试语义补强**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/tests/test_task_reward_service.py backend/app/services/task_reward_service.py
git commit -m "test: cover archive and restore task reward flows"
```

### Task 2: 先写前端测试，锁定默认值兜底和删除恢复调用

**Files:**
- Modify: `frontend/src/pages/Projects.test.jsx`
- Modify: `frontend/src/App.test.jsx`
- Test: `frontend/src/pages/Projects.test.jsx`

- [ ] **Step 1: 扩展 API mocks，给模板更新接口留出测试入口**

```javascript
const {
  fetchProjectsMock,
  fetchTaskTemplatesMock,
  createProjectMock,
  updateProjectMock,
  createTaskTemplateMock,
  updateTaskTemplateMock,
  createDailyTaskMock,
} = vi.hoisted(() => ({
  fetchProjectsMock: vi.fn(),
  fetchTaskTemplatesMock: vi.fn(),
  createProjectMock: vi.fn(),
  updateProjectMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  updateTaskTemplateMock: vi.fn(),
  createDailyTaskMock: vi.fn(),
}));
```

- [ ] **Step 2: 写失败测试，定义留空时提交默认值**

```javascript
test("submits default duration and reward when template fields are blank", async () => {
  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("例如：力量训练 20 分钟"), {
    target: { value: "复盘 20 分钟" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建模板" }));

  await waitFor(() => {
    expect(createTaskTemplateMock).toHaveBeenCalledWith({
      project_id: 1,
      name: "复盘 20 分钟",
      default_estimated_duration_minutes: 20,
      default_reward_amount: 1200,
      notes: "",
      is_active: true,
    });
  });
});
```

- [ ] **Step 3: 写失败测试，定义项目删除和恢复调用**

```javascript
test("archives and restores a project", async () => {
  fetchProjectsMock
    .mockResolvedValueOnce([
      { id: 1, name: "健身", status: "active", sort_order: 0 },
      { id: 2, name: "写作", status: "active", sort_order: 1 },
      { id: 3, name: "存档项目", status: "archived", sort_order: 2 },
    ])
    .mockResolvedValue([
      { id: 2, name: "写作", status: "active", sort_order: 1 },
      { id: 1, name: "健身", status: "archived", sort_order: 0 },
      { id: 3, name: "存档项目", status: "active", sort_order: 2 },
    ]);

  render(<ProjectsPage />);
  expect(await screen.findByText("健身")).toBeInTheDocument();

  window.confirm = vi.fn(() => true);
  fireEvent.click(screen.getByRole("button", { name: "删除项目 健身" }));

  await waitFor(() => {
    expect(updateProjectMock).toHaveBeenCalledWith(1, { status: "archived" });
  });

  fireEvent.click(screen.getByRole("button", { name: "恢复项目 存档项目" }));

  await waitFor(() => {
    expect(updateProjectMock).toHaveBeenCalledWith(3, { status: "active" });
  });
});
```

- [ ] **Step 4: 写失败测试，定义模板删除和恢复调用**

```javascript
test("archives and restores a template", async () => {
  fetchTaskTemplatesMock.mockResolvedValue([
    {
      id: 1,
      project_id: 1,
      name: "跑步 30 分钟",
      default_estimated_duration_minutes: 30,
      default_reward_amount: 2000,
      notes: "",
      is_active: true,
    },
    {
      id: 2,
      project_id: 1,
      name: "旧模板",
      default_estimated_duration_minutes: 20,
      default_reward_amount: 1200,
      notes: "",
      is_active: false,
    },
  ]);

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  window.confirm = vi.fn(() => true);
  fireEvent.click(screen.getByRole("button", { name: "删除模板 跑步 30 分钟" }));

  await waitFor(() => {
    expect(updateTaskTemplateMock).toHaveBeenCalledWith(1, { is_active: false });
  });

  fireEvent.click(screen.getByRole("button", { name: "恢复模板 旧模板" }));

  await waitFor(() => {
    expect(updateTaskTemplateMock).toHaveBeenCalledWith(2, { is_active: true });
  });
});
```

- [ ] **Step 5: 写失败测试，定义删除当前项目后自动切换到下一个可用项目**

```javascript
test("selects the next active project after archiving the current project", async () => {
  fetchProjectsMock
    .mockResolvedValueOnce([
      { id: 1, name: "健身", status: "active", sort_order: 0 },
      { id: 2, name: "写作", status: "active", sort_order: 1 },
    ])
    .mockResolvedValue([
      { id: 1, name: "健身", status: "archived", sort_order: 0 },
      { id: 2, name: "写作", status: "active", sort_order: 1 },
    ]);

  render(<ProjectsPage />);
  expect(await screen.findByText("跑步 30 分钟")).toBeInTheDocument();

  window.confirm = vi.fn(() => true);
  fireEvent.click(screen.getByRole("button", { name: "删除项目 健身" }));

  await waitFor(() => {
    expect(fetchTaskTemplatesMock).toHaveBeenLastCalledWith(2);
  });
});
```

- [ ] **Step 6: 运行页面测试，确认这些场景先红灯**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Projects.test.jsx`  
Expected: 新增测试失败，报缺少按钮/缺少 mock/调用参数不匹配

- [ ] **Step 7: 同步 `App.test.jsx` 的 client mocks，保持应用级测试可编译**

```javascript
  updateTaskTemplateMock: vi.fn(),
```

and

```javascript
  updateTaskTemplate: apiMocks.updateTaskTemplateMock,
```

- [ ] **Step 8: 提交前端测试骨架**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/pages/Projects.test.jsx frontend/src/App.test.jsx
git commit -m "test: cover projects archive restore behaviors"
```

### Task 3: 实现前端 client、hook 和 UI 逻辑，让测试转绿

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/hooks/useProjectsBoard.js`
- Modify: `frontend/src/components/ProjectTemplatePanel.jsx`
- Test: `frontend/src/pages/Projects.test.jsx`

- [ ] **Step 1: 在 API client 中新增模板更新方法**

```javascript
export async function updateTaskTemplate(templateId, payload) {
  return request(`/task-templates/${templateId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 2: 在 hook 中引入默认值常量和模板更新接口**

```javascript
const DEFAULT_TEMPLATE_DURATION_MINUTES = 20;
const DEFAULT_TEMPLATE_REWARD_AMOUNT = 1200;
```

and

```javascript
import {
  createDailyTask,
  createProject,
  createTaskTemplate,
  fetchProjects,
  fetchTaskTemplates,
  getErrorMessage,
  updateProject,
  updateTaskTemplate,
} from "../api/client";
```

- [ ] **Step 3: 提取可用项目选择逻辑，保证删除后自动切换**

```javascript
function getNextActiveProjectId(projectsData, preferredProjectId = null) {
  const activeProjects = projectsData.filter((project) => project.status === "active");
  if (activeProjects.length === 0) {
    return null;
  }

  if (preferredProjectId !== null) {
    const matched = activeProjects.find((project) => project.id === preferredProjectId);
    if (matched) {
      return matched.id;
    }
  }

  return activeProjects[0].id;
}
```

- [ ] **Step 4: 改造 `loadBoard` 和 `submitProject`，统一使用首个可用项目**

```javascript
const initialProjectId = getNextActiveProjectId(projectsData);
setSelectedProjectId(initialProjectId);
if (initialProjectId === null) {
  setTemplates([]);
} else {
  setTemplates(await fetchTaskTemplates(initialProjectId));
}
```

- [ ] **Step 5: 改造 `submitTemplate`，让空值回退到默认值**

```javascript
await createTaskTemplate({
  project_id: selectedProjectId,
  name: payload.name,
  default_estimated_duration_minutes:
    payload.defaultEstimatedDurationMinutes ?? DEFAULT_TEMPLATE_DURATION_MINUTES,
  default_reward_amount:
    payload.defaultRewardAmount ?? DEFAULT_TEMPLATE_REWARD_AMOUNT,
  notes: "",
  is_active: true,
});
```

- [ ] **Step 6: 在 hook 中新增删除恢复动作**

```javascript
const archiveProject = useCallback(async (projectId) => {
  setError(null);
  setSuccessMessage(null);
  try {
    await updateProject(projectId, { status: "archived" });
    const projectsData = await fetchProjects();
    setProjects(projectsData);
    const nextProjectId = getNextActiveProjectId(projectsData, selectedProjectId === projectId ? null : selectedProjectId);
    setSelectedProjectId(nextProjectId);
    setTemplates(nextProjectId === null ? [] : await fetchTaskTemplates(nextProjectId));
    setSuccessMessage("项目已删除，可在已删除项目中恢复。");
  } catch (submitError) {
    setError(getErrorMessage(submitError, "删除项目失败，请稍后重试。"));
    throw submitError;
  }
}, [selectedProjectId]);
```

```javascript
const restoreProject = useCallback(async (projectId) => {
  setError(null);
  setSuccessMessage(null);
  try {
    await updateProject(projectId, { status: "active" });
    setProjects(await fetchProjects());
    setSuccessMessage("项目已恢复。");
  } catch (submitError) {
    setError(getErrorMessage(submitError, "恢复项目失败，请稍后重试。"));
    throw submitError;
  }
}, []);
```

```javascript
const archiveTemplate = useCallback(async (templateId) => {
  if (selectedProjectId === null) {
    return;
  }
  setError(null);
  setSuccessMessage(null);
  try {
    await updateTaskTemplate(templateId, { is_active: false });
    setTemplates(await fetchTaskTemplates(selectedProjectId));
    setSuccessMessage("模板已删除，可在已删除模板中恢复。");
  } catch (submitError) {
    setError(getErrorMessage(submitError, "删除模板失败，请稍后重试。"));
    throw submitError;
  }
}, [selectedProjectId]);
```

```javascript
const restoreTemplate = useCallback(async (templateId) => {
  if (selectedProjectId === null) {
    return;
  }
  setError(null);
  setSuccessMessage(null);
  try {
    await updateTaskTemplate(templateId, { is_active: true });
    setTemplates(await fetchTaskTemplates(selectedProjectId));
    setSuccessMessage("模板已恢复。");
  } catch (submitError) {
    setError(getErrorMessage(submitError, "恢复模板失败，请稍后重试。"));
    throw submitError;
  }
}, [selectedProjectId]);
```

- [ ] **Step 7: 将这些动作暴露给页面**

```javascript
  archiveProject,
  restoreProject,
  archiveTemplate,
  restoreTemplate,
```

- [ ] **Step 8: 改造组件表单提交，把空字符串转成 `null` 而不是 `0`**

```javascript
const duration =
  durationValue.trim() === "" ? null : Number(durationValue);
const reward =
  rewardValue.trim() === "" ? null : Number(rewardValue);
```

```javascript
if (duration !== null && (!Number.isInteger(duration) || duration <= 0)) {
  setTemplateFormError("默认时长需要填写正整数分钟。");
  return;
}
if (reward !== null && (!Number.isInteger(reward) || reward < 0)) {
  setTemplateFormError("默认奖励金额需要填写非负整数。");
  return;
}
```

- [ ] **Step 9: 改造组件 UI，增加分组和删除恢复按钮**

```javascript
const activeProjects = projects.filter((project) => project.status === "active");
const archivedProjects = projects.filter((project) => project.status !== "active");
const activeTemplates = templates.filter((template) => template.is_active);
const archivedTemplates = templates.filter((template) => !template.is_active);
```

```javascript
<button
  className="ghost-button"
  onClick={() => {
    if (window.confirm(`删除项目「${project.name}」？`)) {
      void onArchiveProject(project.id);
    }
  }}
  aria-label={`删除项目 ${project.name}`}
>
  删除
</button>
```

```javascript
<button
  className="ghost-button"
  onClick={() => void onRestoreProject(project.id)}
  aria-label={`恢复项目 ${project.name}`}
>
  恢复
</button>
```

```javascript
<button
  className="ghost-button"
  onClick={() => {
    if (window.confirm(`删除模板「${template.name}」？`)) {
      void onArchiveTemplate(template.id);
    }
  }}
  aria-label={`删除模板 ${template.name}`}
>
  删除
</button>
```

```javascript
<button
  className="ghost-button"
  onClick={() => void onRestoreTemplate(template.id)}
  aria-label={`恢复模板 ${template.name}`}
>
  恢复
</button>
```

```javascript
<p className="field-hint">留空时使用默认：20 分钟 / 1200 分</p>
```

- [ ] **Step 10: 运行页面测试，确认转绿**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Projects.test.jsx`  
Expected: 新增删除恢复和默认值用例通过

- [ ] **Step 11: 运行应用级测试，确认 mock 没断**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/App.test.jsx`  
Expected: `App.test.jsx` 全部通过

- [ ] **Step 12: 提交前端实现**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/api/client.js frontend/src/hooks/useProjectsBoard.js frontend/src/components/ProjectTemplatePanel.jsx frontend/src/pages/Projects.test.jsx frontend/src/App.test.jsx
git commit -m "feat: add restorable project and template archives"
```

### Task 4: 全量验证并整理结果

**Files:**
- Modify: 无
- Test: `backend/tests/test_task_reward_service.py`
- Test: `frontend/src/pages/Projects.test.jsx`
- Test: `frontend/src/App.test.jsx`

- [ ] **Step 1: 运行后端验证**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && pytest tests/test_task_reward_service.py -q`  
Expected: 所有服务层测试通过

- [ ] **Step 2: 运行前端页面验证**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Projects.test.jsx src/App.test.jsx`  
Expected: 两个测试文件全部通过

- [ ] **Step 3: 检查工作区变更是否只包含本次范围**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && git status --short`  
Expected: 只看到本次实现相关文件，以及仓库里原本就存在的未提交文件

- [ ] **Step 4: 汇总验证证据后再宣告完成**

```text
后端验证命令：
cd backend && pytest tests/test_task_reward_service.py -q

前端验证命令：
cd frontend && npm test -- --run src/pages/Projects.test.jsx src/App.test.jsx
```

- [ ] **Step 5: 如需合并为最终提交，再手动整理 commit**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git log --oneline -3
```

根据实际需要决定是否保留分步提交；不要 `git commit --amend`，也不要重写用户已有提交历史。
