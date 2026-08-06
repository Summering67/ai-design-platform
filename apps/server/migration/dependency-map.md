# `apps/api` → `apps/server` 依赖清单

分析范围：21 个 Go 源/测试文件、`go.mod/go.sum`、配置示例、SQL migration、package/Turbo 配置、4 份 API OpenSpec、Web rewrite 和 `chat-api.ts`。依赖类型：`imports`、`calls`、`routes`、`configures`、`persists`、`validates`、`tests`、`consumed-by`。

| Go 来源 | 主要依赖/职责 | Python 目标 | 状态 |
| --- | --- | --- | --- |
| `cmd/server/main.go` | 进程入口 → server | `src/ai_design_server/main.py` | pending |
| `internal/config/config.go` | Viper、配置校验 | `config.py` | pending |
| `internal/config/config_test.go` | 配置测试 | `tests/test_config.py` | pending |
| `internal/logging/logging.go` | Zap 初始化 | `logging.py` | pending |
| `internal/database/database.go` | GORM/PG 连接池、ping、关闭 | `database.py` | pending |
| `internal/auth/auth.go` | User/session、Token、认证数据库访问 | `auth/service.py`, `auth/models.py` | pending |
| `internal/auth/handler.go` | 登录、Depends、Cookie、错误响应 | `auth/router.py` | pending |
| `internal/chat/message.go` | 消息模型与校验 | `chat/models.py` | pending |
| `internal/chat/message_test.go` | 消息单元测试 | `tests/test_chat_models.py` | pending |
| `internal/chat/client.go` | Chat Completions、超时、流 | `chat/client.py` | pending |
| `internal/chat/client_test.go` | 上游 client 测试 | `tests/test_chat_client.py` | pending |
| `internal/project/model.go` | Project/Message/Attempt Model | `project/models.py` | pending |
| `internal/project/service.go` | 事务、租约、历史、重试 | `project/service.py` | pending |
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
