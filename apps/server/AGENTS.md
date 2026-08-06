# apps/server 开发规范

`apps/server` 是默认 API 运行时。它必须能够独立启动，不得导入或在运行时读取 `apps/api` 的私有代码；`apps/api` 仅作为保留的 Go 基准和定向回退入口。

## 技术栈

- FastAPI + Starlette，Uvicorn 仅作为独立进程入口。
- Pydantic Settings + PyYAML：配置只在 `config.py` 解析，业务模块不得直接读取环境变量或 YAML。
- 配置来源为默认值、YAML、`apps/server/.env`、根目录开发兼容变量、进程环境 `API_*`；数据库 DSN 使用 SQLAlchemy/psycopg URL 格式，Go 配置不在 Python 层复用。
- SQLAlchemy 2 AsyncEngine/AsyncSession + psycopg 3 async driver。
- Python 标准 `logging` + 集中 JSON formatter/Filter。
- HTTPX、jsonschema、uv、Ruff、mypy、pytest。

## 数据库

- SQLAlchemy Model 与 Pydantic DTO 分离；每个请求使用独立 `AsyncSession`。
- 事务由领域服务显式控制；不得跨并发任务共享 Session，不依赖隐式 lazy loading。
- 数据库或 SQLAlchemy 异常必须在边界转换为稳定领域错误，不暴露 SQL、DSN 或堆栈。

## HTTP 与生命周期

- 路由按领域放入 `APIRouter`，应用工厂负责注册。
- 认证通过 `Depends` 注入当前用户；业务逻辑不得依赖 FastAPI Request/Response。
- `lifespan` 管理 AsyncEngine、Session factory 和 HTTPX client，并存入 `app.state`。
- Pydantic 请求模型使用 `extra="forbid"`；validation/领域异常统一转换为现有 API 错误结构。
- SSE 使用 `StreamingResponse`，客户端断开必须取消上游并终结 generation。


## 检查

使用 `uv` 及已提交 `uv.lock` 管理依赖。相关测试、静态检查、类型检查和构建结果必须实际记录在迁移队列中。
