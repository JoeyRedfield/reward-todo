# Reward Todo

个人任务板 + 奖励账本的独立仓库骨架。

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

`.env.example` 已包含默认本地登录账号；首次 `docker compose up` 后即可直接登录：

- 用户名：`reward`
- 密码：`replace-me`

如果你本地已经有旧版 `.env`，其中仍使用：

- `APP_BASIC_AUTH_USER`
- `APP_BASIC_AUTH_PASSWORD`

当前仓库的三条链路都会兼容这两个旧键：

- `docker compose up`
- `backend` 直接启动
- `alembic upgrade head`

但建议尽快迁移到新的：

- `AUTH_INITIAL_USERNAME`
- `AUTH_INITIAL_PASSWORD`

另外，`ezbookkeeping` 风格的 Agent / MCP 能力开关也已落地到 `.env`：

- `AUTH_ENABLE_API_TOKENS=true`
- `AUTH_ENABLE_MCP=true`

现在前端也已经提供注册入口；启动后你可以二选一：

- 使用默认引导账号直接登录
- 打开 `http://localhost:8088/signup` 创建新账号，注册完成后会自动进入当前会话

启动后如需演示数据，再另开一个终端执行：

```bash
cd backend
./.venv/bin/alembic upgrade head
python3 scripts/seed_demo_data.py
```

如果当前本地库已经由旧版 `create_all()` 创建过表，先标记到当前 revision，再继续使用 Alembic：

```bash
cd backend
./.venv/bin/alembic stamp head
```

从 `lifeboard` 导入历史任务奖励数据：

```bash
cd backend
./.venv/bin/python scripts/migrate_from_lifeboard.py --source-db-url 'postgresql+asyncpg://lifeboard:lifeboard@localhost:5432/lifeboard'
```

启动后访问：

- `http://localhost:8088/`：统一入口，默认使用应用内登录
- `http://localhost:8088/signup`：注册新账号
- `http://localhost:8088/api/public/health`：无需认证的后端健康检查

默认应用内登录账号：

- 用户名：`reward`
- 密码：`replace-me`

可选的额外入口保护：

- 设置 `.env` 中 `ENABLE_BASIC_AUTH=true` 后，Nginx 会重新启用 Basic Auth 作为额外前置保护。
- Basic Auth 用户文件来自 [`proxy/.htpasswd`](/Users/wuzhuoyi/Desktop/code/reward-todo/proxy/.htpasswd)。

说明：

- 当前仓库已包含待办-奖励最小功能链路：后端 API、前端三页、Postgres、Nginx 单入口，以及应用内登录。
- `docker compose up` 现在会在后端容器启动时先执行 `alembic upgrade head`，再启动 API，因此全新库和历史开发库都能自动补齐 schema。
- 对全新本地库，应用启动时会自动建表并初始化默认登录账号，因此仅验证登录不需要先手动迁移。
- 初次启动默认是空库，执行 `backend/scripts/seed_demo_data.py` 后即可在前端看到示例数据。
- Alembic 已补齐；对全新数据库请先 `upgrade head`，对历史本地开发库请先 `stamp head`，避免重复建表报错。
- 如需运维重置本地账号密码，可执行 `cd backend && python3 scripts/reset_password.py --password 'new-password'`。

## 账号能力

当前账号相关接口分成三类：

- 应用登录会话：`/api/auth/*`
- 账号资料、会话、令牌管理：`/api/account/*`
- Agent / MCP 访问入口：Bearer Token 调业务 API，或访问 `/mcp`

已提供的主要接口：

- `GET /api/account/profile`：查看当前账号资料，以及服务端暴露给前端的能力开关（`api_token_enabled` / `mcp_enabled`）
- `GET /api/account/sessions`：查看当前账号所有登录会话
- `DELETE /api/account/sessions`：退出当前账号的其他所有会话
- `DELETE /api/account/sessions/{session_id}`：撤销某个会话
- `GET /api/account/tokens`：查看当前账号生成的 API / MCP token
- `POST /api/account/tokens`：生成新 token
- `DELETE /api/account/tokens/{token_id}`：撤销 token

## Agent / API Token

