# Reward Todo 登录功能完善设计

## 背景

当前项目只有两层与认证相关的能力：

- 站点入口依赖 `nginx Basic Auth`
- `/api/public/*` 只读接口依赖 Bearer Token

应用本身没有用户模型、登录会话、登录页、路由守卫或业务接口鉴权。前端页面和 `/api/*` 业务接口当前都可直接访问。这不满足“应用内登录，逐步替代 nginx Basic Auth 作为主入口鉴权”的目标。

## 目标

- 建立真正的应用内登录体系，覆盖前端页面和 `/api/*` 业务接口
- 保持 `/api/public/health` 匿名公开
- 保持其余 `/api/public/*` 继续走现有 Bearer Token 只读模式
- 支持单用户、本地账号密码、后端自管
- 支持登录、登出、查询当前登录态、已登录后修改密码
- 使用 `HttpOnly` cookie 承载登录态
- 支持当前会话登出、改密码使全部旧会话失效
- 提供本地运维密码重置入口
- 为认证层补齐关键测试

## 非目标

- 不做多用户
- 不接入第三方 OAuth / OIDC
- 不做注册、邀请、找回密码、邮箱验证
- 不做验证码和登录失败限流
- 不为现有 `/api/public/*` 只读接口改造鉴权模式
- 不在本轮删除 `nginx Basic Auth`，仅将其改为可选外层保护

## 方案概述

采用数据库会话方案：

- 新增 `users` 表保存单用户账号和密码哈希
- 新增 `sessions` 表保存可撤销的登录会话
- cookie 中只存随机 session token
- 数据库存 token 哈希，不存原始 token
- 后端新增独立 `auth` API 和统一鉴权依赖
- 前端新增认证上下文、登录页、路由守卫、全局 `401` 处理和账户入口

这样可以满足以下行为：

- 登出只影响当前会话
- 改密码会使该用户所有旧会话失效
- 会话支持 7 天有效期和滑动续期
- 受保护接口的访问边界清晰

## 当前状态与迁移原则

### 现有访问分层

当前系统已有三类入口：

1. `nginx Basic Auth` 保护的整站入口
2. `/api/public/health` 匿名健康检查
3. 其余 `/api/public/*` Bearer Token 只读接口

### 迁移后分层

迁移后继续保持以下分层：

1. 匿名公开：`/api/public/health`
2. Token 公开只读：现有其他 `/api/public/*`
3. 登录后访问：前端页面与现有 `/api/*` 业务接口

`/api/health` 将纳入登录保护范围，不再作为匿名健康检查入口。

### 与 Basic Auth 的关系

本轮实现后，应用内登录将独立成立，不再依赖 Basic Auth 才能进行业务访问。`nginx Basic Auth` 保留为可选外层保护，通过配置启停；默认部署可以暂时继续开启，用于平滑迁移。

## 数据模型设计

### `users`

新增单用户表，字段如下：

- `id`
- `username`
- `password_hash`
- `created_at`
- `updated_at`
- `password_changed_at`
- `last_login_at`

约束与规则：

- 当前系统只允许存在一个活跃用户
- `username` 作为稳定登录标识，不允许在应用内修改
- `username` 入库前统一转小写
- `password_hash` 使用 `bcrypt`
- `password_changed_at` 用于审计和会话失效判定

### `sessions`

新增会话表，字段如下：

- `id`
- `user_id`
- `session_token_hash`
- `created_at`
- `updated_at`
- `expires_at`
- `last_seen_at`

约束与规则：

- 每次登录创建一条新会话
- cookie 保存原始随机 token
- 数据库只保存 token 哈希
- `expires_at` 表示绝对过期时间
- `last_seen_at` 用于滑动续期与会话活跃审计
- 过期会话在访问时惰性清理

## 配置设计

后端配置新增以下环境变量：

- `AUTH_INITIAL_USERNAME`
- `AUTH_INITIAL_PASSWORD`
- `AUTH_SESSION_COOKIE_NAME`
- `AUTH_SESSION_DAYS`
- `AUTH_COOKIE_SECURE`
- `AUTH_COOKIE_SAMESITE`
- `ENABLE_BASIC_AUTH`

约束：

