# Auth Register Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `reward-todo` 增加可注册认证流、默认工作台初始化，以及更接近 `ezbookkeeping` 的登录/注册/账户页视觉结构，同时保留旧 `.env` 到新 `AUTH_INITIAL_*` 的兼容启动路径。

**Architecture:** 后端在现有 `AuthService` 上扩展注册能力与用户资料字段，通过单独 migration 为历史用户补齐 `display_name` / `email`，并在注册事务中可选创建默认项目与模板。前端保持现有 `AuthContext + react-router` 结构，新增 `/signup` 页面与共用 auth shell 样式，重做登录页和账户页层级但不改变任务奖励主业务数据流。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pytest, React, React Router, Vitest, Testing Library, Docker Compose

---

### Task 1: 扩展用户模型与配置开关

**Files:**
- Create: `backend/alembic/versions/0004_add_user_profile_and_registration_flag.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败的后端配置与 migration 测试**

```python
def test_settings_enable_registration_by_default(monkeypatch):
    monkeypatch.setenv("AUTH_INITIAL_USERNAME", "reward")
    monkeypatch.setenv("AUTH_INITIAL_PASSWORD", "secret-pass")
    monkeypatch.setenv("TESTING", "false")

    settings = get_settings()

    assert settings.auth_enable_registration is True


def test_auth_migrations_create_profile_columns(tmp_path, monkeypatch):
    database_path = tmp_path / "auth_profile.db"
    database_url = f"sqlite:///{database_path}"
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_command, env = _build_alembic_subprocess(backend_dir)
    env["DATABASE_URL"] = database_url
    env["AUTH_INITIAL_USERNAME"] = "reward"
    env["AUTH_INITIAL_PASSWORD"] = "secret-pass"
    env["TESTING"] = "true"

    subprocess.run([*alembic_command, "-c", "alembic.ini", "upgrade", "head"], cwd=backend_dir, env=env, check=True)

    inspector = inspect(create_engine(database_url, future=True))
    columns = {column["name"] for column in inspector.get_columns("users")}

    assert "display_name" in columns
    assert "email" in columns
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && .venv/bin/pytest tests/test_auth_api.py -k "registration_by_default or profile_columns" -v`

Expected: FAIL，提示 `Settings` 缺少 `auth_enable_registration`，且 `users` 表缺少 `display_name` / `email` 列。

- [ ] **Step 3: 最小实现配置、schema、模型与 migration**

```python
# backend/app/config.py
class Settings(BaseSettings):
    auth_enable_registration: bool = True


# backend/app/models/user.py
class User(Base):
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)


# backend/app/schemas/auth.py
class AuthUserRead(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    last_login_at: Optional[datetime]
```

```python
# backend/alembic/versions/0004_add_user_profile_and_registration_flag.py
def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=320), nullable=True))

    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
    op.execute("UPDATE users SET email = username || '@local.invalid' WHERE email IS NULL")

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("display_name", existing_type=sa.String(length=200), nullable=False)
        batch_op.alter_column("email", existing_type=sa.String(length=320), nullable=False)
        batch_op.create_unique_constraint("uq_users_email", ["email"])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && .venv/bin/pytest tests/test_auth_api.py -k "registration_by_default or profile_columns" -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/alembic/versions/0004_add_user_profile_and_registration_flag.py backend/app/models/user.py backend/app/models/__init__.py backend/app/schemas/auth.py backend/app/config.py backend/tests/test_auth_api.py