登录 Web 界面后，可以通过 `POST /api/account/tokens` 生成 `token_type=api` 的 token。前端账号页会先通过 `GET /api/account/profile` 判断 `api_token_enabled` 是否开启；如果服务端关闭了这个能力，前端会隐藏该选项，后端也会拒绝生成请求。

返回结果会带：

- `token`：实际 Bearer Token
- `api_base_url`：当前 API 基地址，默认是 `http://localhost:8088/api`

`POST /api/account/tokens` 当前支持：

- `expires_in_seconds`：优先级最高，支持秒级过期时间
- `expires_in_seconds=0`：生成永不过期 token
- `expires_in_days`：兼容旧调用方式

生成后，Agent 或其他客户端可直接调用现有业务接口，例如：

```bash
curl -H "Authorization: Bearer <api-token>" \
  http://localhost:8088/api/task-projects
```

这条通路与前端当前使用的 HTTP API 相同，只是把 cookie 登录替换成 Bearer Token。

常见 Agent 调用示例：

```bash
curl -H "Authorization: Bearer <api-token>" \
  http://localhost:8088/api/daily-tasks?date=2026-06-22
```

如果你希望像 `ezbookkeeping` 一样给 Agent 一条现成的脚本入口，仓库内已经提供了 skill：

- Skill 文档：[`skills/reward-todo/SKILL.md`](/Users/wuzhuoyi/Desktop/code/reward-todo/skills/reward-todo/SKILL.md)
- Shell 脚本：[`skills/reward-todo/scripts/rewardtools.sh`](/Users/wuzhuoyi/Desktop/code/reward-todo/skills/reward-todo/scripts/rewardtools.sh)

初始化方式：

```bash
export REWARDTOOL_SERVER_BASEURL="http://localhost:8088/api"
export REWARDTOOL_TOKEN="<api-token>"
```

常见命令：

```bash
sh skills/reward-todo/scripts/rewardtools.sh list
sh skills/reward-todo/scripts/rewardtools.sh projects-list
sh skills/reward-todo/scripts/rewardtools.sh projects-update --project-id 1 --name "深度写作"
sh skills/reward-todo/scripts/rewardtools.sh tasks-list --date 2026-06-22
sh skills/reward-todo/scripts/rewardtools.sh rewards-summary
```

## MCP

登录 Web 界面后，可以通过 `POST /api/account/tokens` 生成 `token_type=mcp` 的 token。前端账号页会先通过 `GET /api/account/profile` 判断 `mcp_enabled` 是否开启；如果服务端关闭了这个能力，前端会隐藏该选项，后端也会拒绝生成请求，同时 `/mcp` 入口也会直接返回错误。

返回结果会带：

- `token`：MCP Bearer Token
- `mcp_url`：当前 MCP 入口，默认是 `http://localhost:8088/mcp`

当前已实现的最小 MCP JSON-RPC 能力：

- `initialize`
- `resources/list`
- `resources/read`
- `tools/list`
- `tools/call`
- `ping`

当前内置的 MCP resources：

- `reward-todo://projects`
- `reward-todo://daily-tasks/today`
- `reward-todo://reward-summary/today`
- `reward-todo://reward-ledger/recent`
- `reward-todo://account/profile`

当前内置的 MCP tools：

- `get_reward_summary`
- `list_task_projects`
- `list_task_templates`
- `list_daily_tasks`
- `list_reward_ledger`
- `create_project`
- `update_project`
- `create_task_template`
- `update_task_template`
- `create_daily_task`
- `complete_daily_task`
- `reopen_daily_task`
- `spend_reward`

如果你要给支持 MCP 的桌面客户端或 Agent 配置服务，可以直接使用下面的配置片段：

```json
{
  "mcpServers": {
    "reward-todo-mcp": {
      "type": "streamable-http",
      "url": "http://localhost:8088/mcp",
      "headers": {
        "Authorization": "Bearer <mcp-token>"
      }
    }
  }
}
```

请求示例：

```bash
curl http://localhost:8088/mcp \
  -H "Authorization: Bearer <mcp-token>" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_reward_summary",
      "arguments": {
        "date": "2026-06-20"
      }
    }
  }'
```
