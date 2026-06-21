# Reward Todo

个人任务板 + 奖励账本的独立仓库骨架。

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

启动后另开一个终端，执行迁移并灌入演示数据：

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

- `http://localhost:8088/`：统一入口，需要 Basic Auth
- `http://localhost:8088/api/public/health`：无需认证的后端健康检查

默认占位认证账号：

- 用户名：`reward`
- 密码：`replace-me`

说明：

- 当前仓库已包含待办-奖励最小功能链路：后端 API、前端三页、Postgres、Nginx 单入口。
- 初次启动默认是空库，执行 `backend/scripts/seed_demo_data.py` 后即可在前端看到示例数据。
- Alembic 已补齐；对全新数据库请先 `upgrade head`，对历史本地开发库请先 `stamp head`，避免重复建表报错。
