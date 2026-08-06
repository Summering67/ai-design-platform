# `apps/api` → `apps/server` 依赖清单

分析范围：21 个 Go 源/测试文件、`go.mod/go.sum`、配置示例、SQL migration、package/Turbo 配置、4 份 API OpenSpec、Web rewrite 和 `chat-api.ts`。依赖类型：`imports`、`calls`、`routes`、`configures`、`persists`、`validates`、`tests`、`consumed-by`。

| Go 来源 | 主要依赖/职责 | Python 目标 | 状态 |
| --- | --- | --- | --- |
| `cmd/server/main.go` | 进程入口 → server | `src/ai_design_server/main.py` | pending |
| `internal/config/config.go` | Viper、配置校验 | `config.py` | pending |
| `internal/config/config_test.go` | 配置测试 | `tests/test_config.py` | pending |
| `internal/logging/logging.go` | Zap 初始化 | `logging.py` | pending |
| `internal/database/database.go` | GORM/PG 连接池、ping、关闭 | `database.py` | verified |
| `internal/auth/auth.go` | User/session、Token、认证数据库访问 | `auth/service.py`, `auth/models.py` | in_progress |
| `internal/auth/handler.go` | 登录、Depends、Cookie、错误响应 | `auth/router.py` | pending |
| `internal/chat/message.go` | 消息模型与校验 | `chat/models.py` | pending |
| `internal/chat/message_test.go` | 消息单元测试 | `tests/test_chat_models.py` | pending |
| `internal/chat/client.go` | Chat Completions、超时、流 | `chat/client.py` | pending |
| `internal/chat/client_test.go` | 上游 client 测试 | `tests/test_chat_client.py` | pending |
| `internal/project/model.go` | Project/Message/Attempt Model | `database.py` | verified |
| `internal/project/service.go` | 事务、租约、历史、重试 | `project/service.py` | in_progress |
| `internal/project/handler.go` | JSON/SSE HTTP 边界 | `project/router.py` | pending |
| `internal/server/router.go` | 健康、路由、认证保护、日志恢复 | `server.py` | pending |
| `internal/server/router_test.go` | 健康与路由测试 | `tests/test_server.py` | pending |
| `internal/server/server.go` | 启动、信号、优雅关闭 | `main.py`, `app.py` | pending |
| `internal/design/design.go` | v1 结构校验/迁移输入 | `design/v1.py` | pending |
| `internal/design/design_test.go` | v1 测试 | `tests/test_design_v1.py` | pending |
| `internal/design/v2.go` | v2 Schema/语义校验 | `design/v2.py` | pending |
| `internal/design/v2_test.go`, `v2_integration_test.go` | v2 单元/集成测试 | `tests/test_design_v2.py` | pending |

非代码边：`apps/api/migrations/*.sql` → 两个后端共同 Schema；`apps/web/next.config.js` 与 `app/workspace/chat-api.ts` → 当前仍消费 Go，后续切换前作为 Python fixture；现有 OpenSpec → 行为事实源。

已解析的内部 Go 依赖主路径：`config → database/logging`；`auth → database`；`project → database + auth + chat`；`server → config + database + logging + chat + auth + project`；`cmd/server → server`。当前未发现环；Python 目标均位于 `apps/server`。

数据库迁移证据（2026-08-06）：SQLAlchemy Model 已逐项映射现有 SQL migration 的 `TEXT`、CHECK、UNIQUE、部分唯一索引和稳定排序索引；真实隔离 PostgreSQL 已验证请求 Session 隔离、事务原子回滚、外键 flush 顺序、租约接管、并发单运行约束与客户端消息幂等。项目历史、重试及完整 HTTP/SSE 等价仍按迁移队列继续验证。

HTTP 契约证据（2026-08-06）：`test_api_contract_parity.py` 已按当前 Web `chat-api.ts`/`workspace-chat.tsx` 的真实 JSON 与无 body 请求形状覆盖认证、项目读取、首次生成、后续生成、停止和重试，并校验 Go 等价的状态码、完整 JSON 字段、Cookie 属性及 completed/failed/interrupted SSE 事件。`test_go_python_live_parity.py` 提供双服务规范化逐项比较门禁；必须由隔离数据环境显式启用，当前未提供双服务地址，因此不将队列标记为 `verified`。
