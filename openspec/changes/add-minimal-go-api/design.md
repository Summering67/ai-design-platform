## Context

当前仓库是由 pnpm workspace 和 Turborepo 管理的前端 monorepo，尚无后端应用。此次变更在 `apps/api` 中加入独立 Go module，作为后续迁移其他语言后端的最小运行基础。它需要跨越配置、日志、数据库和 HTTP 生命周期多个模块，因此先明确依赖方向和失败语义，避免业务开发开始后再重构启动流程。

## Goals / Non-Goals

**Goals:**

- 提供可独立启动的 Go API，技术栈限定为 Gin、GORM PostgreSQL Driver、Zap 与 Viper。
- 用小而明确的模块集中配置解析、日志初始化、数据库生命周期和 HTTP 路由。
- 提供可供本地开发及部署探针使用的存活、就绪端点。
- 对启动失败和关闭流程采取提前返回，避免部分初始化的服务继续运行。
- 保持 Go 依赖管理独立，同时将运行任务接入现有 pnpm/Turborepo 工作流。

**Non-Goals:**

- 不迁移旧后端业务接口，不新增账号、项目或设计等业务模块。
- 不实现认证、授权、CORS、限流、链路追踪或 API 版本管理。
- 不创建数据库表，不引入 SQL migration 工具，也不调用 GORM `AutoMigrate`。
- 不定义生产部署方式、容器镜像或 CI/CD 流程。

## Decisions

### 1. 使用独立 Go module 与 Turborepo 任务适配层

代码位于 `apps/api`，使用自身的 `go.mod` 和 `go.sum`。沿用已建立的正式 module path `github.com/Summering67/ai-design-platform/apps/api`。同时增加不包含 JavaScript 依赖的 `package.json`，将 `go run`、`go build`、`go vet` 和仅编译测试的 `go test` 映射到 Turborepo 已有的 `dev`、`build`、`lint` 与 `check-types` 任务。

包级 `turbo.json` 继承根配置并将 Go 构建产物声明为 `dist/**`，避免把 Go 输出规则应用到其他 workspace。备选方案是把 Go 依赖改由 pnpm 管理，但 pnpm 不理解 Go module 依赖，因此只把它用作任务编排层。

### 2. 从最小目录开始

采用以下结构：

```text
apps/api/
├── cmd/server/main.go
├── internal/
│   ├── config/config.go
│   ├── database/database.go
│   ├── logging/logging.go
│   └── server/
│       ├── router.go
│       └── server.go
├── config/config.example.yaml
├── go.mod
├── go.sum
├── package.json
└── turbo.json
```

`main.go` 只负责调用启动函数并确定进程退出结果。初始化顺序为配置、日志、数据库、路由和 HTTP 服务；任一步失败立即返回，并通过已建立的清理函数逆序释放资源。业务模块和中间件目录只在出现实际能力时创建。

备选方案是预先建立 `bootstrap`、`platform`、`middleware` 及各业务目录。这些目录目前没有行为，会形成空抽象和浅模块，因此延后创建。

### 3. Viper 仅存在于配置模块

`internal/config` 定义强类型 `Config` 及嵌套的 Server、Database、Log 配置。Viper 读取可选配置文件、设置默认值，并将 `API_SERVER_ADDRESS`、`API_DATABASE_DSN` 等环境变量映射到字段；环境变量优先。加载后统一校验端口地址、必需 DSN、正数连接池参数和正数超时。

其他模块只接收强类型配置，不直接读取 Viper 全局状态。这样配置来源的复杂度被隐藏在一个模块内，测试和后续替换配置来源都集中在同一接缝。

备选方案是在调用点直接使用 `viper.Get*`。这会传播字符串键和隐式默认值，使依赖难以识别，因此拒绝。

### 4. 数据库模块拥有连接生命周期

`internal/database` 接收数据库配置，使用 `gorm.Open(postgres.Open(dsn))` 创建 GORM 句柄，再取得底层 `*sql.DB` 配置最大空闲连接、最大打开连接和连接最大生命周期。初始化阶段执行有超时的 `PingContext`，失败即返回。模块同时返回关闭函数，使启动流程可以确定性释放连接。

健康检查只依赖最小的 `PingContext(context.Context) error` 接口，而不是让路由依赖 GORM。当前真实 PostgreSQL 和健康检查测试替身构成这处接缝。

备选方案是使用 `AutoMigrate` 保证表存在。当前没有业务表，而且生产数据库结构必须由显式迁移管理，因此不启用。

### 5. Zap 适配 Gin 访问日志

`internal/logging` 根据环境与日志级别创建 Zap Logger。Gin 使用自定义中间件记录方法、匹配到的路由路径、状态码、耗时和客户端 IP；不记录请求体、完整查询字符串或配置内容。Gin Recovery 捕获 panic，并通过 Zap 记录异常。

备选方案是直接使用 Gin 默认文本日志。它无法与应用启动日志保持统一字段和输出格式，因此使用 Zap 中间件。

### 6. 健康检查区分存活与就绪

`/health/live` 始终返回 `200` 与 `{"status":"ok"}`，不访问外部依赖。`/health/ready` 使用短超时调用数据库 Ping；成功返回 `200` 与 `{"status":"ready"}`，失败返回 `503` 与 `{"status":"not_ready"}`。响应不暴露数据库错误详情，具体错误只写日志。

将两者分开可避免数据库短暂故障导致编排系统持续重启仍然存活的进程。

### 7. 显式管理 HTTP 启停

使用标准库 `http.Server` 包装 Gin Router，并设置读取、写入和空闲超时。启动 goroutine 只将非 `http.ErrServerClosed` 错误视为失败。主流程等待 `SIGINT`、`SIGTERM` 或服务异常；正常终止时用带截止时间的 context 调用 `Shutdown`，随后关闭数据库并同步 Zap 缓冲。

备选方案是直接调用 `router.Run`。它隐藏 HTTP Server 配置且不利于统一处理关闭超时，因此拒绝。

## Risks / Trade-offs

- [启动时要求 PostgreSQL 可用会降低离线启动能力] → 这是就绪依赖的最小后端，失败应尽早暴露；存活检查仍不在运行时依赖数据库。
- [就绪检查每次执行数据库 Ping 会产生少量负载] → 使用短超时和数据库连接池；若未来探针频率造成压力，再引入有界缓存。
- [示例配置可能被误用于生产] → DSN 保持为空并标注由环境变量提供，配置校验阻止缺失凭据的启动。
- [当前未提供 schema migration] → 本次没有业务表；首次引入持久化模型时单独提出迁移能力变更。

## Migration Plan

1. 新增 `apps/api` Go module、最小运行模块和 Turborepo 任务适配层，不改变现有前端应用。
2. 使用示例配置准备本地环境，并通过环境变量提供 PostgreSQL DSN。
3. 验证配置失败、数据库不可用、两个健康端点及终止信号关闭行为。
4. 后续业务能力按独立 OpenSpec 变更逐个接入该运行骨架。

本变更不承接现有生产流量，回滚时可移除 `apps/api`，不会影响现有前端或旧后端。

## Open Questions

无。本次沿用现有正式 module path，并使用 JSON 健康响应作为明确默认值；部署方式与业务接口在后续变更中决定。
