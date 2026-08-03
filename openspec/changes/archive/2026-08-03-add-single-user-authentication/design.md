## Context

基线中的 Web 工作台把消息历史保存在 Zustand 内存，并将完整消息数组提交给匿名 `POST /api/chat`；API 一次性调用上游并返回 JSON。API 已使用 PostgreSQL 和 GORM，但基线没有用户、登录会话、项目、消息或 migration。此次变更跨越 Next.js 路由、Go HTTP 边界、AI 上游流式调用和 PostgreSQL 数据模型，同时受固定单用户、无后台任务和仅新增 SQL migration 的范围约束。

## Goals / Non-Goals

**Goals:**

- 提供固定用户的邮箱密码登录、独立数据库登录会话和当前会话退出。
- 让项目、完整消息与生成尝试归属于用户，并通过项目地址恢复对话。
- 用户消息先持久化，再以前台 SSE 流式生成；完整成功后才保存助手消息。
- 同一项目串行生成，支持用户停止和针对同一用户消息显式重新生成。
- 数据库保存全部完整历史，上游仅接收最近的受限完整轮次，不做摘要。

**Non-Goals:**

- 注册、找回或修改密码、第三方登录、多用户或权限管理、安全增强。
- 项目新建以外的项目管理功能，以及其余失败状态的完整界面设计。
- 后台队列、任务消费者、自动重试、断线续传或保存未完成的助手文本。
- migration runner、自动迁移或修改已经应用的 migration。

## Decisions

### 固定用户凭据与数据库登录会话

Migration 只写入固定用户的非敏感资料：稳定 ID、邮箱 `developer@local.test` 和显示名称。API 从必需的 `API_AUTH_FIXED_USER_PASSWORD` 读取密码并在缺失时停止启动；密码不进入数据库、migration、示例配置、响应或日志。

登录成功后生成高熵随机令牌，只把令牌摘要、用户 ID、创建时间和固定的 `expires_at = created_at + 7 days` 写入 `user_sessions`，原始令牌通过 HttpOnly Cookie 返回。认证查询只校验现有且未过期的记录，不更新过期时间。每次登录新增记录，因此多浏览器会话互不影响；退出按当前 Cookie 的令牌摘要撤销单条记录。

选择数据库会话而非 JWT，是因为现有 PostgreSQL 能直接表达可撤销的当前会话，并满足“退出仅影响当前浏览器”。JWT 需要额外撤销状态，不能简化当前约束。

### 公开路由与认证边界

Web 的 `/` 与 `/login` 公开；`/workspace` 和 `/workspace/{projectId}` 在服务端入口检查当前用户，未登录时跳转 `/login` 并保留原目标地址。首页 prompt 和未发送草稿只保存在当前标签页，登录后恢复，不进入 URL 中的长期历史或数据库。

API 的 `/health/live`、`/health/ready` 和 `POST /api/auth/login` 公开。`GET /api/auth/me`、`POST /api/auth/logout`、所有 `/api/projects` 与 generation 路由统一经过认证中间件。旧 `POST /api/chat` 不保留兼容处理器。

### 项目、消息和生成尝试模型

`projects` 归属于用户，一个项目就是一条 AI 对话。`POST /api/projects` 同时接收首条非空用户消息，并在一个事务中创建项目、用户消息和运行中的生成尝试；因此访问空白 `/workspace` 不会留下空项目。创建成功后 Web 立即将地址替换为 `/workspace/{projectId}`。

`messages` 保存项目中完整的 user 或 assistant 消息。`generation_attempts` 关联目标用户消息，并记录 `running`、`completed`、`failed` 或 `interrupted`、稳定错误码、租约时间，以及成功时关联的助手消息。用户消息在上游调用前提交；助手文本只在上游完整结束后一次性写入，并与 attempt 完成状态在同一事务提交。

生成尝试与消息分离，可以保留失败、中断和重新生成记录，同时保证 SSE 临时文本不会伪装成消息。替代方案是把失败状态放在消息行上，但会混淆“完整历史”与执行状态。

### 项目与 generation HTTP/SSE 契约

采用以下受认证接口：

- `GET /api/projects`：返回当前用户最近更新的 20 个项目。
- `POST /api/projects`：提交首条用户消息，创建项目并启动 SSE 生成。
- `GET /api/projects/{projectId}`：返回项目和全部完整消息。
- `POST /api/projects/{projectId}/generations`：保存新的用户消息并启动 SSE 生成。
- `POST /api/projects/{projectId}/messages/{messageId}/generations`：针对未获得助手消息的同一用户消息显式重新生成。
- `POST /api/projects/{projectId}/generations/{generationId}/stop`：停止当前运行中的生成尝试；已结束时按当前状态幂等返回。

