# apps/server 开发规范

`apps/server` 是与 `apps/api` 并存的 Python/FastAPI 后端验证实现。`apps/api` 是只读 Go 基准；本目录不得修改、移动、删除或导入 `apps/api/internal` 私有实现。

## 技术栈

- FastAPI + Starlette，Uvicorn 仅作为独立进程入口。
- Pydantic Settings + PyYAML：配置只在 `config.py` 解析，业务模块不得直接读取环境变量或 YAML。
- 配置来源为默认值、YAML、`apps/server/.env`、根目录开发兼容变量、进程环境 `API_*`；数据库 DSN 使用 SQLAlchemy/psycopg URL 格式，Go 配置不在 Python 层复用。
- SQLAlchemy 2 AsyncEngine/AsyncSession + psycopg 3 async driver。
- Python 标准 `logging` + 集中 JSON formatter/Filter。
- HTTPX、jsonschema、uv、Ruff、mypy、pytest。

## 数据库

- `apps/api/migrations/*.sql` 是唯一 Schema 事实源；禁止复制 migration、Alembic、`metadata.create_all()` 和自动建表。
- SQLAlchemy Model 与 Pydantic DTO 分离；每个请求使用独立 `AsyncSession`。
- 事务由领域服务显式控制；不得跨并发任务共享 Session，不依赖隐式 lazy loading。
- 数据库或 SQLAlchemy 异常必须在边界转换为稳定领域错误，不暴露 SQL、DSN 或堆栈。

## HTTP 与生命周期

- 路由按领域放入 `APIRouter`，应用工厂负责注册。
- 认证通过 `Depends` 注入当前用户；业务逻辑不得依赖 FastAPI Request/Response。
- `lifespan` 管理 AsyncEngine、Session factory 和 HTTPX client，并存入 `app.state`。
- Pydantic 请求模型使用 `extra="forbid"`；validation/领域异常统一转换为现有 API 错误结构。
- SSE 使用 `StreamingResponse`，客户端断开必须取消上游并终结 generation。

## 双实现边界

- 默认根开发入口继续运行 `apps/api`；本包只提供 `dev:standalone`。
- Python 目标使用 `API_*` 配置键以保持未来切换兼容，但当前 Web 不指向本包。
- 等价验证使用隔离数据库或 Schema；不得让 Go/Python 并发修改同一测试记录。

## 检查

使用 `uv` 及已提交 `uv.lock` 管理依赖。相关测试、静态检查、类型检查和构建结果必须实际记录在迁移队列中。
