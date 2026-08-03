## Why

当前工作台和 AI 对话接口允许匿名访问，消息历史只存在于浏览器内存，无法建立稳定的用户、项目和对话归属。开发环境需要一个范围受控的固定用户登录方案，并把生成过程迁移为可恢复、可停止且具有明确项目边界的持久化对话。

## What Changes

- 新增仅支持固定用户 `developer@local.test` 的邮箱密码登录；密码只由必需的 `API_AUTH_FIXED_USER_PASSWORD` 环境变量提供，不提供注册、找回密码或第三方登录。
- 新增数据库登录会话：每次登录创建独立会话，固定有效期 7 天且不滑动续期；允许多浏览器同时登录，退出仅撤销当前会话。
- 明确公开与受保护边界：首页、登录页、健康检查和登录接口公开；工作台、当前用户、退出、项目及生成接口必须登录。
- 新增用户所属项目、完整消息历史和生成尝试持久化；一个项目对应一条 AI 对话，首次发送非空消息时才创建项目，并使用 `/workspace/{projectId}` 恢复。
- **BREAKING** 移除匿名 `POST /api/chat`，改为受认证的项目读取接口和项目级 generation SSE 接口。
- 用户消息在调用 AI 前保存；数据库保留完整历史，AI 只接收最近的受限完整对话轮次和当前目标用户消息，不生成或保存摘要。
- 同一项目拒绝并发生成；前台 SSE 支持停止和显式重新生成，不设后台队列、不自动重试，也不保存未完成的助手回复。
- 新增可回滚 PostgreSQL SQL migration，不引入 migration runner。

## Capabilities

### New Capabilities

- `user-authentication`: 固定用户登录、7 天数据库会话、当前用户、单会话退出和公开/受保护访问边界。
- `project-conversations`: 用户项目、完整消息历史、生成尝试、首次发送创建项目、项目恢复、并发控制、停止和显式重新生成。

### Modified Capabilities

- `ai-chat`: 将匿名 JSON 对话改为受认证的项目级 SSE 生成，并限定上游只使用最近的完整轮次。
- `go-api-runtime`: 增加必需的固定用户密码运行配置，并继续禁止敏感配置进入示例文件。

## Impact

- 后端：认证、项目和生成领域，AI 流式客户端，Gin 路由、强类型配置及相关测试。
- 前端：首页到登录/工作台的跳转、登录页、受保护工作台、`/workspace/{projectId}`、SSE 客户端、停止和重新生成状态。
- 数据库：通过一组配对的 up/down SQL migration 新增用户、登录会话、项目、消息和生成尝试结构及固定用户资料。
- 契约：新增 `user-authentication` 与 `project-conversations`，修改 `ai-chat` 与 `go-api-runtime`。
- 依赖与基础设施：预计不新增运行时依赖，不新增队列、任务消费者或 migration runner。
