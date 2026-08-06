## Context

当前根 workspace 会发现 `apps/server` 的 `dev` 脚本，但 Go 与 Python 都仍可被根 `turbo run dev` 调度。Python package 脚本直接调用 Uvicorn 并硬编码 `localhost:8081`，绕过了 `RuntimeConfig.server`；Turborepo 严格环境模式也只声明 `API_BASE_URL`。此外，Design v2 校验从仓库相对路径读取 JSON Schema，wheel 本身不包含该资源。现有测试可以覆盖大部分进程内 HTTP 契约，但 PostgreSQL 集成测试和双服务实跑因环境缺失被跳过。

## Goals / Non-Goals

**Goals:**

- 让根开发入口只选择 Python Server 作为后端，同时保留 Go 源码用于删除前回退和一次性等价验证。
- 让 Python 进程入口从统一 `RuntimeConfig` 应用监听地址、keep-alive 与关闭超时。
- 让 Turborepo 将 `API_*` 运行配置传给 Server dev 任务。
- 让 wheel 包含 Design v2 的同一份规范 Schema，并通过包资源读取。
- 建立不依赖 Go 进程的冻结契约回归面，并保留未完成数据库验证的真实状态。

**Non-Goals:**

- 不删除 `apps/api`，不实现或复制 SQL migration。
- 不修改数据库 Schema、HTTP 请求/响应结构或 Web 业务调用。
- 不在缺少隔离 PostgreSQL 时将相关队列项标记为已验证。

## Decisions

1. 根 `dev` 使用 Turborepo 负过滤排除 `api`，而不是修改 Go package。这样 Go 回退入口保持完整，删除目录后同一根命令仍可使用。
2. `ai_design_server.main` 提供唯一进程入口。package 脚本不再重复监听参数；入口把 `:port` 映射为 `0.0.0.0:port`，显式主机地址保持原值，并将 idle/shutdown 配置映射到 Uvicorn 支持的 keep-alive/graceful-shutdown 参数。应用层 AI 超时继续由 `ChatClient` 管理；不伪造 Uvicorn 不提供的独立 write timeout。
3. 在 `apps/server/turbo.json` 的 `dev` 任务声明 `API_*`，使严格环境模式既透传又参与任务环境声明；敏感值不写入任何制品。
4. 使用 Hatch wheel `force-include` 从 `packages/design-contract` 的唯一 Schema 源打包资源。安装后的 runtime 优先读取包资源，源码开发模式才回退到 workspace Schema，避免维护第二份手工副本。
5. 删除后的持续测试以进程内冻结契约为主；双服务 live parity 只作为删除前门禁。数据库测试继续要求隔离 DSN，不使用 SQLite 或自动建表替代 PostgreSQL 语义。

## Risks / Trade-offs

- [Hatch 对 workspace 外文件的打包路径受构建配置影响] → 构建 wheel 后检查归档内容，并从解压后的包资源执行 Design v2 校验测试。
- [根开发入口提前切到 Python 后，未完成数据库等价问题会更早暴露] → 保留 `pnpm --filter api dev` 回退方式，并在删除前维持 Go 目录不变。
- [Uvicorn 没有与 Go `http.Server` 完全相同的读写超时参数] → 只映射原生支持的监听、keep-alive 和优雅关闭；请求及上游超时留在应用接口处验证并记录差异。
- [当前缺少隔离 PostgreSQL] → 测试继续跳过并在队列保持阻塞，不降低验收门槛。

## Migration Plan

1. 切换根开发任务并验证任务图只包含 Python Server。
2. 实现并测试统一 Python 进程入口及 Turbo 环境透传。
3. 构建并检查自包含 wheel。
4. 运行 Ruff、mypy、pytest、build；数据库与 live parity 无环境时保持未验证。
5. 在 migration 完成并补齐 PostgreSQL、live parity 证据后，另行删除 `apps/api` 并更新锁文件及主规格。

回退时将根 `dev` 恢复为未过滤的 Turborepo 入口，或定向运行保留的 `api` package；本变更不破坏 Go 回退代码。

## Open Questions

- PostgreSQL migration 的最终归属和执行工具仍由后续变更决定。
- 生产部署平台尚未在仓库中定义；本变更只保证进程入口和 wheel 可被部署系统消费。