创建与后续生成请求携带稳定的 `client_message_id`。同一项目重复提交相同标识时不重复插入用户消息或 attempt，而是返回现有状态；这只用于请求幂等，不触发自动重试。不同标识遇到运行中生成时返回 `409 generation_in_progress`，且不保存第二条消息。

校验、认证、归属或并发错误发生在建立 SSE 前时使用稳定 JSON 错误。建立流后依次发送 `generation`、零到多个 `delta`，以及单个终态 `completed`、`failed` 或 `interrupted` 事件。`generation` 包含项目、用户消息和生成尝试标识；`completed` 包含已持久化的完整助手消息。SSE 只是当前请求的展示通道，项目读取结果才是刷新恢复的事实来源。

### 停止、断开与前台执行

生成在发起 SSE 的 HTTP 请求内执行，不移交后台任务。服务维护当前进程内运行 attempt 到取消函数的短期映射，供 stop 接口触发取消；浏览器主动停止时同时调用 stop 并关闭本地流。请求断开、刷新、显式停止、上游取消或服务关闭都会取消上游上下文，并把仍为 `running` 的 attempt 转为 `interrupted`，不保存已转发的临时文本。

不设置后台队列、不自动重试，也不在断线后继续生成。显式重新生成必须由用户发起，复用原用户消息并创建新的 attempt。对已经有被采纳助手消息的用户消息拒绝重新生成，避免一条用户消息对应多个助手消息。

### 项目内串行化与异常租约

数据库用“每个项目最多一个 `running` attempt”的部分唯一索引作为最终并发保证，业务事务在插入新用户消息前先检查运行状态。若运行 attempt 的租约已经过期，下一次生成命令先将其转为 `interrupted`，再尝试获取生成权；租约仅用于 API 异常退出后的解锁，不用于后台续跑。

项目和 generation 查询始终同时过滤当前用户 ID 与项目 ID。访问其他用户的项目统一返回 `404 not_found`，不暴露资源是否存在。

### 完整历史与受限完整轮次

数据库读取项目时返回按稳定顺序排列的全部完整消息，不删除、不摘要。每个完整对话轮次由目标用户消息和该次成功 attempt 关联的助手消息组成；失败、中断、运行中 attempt 的临时文本以及尚无助手消息的用户消息都不是完整轮次。

调用上游时，从目标用户消息之前的历史中由新到旧选取最多 24 个完整轮次，再按原时间顺序排列并追加本次目标用户消息，最多形成 49 条消息。达到服务端总内容上限时只移除最旧的整个轮次，不截断单条消息、不拆分轮次、不生成摘要；本次目标用户消息始终保留。相比直接截取最近 50 条消息，此规则不会以孤立 assistant 消息开头，也不会把失败轮次送入 AI。

### Web 状态与恢复

`/workspace` 表示尚无项目的新对话；首次 SSE 的 `generation` 事件返回项目 ID 后，Web 替换为 `/workspace/{projectId}`。已有项目页先读取服务端完整历史，再允许发送。流式 delta 只存在于当前页面的临时状态；收到 `completed` 后用服务端消息替换临时文本，失败、中断或刷新则丢弃临时助手文本并保留已保存的用户消息。

首页 prompt、登录前目标地址和工作台草稿使用当前标签页的 `sessionStorage`，避免跨浏览器共享或创建空项目。未认证响应统一回到登录页；登录成功后先恢复原目标地址，再恢复未发送草稿或首条 prompt。

## Risks / Trade-offs

- [浏览器断开或刷新会停止生成] → 用户消息和中断 attempt 已持久化，用户可显式重新生成。
- [SSE 已展示文本但最终数据库提交失败] → 客户端只把 `completed` 中的持久化消息视为完成，其他临时文本在结束或刷新时丢弃。
- [API 进程崩溃无法执行中断清理] → attempt 租约过期后由下一次生成命令转为中断，避免永久占用项目。
- [进程内 stop 映射不跨实例] → 当前部署按前台请求执行；数据库状态和租约仍是并发事实来源，多实例主动停止协调不在本次范围。
- [固定密码来自环境] → 缺失时 API 启动失败，仓库不提供默认值或真实示例。
- [down migration 会删除本功能数据] → 回滚前先部署兼容旧结构的应用，并人工确认允许删除开发期项目与会话数据。

## Migration Plan

1. 审查并显式执行新增 up migration，创建用户、登录会话、项目、消息、生成尝试、约束和固定用户资料。
2. 在部署环境提供 `API_AUTH_FIXED_USER_PASSWORD`，再部署 API 和 Web；不配置密码时部署应快速失败。
3. Web 与 API 同步切换到认证、项目和 generation 契约，并确认旧 `/api/chat` 已移除。
4. 回滚时先部署不依赖新表和新接口的旧应用，再显式执行配对 down migration；执行前确认可删除新功能产生的数据。

## Open Questions

无。项目管理、安全增强和其余失败状态界面细节明确留在本次范围外。
