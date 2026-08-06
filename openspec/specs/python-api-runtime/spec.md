# python-api-runtime Specification

## Purpose
TBD - created by archiving change migrate-go-api-to-python. Update Purpose after archive.
## Requirements
### Requirement: FastAPI 应用边界

`apps/server` SHALL 使用 FastAPI 应用工厂和领域 `APIRouter` 组装全部 HTTP 路由，SHALL 使用 `Depends` 实现当前用户等请求级依赖，SHALL 使用 lifespan 管理 SQLAlchemy `AsyncEngine`、Session factory 与 HTTPX client，并 SHALL 使用集中 exception handler 将 Pydantic 校验错误和领域错误转换为既有状态码、错误码及 JSON 结构。业务逻辑 MUST NOT 依赖 FastAPI `Request`、`Response` 或框架异常，进程级资源 MUST NOT 存放在模块级可变单例中。

#### Scenario: 严格请求校验失败

- **WHEN** FastAPI 接收到缺失必填字段、字段无效或包含未知字段的 API 请求
- **THEN** 系统在执行数据库或上游调用前返回既有 HTTP 400 与 `invalid_request`，而不是暴露默认 422 响应

#### Scenario: 认证依赖解析用户

- **WHEN** 受保护的 `APIRouter` 路由收到有效会话 Cookie
- **THEN** `Depends` 解析并注入当前用户，且路径函数只接收领域值而不复制认证逻辑

#### Scenario: lifespan 管理资源

- **WHEN** FastAPI 应用启动后再进入关闭流程
- **THEN** lifespan 按既定顺序创建并关闭连接池与 HTTPX client，且不遗留模块级可变资源

#### Scenario: 流式客户端断开

- **WHEN** `StreamingResponse` 发送 generation 增量期间客户端断开
- **THEN** 流生成器停止发送、取消 HTTPX 上游并按现有契约终结 generation

### Requirement: Python 强类型运行配置

系统 SHALL 使用 Pydantic Settings 定义强类型配置模型，使用 PyYAML 安全读取可选 YAML 配置文件，并通过显式来源合并保持“默认值 < YAML < 开发兼容变量 < `API_*`”的优先级。固定用户密码 SHALL 只从必需的 `API_AUTH_FIXED_USER_PASSWORD` 环境变量提供，AI 开发兼容变量、默认值、校验约束和敏感值保护 SHALL 与现行 API 契约一致；FastAPI 路由和领域模块 MUST NOT 直接读取环境变量或 YAML。

#### Scenario: 环境变量覆盖配置文件

- **WHEN** 配置文件与环境变量同时提供同一项非敏感配置
- **THEN** Python runtime 使用环境变量中的值启动

#### Scenario: 必需敏感配置缺失

- **WHEN** 固定用户密码、AI BaseURL 或 AI APIKey 在允许的配置来源中缺失或为空
- **THEN** Python runtime 返回明确配置错误且不启动 HTTP 服务

#### Scenario: 示例配置安全

- **WHEN** 开发者查看 API 示例配置
- **THEN** 示例只包含非敏感值和环境变量说明，不包含密码、API Key 或完整 DSN

### Requirement: Python 结构化运行日志

系统 SHALL 使用 FastAPI/Starlette 中间件、Python 标准 `logging`、集中 JSON formatter 和敏感字段 Filter，为每个已完成 HTTP 请求记录方法、匹配路由、状态码和耗时。系统 MUST NOT 并列引入第二日志门面，MUST NOT 记录请求体、Authorization Header、Cookie、完整 URL 查询、数据库连接凭据或 AI 密钥。未处理异常 SHALL 由集中 exception handler 转换为稳定内部错误响应，且外部响应 MUST NOT 包含堆栈或内部文件路径。

#### Scenario: HTTP 请求完成

- **WHEN** ASGI 应用完成一个 HTTP 请求
- **THEN** 系统写入包含方法、匹配路由、状态码和耗时的结构化访问日志

