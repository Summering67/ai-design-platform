## Why

当前仓库只有前端应用，缺少可独立启动、连接 PostgreSQL 并提供基础运行状态检查的后端。先建立一个最小且职责清晰的 Go 后端骨架，可以为后续逐步迁移现有其他语言后端的业务接口提供稳定起点，避免提前引入未使用的业务抽象。

## What Changes

- 在 `apps/api` 新增独立 Go module，使用 Gin 提供 HTTP 服务。
- 将 `apps/api` 注册为 pnpm workspace 包，并通过包级 Turborepo 配置接入统一的 `dev`、`build`、`lint` 和 `check-types` 任务。
- 使用 Viper 将配置文件与环境变量解析为强类型配置，并在配置无效时阻止服务启动。
- 使用 Zap 提供结构化日志，并记录 HTTP 请求的基础访问日志。
- 使用 GORM 连接 PostgreSQL，配置连接池，并在退出时关闭底层数据库连接。
- 提供 `/health/live` 与 `/health/ready` 健康检查端点。
- 支持 HTTP 服务优雅关闭，并集中完成配置、日志、数据库和路由的依赖组装。
- 提供不包含敏感值的示例配置；本次不新增业务模块、认证、数据库表或自动迁移。

## Capabilities

### New Capabilities

- `go-api-runtime`: Go API 的配置加载、日志、数据库连接、HTTP 生命周期和健康检查运行能力。

### Modified Capabilities

无。

## Impact

- 新增代码位于 `apps/api`，依赖仍由独立的 `go.mod` 管理，同时使用 `package.json` 作为 pnpm/Turborepo 的任务适配层。
- 新增 Gin、GORM PostgreSQL Driver、Zap 和 Viper 依赖。
- 运行环境需要可用的 PostgreSQL 连接信息；存活检查不依赖数据库，就绪检查会验证数据库连接。
- 不修改现有前端接口、页面、共享 UI 包或数据库结构。
