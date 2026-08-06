## Why

当前 Go API 是唯一可运行基准，直接在 `apps/api` 内原地改写会失去可比对和可回退的实现。为保持可验证性，需要完整保留 `apps/api`，在新的 `apps/server` 中用 FastAPI 建立功能等价后端，并在后续独立变更中由用户决定何时替换根项目入口。

## What Changes

- 新增后端迁移规则手册，明确 `apps/api` 基准与 `apps/server` 目标的边界、Go/Gin→Python/FastAPI 映射、FastAPI 依赖注入与 lifespan、错误与时间语义、数据库兼容、安全和等价验证规则。
- 盘点 `apps/api` 的 Go 源文件、测试、配置、SQL migration、Turborepo 任务、OpenSpec 契约及 Web 调用方，记录文件级依赖、跨模块依赖、外部依赖和迁移阻塞项。
- 建立按依赖拓扑排序的迁移队列；每个队列项包含 `apps/api` 来源、`apps/server` 目标、前置项、契约、验证方式、状态和等价证据。
- 明确替换后端基础栈：Gin→FastAPI/Starlette、Go `http.Server`→Uvicorn、GORM→SQLAlchemy 2 Async ORM/表达式 API + psycopg 3、Zap→Python 标准 `logging` JSON 日志、Viper→Pydantic Settings + PyYAML、Go Modules→`uv` + `pyproject.toml` + `uv.lock`。
- 在 `apps/server` 内以 FastAPI 重建配置、结构化日志、PostgreSQL 生命周期、认证、项目对话、Chat Completions 流、DesignDocument 校验、HTTP 路由和进程生命周期，并保持与 `apps/api` 相同的 HTTP/SSE、Cookie、数据库 Schema、环境变量与错误码行为。
- 将 `apps/server` 注册为独立 workspace，提供不会接管当前根 `dev` 入口的定向开发、构建、检查和测试能力，并将 wheel 输出到 `apps/server/dist/**`。
- 使用相同契约 fixture、隔离 PostgreSQL 测试数据和跨实现集成测试证明两个后端功能等价。
- 保留 `apps/api` 的 Go 源码、Go Modules、package/Turbo 配置和运行入口；本次不修改 Web `API_BASE_URL`、根项目入口或当前部署指向。

## Capabilities

### New Capabilities

- `backend-migration-governance`: 定义双实现迁移规则手册、文件依赖清单、拓扑迁移队列、等价证据和根入口切换边界。
- `python-api-runtime`: 定义位于 `apps/server` 的 FastAPI 应用边界、配置、日志、PostgreSQL、健康检查、服务生命周期、质量检查和独立 workspace 集成要求。

### Modified Capabilities

无。`go-api-runtime` 及其实现保持不变。

## Impact

- 新增 `apps/server` Python workspace、FastAPI 应用、测试、迁移文档和 `dist/**` 构建产物；`apps/api` 内容保持不变。
- 新增 FastAPI、Starlette、Uvicorn、Pydantic Settings、PyYAML、SQLAlchemy 2、psycopg 3、HTTPX 与 jsonschema 等 Python 依赖，使用 `uv`、`pyproject.toml` 和 `uv.lock` 管理并锁定；不新增 Alembic、数据库基础设施或修改既有 SQL migration。
- 新增 Python runtime 与双实现迁移治理契约；认证、项目对话和 AI Chat 的外部需求保持不变，并由同一套 fixture 验证 Go/Python 等价。
- Web 继续通过当前根入口和 `/backend/api` rewrite 访问 Go `apps/api`；不会在本次变更中指向 `apps/server`。
- 后续根入口替换、生产切流和 Go 退役必须由新的明确变更处理，不属于本次范围。