#### Scenario: 请求发生未处理异常

- **WHEN** 请求处理发生未处理异常
- **THEN** 系统记录脱敏错误并返回稳定内部错误，响应不包含堆栈或内部路径

### Requirement: Python PostgreSQL 生命周期

系统 SHALL 使用 SQLAlchemy 2 `AsyncEngine` 与连接池建立 PostgreSQL 连接，使用 psycopg 3 作为 async driver，应用既有连接池参数，并在 FastAPI lifespan 关闭时释放 Engine。系统 SHALL 将现有 GORM Model、链式查询、事务和错误分支逐项迁移为 typed declarative model、显式 SQLAlchemy statement、`AsyncSession` 事务与稳定领域错误；持久化 Model MUST 与 Pydantic DTO 分离，每个请求 MUST 使用独立 Session，MUST NOT 依赖隐式 lazy loading、跨并发任务共享 Session、调用 `metadata.create_all()` 或新增 Alembic。`apps/api/migrations/*.sql` SHALL 保持为两个实现共同的 Schema 唯一事实源，`apps/server` MUST NOT 复制或修改 migration，并 SHALL 保持既有表、索引、约束、稳定排序、UTC 时间、UUID、generation 唯一运行约束和租约行为。

#### Scenario: 数据库连接成功

- **WHEN** PostgreSQL 可访问且连接配置有效
- **THEN** Python runtime 完成 SQLAlchemy AsyncEngine 与 Session factory 初始化并继续启动 HTTP 服务

#### Scenario: 数据库连接失败

- **WHEN** PostgreSQL 不可访问或连接配置错误
- **THEN** Python runtime 记录脱敏启动失败且不启动 HTTP 服务

#### Scenario: 服务关闭

- **WHEN** Python runtime 进入关闭流程
- **THEN** 系统释放 SQLAlchemy AsyncEngine 连接池且不执行 `create_all`、Alembic 或其他自动 migration

#### Scenario: 请求事务完成

- **WHEN** 领域服务通过请求级 `AsyncSession` 成功完成原子业务操作
- **THEN** 服务在显式事务边界提交全部变更，且 FastAPI 依赖不额外自动提交

#### Scenario: 唯一约束冲突

- **WHEN** SQLAlchemy flush 或 commit 收到 PostgreSQL 唯一约束冲突
- **THEN** 数据库边界回滚事务并转换为既有稳定领域错误，不向 Handler 暴露 `IntegrityError`

### Requirement: Python 健康检查

FastAPI 应用 SHALL 继续提供 `GET /health/live` 和 `GET /health/ready`。存活检查 SHALL 仅表示 ASGI 进程可以处理请求；就绪检查 SHALL 在独立超时内验证数据库连接，并保持既有状态码和 JSON 响应。

#### Scenario: 服务存活

- **WHEN** 客户端请求 `GET /health/live`
- **THEN** Python runtime 返回 HTTP 200 和既有健康状态 JSON

#### Scenario: 数据库就绪

- **WHEN** 客户端请求 `GET /health/ready` 且数据库连接验证成功
- **THEN** Python runtime 返回 HTTP 200 和既有就绪状态 JSON

#### Scenario: 数据库未就绪

- **WHEN** 客户端请求 `GET /health/ready` 且数据库连接验证失败或超时
- **THEN** Python runtime 返回 HTTP 503 和既有未就绪状态 JSON

### Requirement: Python HTTP 服务生命周期

系统 SHALL 使用 Uvicorn 承载 FastAPI 应用，以显式读取、写入、空闲和关闭约束启动 API，并 SHALL 在收到 `SIGINT` 或 `SIGTERM` 后停止接收新请求、在关闭超时内等待进行中的请求完成，然后通过 lifespan 按 HTTP、数据库和日志的顺序释放资源。客户端断开 SHALL 传播取消信号到 SSE generation 和上游 AI 请求。

