## Why

`apps/server` 已具备基础 FastAPI 实现，但当前启动命令未应用强类型 Server 配置，Turborepo 未透传 Python runtime 所需环境变量，构建产物仍依赖仓库外部 Schema，关键验证也依赖待退役的 Go 进程。若此时删除 `apps/api`，只能保证部分本地源码场景可用，无法证明根开发入口、独立构建产物和回归验证仍可靠。

## What Changes

- 让 Python 进程入口统一读取并应用监听地址、端口和关闭超时，避免 package 脚本绕过 `API_*` 配置。
- 为 Server 的 Turborepo 任务显式透传运行所需的 `API_*` 配置，并保持 Web 默认 rewrite 指向 Python 监听端口。
- 让 Server wheel 自包含 DesignDocument v2 Schema，不再在运行时依赖仓库相对路径。
- 将删除前必须完成的双实现结果固化为可长期运行的 Python 契约回归测试；保留一次性 Go/Python 实跑作为删除门禁，而非删除后的持续依赖。
- 更新迁移队列和根切换清单，明确 migration 与 PostgreSQL 集成验证仍是删除 `apps/api` 的阻塞项。
- 本变更不删除 `apps/api`，不复制或替代 SQL migration，也不声称未实际运行的 PostgreSQL 验证已经通过。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `python-api-runtime`: 使 Python 启动入口、环境透传、根开发任务和 wheel 资源满足独立运行要求。
- `backend-migration-governance`: 将可重复契约 fixture 与一次性双实现实跑分别作为删除前后的验证机制，并明确删除门禁。

## Impact

- 影响 `apps/server` 的进程入口、package/Turbo 配置、Design v2 Schema 加载和相关测试。
- 影响根 Turborepo 环境变量声明、迁移队列及切换清单。
- 不改变现有 HTTP/JSON/Cookie/SSE 公开契约，不修改数据库结构，不新增依赖，不删除 Go 实现。