- 非测试环境缺少 `AUTH_INITIAL_USERNAME` 或 `AUTH_INITIAL_PASSWORD` 时，后端启动失败
- 初始账号配置只用于首次初始化
- 当数据库中已存在用户时，不再自动用环境变量覆盖用户名或密码
- `AUTH_COOKIE_SAMESITE` 固定使用 `Lax`
- 本地开发允许 `AUTH_COOKIE_SECURE=false`
- 生产环境要求 `AUTH_COOKIE_SECURE=true`
- `ENABLE_BASIC_AUTH` 用于驱动代理层是否启用 Basic Auth，不由后端业务代码消费

## 启动与初始化

应用启动时执行“确保初始用户存在”的逻辑：

1. 查询 `users` 表
2. 若无用户，则读取初始用户名和密码并创建该用户
3. 若已有用户，则跳过，不做覆盖

初始化逻辑不负责重置密码，也不负责同步用户名变更。密码恢复通过单独的运维命令处理，而非启动自动覆盖。

## 后端组件设计

### 新增模块

后端新增以下模块：

- `app/models/user.py`
- `app/models/session.py`
- `app/services/auth_service.py`
- `app/security.py`
- `app/api/auth.py`

### `security.py`

负责以下基础能力：

- 用户名归一化
- 生成随机 session token
- 计算 token 哈希
- `bcrypt` 密码哈希与校验
- cookie 参数构造

### `auth_service.py`

负责以下认证业务：

- 初始化单用户
- 校验用户名与密码
- 创建会话
- 读取当前会话与当前用户
- 滑动续期
- 删除当前会话
- 删除某用户全部会话
- 修改密码
- 惰性清理过期会话

### 统一鉴权依赖

新增 `require_authenticated_user` 依赖，作用如下：

- 从 cookie 中读取 session token
- 计算 token 哈希并查找会话
- 若会话不存在或过期，返回 `401`
- 若用户不存在，返回 `401`
- 校验通过后返回当前用户
- 在成功请求时更新会话活跃时间并视需要续期

现有 `/api/*` 业务路由统一接入此依赖；`/api/public/*` 不接入。

## API 设计

### `POST /api/auth/login`

请求体：

- `username`
- `password`

行为：

- 用户名归一化为小写
- 用户不存在或密码错误时统一返回 `401`
- 错误文案统一为“用户名或密码错误”
- 登录成功后：
  - 创建新 session
  - 更新 `last_login_at`
  - 设置 `HttpOnly` cookie
  - 返回当前用户的最小公开信息

### `POST /api/auth/logout`

行为：

- 读取当前 cookie 对应会话
- 删除当前会话记录
- 清除 cookie
- 即使会话已不存在，也返回成功语义，避免前端复杂化

### `GET /api/auth/me`

行为：

- 根据 cookie 返回当前登录用户
- 未登录返回 `401`
- 用于前端启动时初始化登录态

### `POST /api/auth/change-password`

请求体：

- `current_password`
- `new_password`
- `confirm_new_password`

规则：

- 当前密码必须正确
- 新密码长度至少 8 位
- 新密码与确认密码必须一致

成功后：

- 更新 `password_hash`
- 更新 `password_changed_at`
- 删除该用户全部旧会话
- 重新为当前请求签发一个新会话并写入 cookie

这样当前浏览器保持登录，其他浏览器或旧标签页中的旧会话全部失效。

## Cookie 与会话策略

cookie 统一策略：

- `HttpOnly=true`
- `SameSite=Lax`
- `Secure` 在生产开启，本地开发可关闭
- 路径作用域为 `/`
- Max-Age 为 7 天

会话策略：

- 默认有效期 7 天
- 每次通过鉴权的请求执行滑动续期
- 登出只删除当前会话
- 改密码删除全部旧会话并补发当前新会话
- 过期会话通过鉴权时惰性清理

## 前端设计

### 路由结构

新增 `/login` 页面，并引入受保护路由模型：

- 未登录访问 `/today`、`/projects`、`/rewards` 时重定向到 `/login`
- 查询参数保存原目标地址，用于登录成功后回跳
- 已登录访问 `/login` 时直接跳转回目标页，若无目标则跳 `/today`

### 认证状态管理

前端新增 `AuthProvider`，负责：

- 启动时请求 `GET /api/auth/me`
- 保存当前用户、认证加载状态、未认证状态
- 暴露 `login`、`logout`、`refreshCurrentUser` 等能力

