# 双实现迁移规则

## 边界

`apps/api` 是 Go/Gin/GORM/Zap/Viper/Go Modules 的只读运行基准；`apps/server` 是 Python/FastAPI 等价实现。本次只新增和验证 `apps/server`，不修改根入口、Web rewrite、部署指向或任何 `apps/api` 文件。

## 替换矩阵

| 基准 | 目标 |
| --- | --- |
| Gin / `http.Server` | FastAPI/Starlette + Uvicorn + lifespan |
| GORM + PostgreSQL Driver | SQLAlchemy 2 AsyncEngine/typed ORM/表达式 API + psycopg 3 |
| Zap | 标准 `logging` + 集中 JSON formatter/Filter |
| Viper | Pydantic Settings + PyYAML 显式来源合并 |
| Go Modules | `pyproject.toml` + `uv.lock`，只用 uv 安装 |

## 契约与数据

- 现有 OpenSpec、Web `chat-api.ts`、`apps/api/migrations/*.sql` 和 Go 测试 fixture 优先于框架默认行为。
- 保持路由、状态码、错误码、JSON 字段、Cookie 属性、SSE 事件、UTC/UUID、超时、并发、租约和事务语义。
- SQL migration 是两个后端共同的 Schema 唯一事实源；不得使用 Alembic、`metadata.create_all()` 或复制 migration。
- SQLAlchemy Model 与 Pydantic DTO 分离；每个请求独立 AsyncSession，事务由领域服务控制。
- 配置优先级固定为默认值 < YAML < `apps/server/.env` < 根目录开发兼容变量 < 进程环境 `API_*`；`.env` 只作为本地开发来源，不提交敏感值。
- `apps/server/.env` 的数据库 DSN 使用 SQLAlchemy/psycopg URL 格式，例如 `postgresql+psycopg://user:password@host:5432/database`；Go/libpq 配置只属于 `apps/api`，不在 Python 配置层兼容；禁止记录完整 DSN。

## FastAPI 边界

- 领域路由使用 `APIRouter`，应用工厂负责注册。
- 认证和请求级资源使用 `Depends`；依赖不隐藏事务、不吞领域错误。
- lifespan 管理 Engine、Session factory 和 HTTPX client，资源放在 `app.state`。
- `extra="forbid"`，默认 422 必须转换为既有 400 `invalid_request`。
- generation 使用 `StreamingResponse`，客户端断开取消上游并终结 generation。

## 验证与状态

队列状态只能为 `pending → ready → in_progress → verified`。`verified` 只表示 Python 目标通过等价证据，不代表 Go 可删除或根入口可切换。写数据库比较使用隔离 DSN/Schema 和相同初始 fixture；网络并行使用不同端口，优先使用 Go httptest 与 Python ASGITransport。

## 安全

迁移文档、日志和测试证据不得包含密码、Token、API Key、Authorization Header、完整 DSN、真实用户资料或请求体。