git commit -m "feat: add registration settings and user profile fields"
```

### Task 2: 注册 API 与默认工作台初始化

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败的注册服务与 API 测试**

```python
def test_register_creates_user_session_and_default_workspace(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "new-user",
            "display_name": "New User",
            "email": "new@example.com",
            "password": "new-secret1",
            "confirm_password": "new-secret1",
            "create_default_workspace": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["username"] == "new-user"
    user = db_session.scalar(select(User).where(User.username == "new-user"))
    assert user is not None
    assert db_session.scalar(select(TaskProject).where(TaskProject.name == "学习")) is not None


def test_register_rejects_when_registration_disabled(client, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLE_REGISTRATION", "false")
    get_settings.cache_clear()

    response = client.post(
        "/api/auth/register",
        json={
            "username": "blocked",
            "display_name": "Blocked",
            "email": "blocked@example.com",
            "password": "blocked123",
            "confirm_password": "blocked123",
            "create_default_workspace": False,
        },
    )

    assert response.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && .venv/bin/pytest tests/test_auth_api.py -k "register_creates_user_session_and_default_workspace or register_rejects_when_registration_disabled" -v`

Expected: FAIL，提示 `/api/auth/register` 不存在。

- [ ] **Step 3: 最小实现注册 schema、服务逻辑和路由**

```python
# backend/app/schemas/auth.py
class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=8, max_length=255)
    create_default_workspace: bool = True
```

```python
# backend/app/services/auth_service.py
def register_user(self, payload: RegisterRequest) -> tuple[User, str, SessionRecord]:
    if not self.settings.auth_enable_registration:
        raise ValueError("注册功能已关闭")
    if payload.password != payload.confirm_password:
        raise ValueError("两次密码输入不一致")

    user = User(
        username=normalize_username(payload.username),
        display_name=payload.display_name.strip(),
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
        password_changed_at=utc_now(),
    )
    self.session.add(user)
    self.session.flush()
    if payload.create_default_workspace:
        self._create_default_workspace(user.id)
    return self._commit_user_with_new_session(user)
```

```python
# backend/app/api/auth.py
@router.post("/register", response_model=AuthUserRead)
def register(payload: RegisterRequest, response: Response, service: AuthService = Depends(get_auth_service), settings: Settings = Depends(get_settings)):
    try:
        user, session_token, _ = service.register_user(payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 403 if detail == "注册功能已关闭" else 400
        raise HTTPException(status_code=status_code, detail=detail)
    _set_session_cookie(response, settings=settings, session_token=session_token)
    return user
```

- [ ] **Step 4: 补重复用户名、重复邮箱、默认模板数量测试并全量运行认证测试**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && .venv/bin/pytest tests/test_auth_api.py -v`

Expected: PASS，新增覆盖重复用户名、重复邮箱、关闭注册、默认工作台初始化。

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/api/auth.py backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat: add registration api and workspace bootstrap"
```

### Task 3: 前端 API、AuthContext 与路由接入注册流

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/auth/AuthContext.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.test.jsx`

- [ ] **Step 1: 写失败的前端路由与注册状态测试**

```jsx
test("renders signup page when visiting /signup", async () => {
  renderAt("/signup");
  expect(await screen.findByRole("heading", { name: "创建账号" })).toBeInTheDocument();
});

test("register stores current user and navigates to completion step", async () => {
  renderAt("/signup");
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "new-user" } });
  fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "New User" } });
  fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "new@example.com" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "new-secret1" } });
  fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "new-secret1" } });
  fireEvent.click(screen.getByRole("button", { name: "下一步" }));

  await screen.findByText("初始化工作台");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/App.test.jsx`

Expected: FAIL，提示 `/signup` 未定义或缺少注册页元素。

- [ ] **Step 3: 最小实现 API 和认证上下文**

```javascript
// frontend/src/api/client.js
export async function register(payload) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


// frontend/src/auth/AuthContext.jsx
import { register as registerRequest } from "../api/client";

async function register(payload) {
  const currentUser = await registerRequest(payload);
  setUser(currentUser);
  setSessionExpired(false);
  return currentUser;
}
```

```jsx
// frontend/src/App.jsx
import SignupPage from "./pages/Signup";

<Route path="/signup" element={<SignupPage />} />
```

- [ ] **Step 4: 运行前端应用级测试**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/App.test.jsx`

Expected: PASS，`/signup` 路由和注册状态接线正常。

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/api/client.js frontend/src/auth/AuthContext.jsx frontend/src/App.jsx frontend/src/App.test.jsx
git commit -m "feat: wire signup flow into frontend auth state"
```

### Task 4: 实现登录页、注册页与账户页重构

**Files:**
- Create: `frontend/src/pages/Signup.jsx`
- Modify: `frontend/src/pages/Login.jsx`
- Modify: `frontend/src/pages/Login.test.jsx`
- Modify: `frontend/src/pages/Account.jsx`
- Modify: `frontend/src/pages/Account.test.jsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: 写失败的页面交互测试**

```jsx
test("login page links to signup", async () => {
  renderLogin();
  expect(screen.getByRole("link", { name: "创建账号" })).toHaveAttribute("href", "/signup");
});

test("signup completes three-step flow", async () => {
  render(<SignupPage />, { wrapper: MemoryRouter });
  fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "new-user" } });
  fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "New User" } });
  fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "new@example.com" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: "new-secret1" } });
  fireEvent.change(screen.getByLabelText("确认密码"), { target: { value: "new-secret1" } });
  fireEvent.click(screen.getByRole("button", { name: "下一步" }));
  fireEvent.click(screen.getByRole("button", { name: "创建账号" }));

  expect(await screen.findByText("账号创建成功")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "进入今日面板" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Login.test.jsx src/pages/Account.test.jsx`

Expected: FAIL，提示缺少注册链接、缺少注册页流程、账户页标题结构不匹配。

- [ ] **Step 3: 实现 auth 页面与视觉重构**

```jsx
// frontend/src/pages/Login.jsx
return (
  <div className="auth-shell">
    <section className="auth-hero">
      <p className="auth-eyebrow">Reward Todo</p>
      <h1>登录你的任务账本</h1>
      <p className="auth-description">计划任务，完成记奖，支出回收，都在一个工作台里继续。</p>
      <ul className="auth-points">
        <li>计划任务</li>
        <li>完成记奖</li>
        <li>支出回收</li>
      </ul>
    </section>
    <form className="auth-panel" onSubmit={handleSubmit}>
      ...
      <p className="auth-switch">没有账号？<Link to="/signup">创建账号</Link></p>
    </form>
  </div>
);
```

```jsx
// frontend/src/pages/Signup.jsx
const steps = ["basic", "workspace", "done"];

if (step === "workspace") {
  return (
    <>
      <h1>初始化工作台</h1>
      <label>
        <input type="checkbox" checked={createDefaultWorkspace} onChange={...} />
        创建默认项目与模板
      </label>
      <button type="button" onClick={handleRegister}>创建账号</button>
    </>
  );
}
```

```css
/* frontend/src/styles.css */
:root {
  font-family: "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
  --auth-bg: #f5f7f4;
  --auth-panel: #ffffff;
  --auth-ink: #1f2933;
  --auth-accent: #c9723f;
}

.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(320px, 1.1fr) minmax(360px, 460px);
}
```

- [ ] **Step 4: 运行页面测试和样式相关回归**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run src/pages/Login.test.jsx src/pages/Account.test.jsx src/App.test.jsx`