由于 cookie 是 `HttpOnly`，前端不保存 token，也不判断 token 内容，只相信 `/api/auth/me` 的返回结果。

### 全局请求处理

现有 `frontend/src/api/client.js` 需要补两个变化：

- fetch 请求显式开启携带 cookie
- 对 `401` 做统一识别，交由前端认证层处理

前端在收到 `401` 时：

- 清空内存中的当前用户
- 若当前位于受保护页面，则提示“登录已失效，请重新登录”
- 跳转到 `/login` 并带上当前地址作为回跳目标

### 登录页

登录页保持极简，只包含：

- 用户名输入框
- 密码输入框
- 提交按钮
- 提交中状态
- 登录失败错误提示

不包含：

- 注册
- 忘记密码
- 营销文案

### 已登录账户入口

在现有侧边栏中新增固定账户区，显示：

- 当前用户名
- 修改密码入口
- 登出入口

修改密码使用轻量弹层表单，但必须位于已登录应用内入口中，不单独做独立路由页。

## 修改密码交互

修改密码交互要求：

- 输入当前密码
- 输入新密码
- 再次确认新密码

校验规则：

- 新密码最少 8 位
- 两次新密码输入必须一致
- 用户名不可编辑

成功后前端应：

- 显示成功提示
- 保持当前页面可继续使用
- 后续任何旧标签页或其他浏览器窗口会在下一次请求时收到 `401`

## 业务接口接入策略

现有 `/api/*` 业务接口统一接入登录保护，包括：

- `/api/health`
- `/api/task-projects`
- `/api/task-templates`
- `/api/daily-tasks`
- `/api/rewards/*`

这部分不改变业务接口语义，只增加统一鉴权依赖。

## 运维重置密码

新增本地运维脚本：

- `backend/scripts/reset_password.py`

能力要求：

- 接收新密码参数
- 定位当前唯一用户
- 重置密码哈希
- 更新 `password_changed_at`
- 删除该用户全部现有会话

此入口只用于本地运维恢复，不在前端暴露。

## 测试设计

### 后端测试

新增或扩展以下测试：

- 未登录访问受保护接口返回 `401`
- 登录成功可访问 `/api/auth/me`
- 登录失败统一返回“用户名或密码错误”
- 登出后当前会话失效
- 改密码后旧密码不可登录
- 改密码后新密码可登录
- 改密码后旧会话失效
- `/api/public/health` 仍匿名可访问
- 其他 `/api/public/*` 继续要求 Bearer Token

### 前端测试

新增或扩展以下测试：

- 未登录访问业务路由时跳转 `/login`
- 登录成功后回跳原目标页
- 已登录访问 `/login` 时自动跳走
- 会话失效后显示提示并回登录页
- 侧边栏显示用户名与登出入口
- 修改密码成功后当前登录态保持有效

## 安全边界

本轮安全基线如下：

- 密码仅以 `bcrypt` 哈希形式保存
- session token 原文不落库
- cookie 使用 `HttpOnly`
- 不开放跨域
- 依赖同源部署与 `SameSite=Lax` 作为当前阶段 CSRF 基线

本轮明确不做：

- CSRF token
- 登录限流
- 多因素认证
- 完整认证审计日志表

## 实施顺序建议

1. 增加数据模型与 Alembic 迁移
2. 增加配置与初始化逻辑
3. 实现认证服务与鉴权依赖
4. 增加 `auth` API
5. 为现有 `/api/*` 业务接口接入登录保护
6. 增加密码重置脚本
7. 前端增加认证上下文与路由守卫
8. 增加登录页和侧边栏账户区
9. 增加修改密码交互
10. 补齐后端和前端测试
11. 调整 README 和部署说明

## 验收标准

满足以下条件视为本设计完成：

- 在关闭或绕过 Basic Auth 的前提下，应用内登录仍可独立完成完整访问控制
- 未登录无法访问前端业务页面和 `/api/*` 业务接口
- 登录后可以正常访问现有任务、项目、奖励功能
- 登出只影响当前会话
- 改密码后其他旧会话全部失效，当前会话保持可用
- `/api/public/health` 继续匿名可用
- 现有 Bearer Token 只读接口行为不变
- 认证关键路径拥有自动化测试覆盖