#### Scenario: 正常启动

- **WHEN** 配置、日志、数据库和应用组装全部成功
- **THEN** Python runtime 在既有配置地址启动 HTTP 服务

#### Scenario: 收到终止信号

- **WHEN** 运行中的 Python runtime 收到 `SIGINT` 或 `SIGTERM`
- **THEN** 系统在关闭超时内执行优雅关闭并释放资源

#### Scenario: SSE 客户端断开

- **WHEN** 客户端在 generation 完成前断开 SSE 请求
- **THEN** 系统取消上游调用并按现有契约终结 generation，不在后台继续运行

### Requirement: Python Turborepo 任务集成

`apps/server` SHALL 使用 `uv` 作为唯一 Python 依赖管理入口，将直接和开发依赖声明在 `pyproject.toml`，将完整版本解析结果提交到 `uv.lock`，并 MUST NOT 使用 `requirements.txt`、Pipenv、Poetry 或未锁定裸安装作为并列依赖事实源。系统 SHALL 将 `apps/server` 注册为 package 名 `server` 的独立 pnpm workspace，提供 `dev:standalone`、`build`、`lint`、`check-types` 和 `test`，但本次 MUST NOT 提供会被当前根 `turbo run dev` 自动执行的 `dev` 脚本。Python 构建 SHALL 在 `apps/server/dist/**` 输出可缓存 wheel，lint SHALL 执行 Ruff，类型检查 SHALL 执行 mypy，测试 SHALL 通过 pytest 区分单元测试和集成测试。

#### Scenario: 依赖锁定可复现

- **WHEN** 开发者或任务入口在干净环境安装 API 的运行和开发依赖
- **THEN** `uv` 使用已提交且与 `pyproject.toml` 一致的 `uv.lock` 解析相同版本，不执行浮动依赖解析

#### Scenario: 运行 Python server 定向任务

- **WHEN** 开发者通过 Turborepo 对 `server` 包执行 `build`、`lint` 或 `check-types`
- **THEN** 系统执行对应 Python 工具链命令且任务成功时返回成功状态

#### Scenario: 运行当前根开发入口

- **WHEN** 开发者在仓库根目录执行当前 `dev` 管线
- **THEN** Go `apps/api` 继续启动，Python `apps/server` 不自动启动或争用后端监听端口

#### Scenario: 运行仓库级检查

- **WHEN** 开发者在仓库根目录执行已有 `build`、`lint` 或 `check-types` 管线
- **THEN** Turborepo 将 `apps/server` 与现有 workspace 一起纳入对应非持久任务图，且不替换 `apps/api`

#### Scenario: 缓存 Python 构建产物

- **WHEN** Turborepo 成功构建 `server` 包
- **THEN** wheel 生成在 `apps/server/dist` 且 `dist/**` 声明为该包的构建输出

### Requirement: 现有 API 契约等价

`apps/server` SHALL 实现现行 `user-authentication`、`project-conversations`、`ai-chat` 和 DesignDocument 校验行为，并 SHALL 保持与 `apps/api` 相同的公开路由、JSON 字段、HTTP 状态码、错误码、Cookie 属性、SSE 事件顺序与终态、AI 历史选择、请求限制、数据库写入和取消语义。Web 调用方 MUST NOT 因新增 Python 实现而修改业务请求格式或当前后端指向。

#### Scenario: 相同契约 fixture

- **WHEN** Python runtime 接收覆盖成功、校验失败、未认证、冲突、上游失败和中断的冻结请求 fixture
- **THEN** 其状态码、响应字段、错误码、SSE 事件和数据库结果符合现行 OpenSpec

#### Scenario: Web 保持使用 Go 后端

- **WHEN** 本次变更完成后 Web 继续通过 `/backend/api` 和当前根入口请求后端
- **THEN** 请求仍由 Go `apps/api` 处理，`apps/server` 仅通过定向或进程内测试验证等价性