Expected: PASS，登录页、注册页、账户页文本与流程行为符合新结构。

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add frontend/src/pages/Signup.jsx frontend/src/pages/Login.jsx frontend/src/pages/Login.test.jsx frontend/src/pages/Account.jsx frontend/src/pages/Account.test.jsx frontend/src/styles.css
git commit -m "feat: redesign auth pages and account layout"
```

### Task 5: 更新启动说明并做端到端验证

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docker-compose.yml`

- [ ] **Step 1: 写失败的文档与 compose 兼容检查**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
rg -n "APP_BASIC_AUTH|AUTH_ENABLE_REGISTRATION|AUTH_INITIAL_USERNAME|AUTH_INITIAL_PASSWORD" .env.example README.md docker-compose.yml
```

Expected: 先记录当前缺口，例如 `.env.example` 未说明注册开关，README 未解释完成页和注册入口，`docker-compose.yml` 仍只体现旧逻辑时需要调整。

- [ ] **Step 2: 更新示例环境文件、README 与 compose 注释**

```dotenv
# .env.example
AUTH_INITIAL_USERNAME=reward
AUTH_INITIAL_PASSWORD=replace-me
AUTH_ENABLE_REGISTRATION=true
```

```yaml
# docker-compose.yml
environment:
  AUTH_INITIAL_USERNAME: ${AUTH_INITIAL_USERNAME:-${APP_BASIC_AUTH_USER:-reward}}
  AUTH_INITIAL_PASSWORD: ${AUTH_INITIAL_PASSWORD:-${APP_BASIC_AUTH_PASSWORD:-replace-me}}
  AUTH_ENABLE_REGISTRATION: ${AUTH_ENABLE_REGISTRATION:-true}
```

```md
# README.md
1. 复制 `.env.example` 为 `.env`
2. 运行 `docker compose up --build`
3. 直接使用 `AUTH_INITIAL_*` 登录，或从 `/login` 进入 `/signup` 自助注册
```

- [ ] **Step 3: 跑后端、前端与 compose 验证**

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/backend && .venv/bin/pytest tests/test_auth_api.py tests/test_public_api.py -v`

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo/frontend && npm test -- --run`

Run: `cd /Users/wuzhuoyi/Desktop/code/reward-todo && docker compose up --build -d`

Run: `curl -i http://localhost:8088/api/public/health`

Expected:
- Pytest PASS
- Vitest PASS
- Compose 容器全部 healthy / running
- `GET /api/public/health` 返回 `200 OK`

- [ ] **Step 4: 手工验证注册与登录**

```bash
open http://localhost:8088/login
```

Expected:
- 可见“创建账号”入口
- 注册新账号后进入完成页
- 点击“进入今日面板”后可看到默认项目与模板
- 初始账号 `reward` 仍可登录

- [ ] **Step 5: 提交**

```bash
cd /Users/wuzhuoyi/Desktop/code/reward-todo
git add .env.example README.md docker-compose.yml
git commit -m "docs: document registration-enabled startup flow"
```
