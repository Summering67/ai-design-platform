# Go API Runtime Specification

## Purpose

定义 Go API 服务的运行配置、日志、数据库、健康检查、服务生命周期和 Turborepo 集成要求。

## Requirements

### Requirement: 强类型运行配置
系统 SHALL 使用 Viper 从可选 YAML 配置文件和带 `API_` 前缀的环境变量加载配置，并将结果解析为供其他模块使用的强类型配置值。环境变量 SHALL 覆盖配置文件中的同名配置，敏感值 SHALL 不出现在示例配置中。

#### Scenario: 环境变量覆盖配置文件
- **WHEN** 配置文件与环境变量同时提供同一项配置
- **THEN** 系统使用环境变量中的值启动

#### Scenario: 配置无效
- **WHEN** 服务地址、数据库连接或连接池配置缺失或无效
- **THEN** 系统返回明确的启动错误并且不启动 HTTP 服务

### Requirement: 结构化运行日志
系统 SHALL 使用 Zap 输出结构化日志，并 SHALL 为每个已完成的 HTTP 请求记录请求方法、路由路径、响应状态码和处理耗时。系统 SHALL NOT 在访问日志中记录请求体或数据库连接凭据。

#### Scenario: HTTP 请求完成
- **WHEN** Gin 完成一个 HTTP 请求
- **THEN** 系统写入包含方法、路径、状态码和耗时的结构化访问日志

### Requirement: PostgreSQL 生命周期
系统 SHALL 使用 GORM PostgreSQL Driver 建立数据库连接，应用配置的连接池参数，并在服务关闭时关闭 GORM 使用的底层 SQL 连接。系统 SHALL NOT 在启动时自动修改数据库结构。

#### Scenario: 数据库连接成功
- **WHEN** PostgreSQL 可访问且连接配置有效
- **THEN** 系统完成数据库初始化并继续启动 HTTP 服务

#### Scenario: 数据库连接失败
- **WHEN** PostgreSQL 不可访问或连接配置错误
- **THEN** 系统记录启动失败并且不启动 HTTP 服务

#### Scenario: 服务关闭
- **WHEN** 服务进入关闭流程
- **THEN** 系统关闭底层数据库连接且不执行数据库自动迁移

### Requirement: 健康检查
系统 SHALL 提供 `GET /health/live` 和 `GET /health/ready`。存活检查 SHALL 仅表示 HTTP 进程可以处理请求；就绪检查 SHALL 在请求时验证数据库连接。

#### Scenario: 服务存活
- **WHEN** 客户端请求 `GET /health/live`
- **THEN** 系统返回 HTTP 200 和稳定的健康状态 JSON

#### Scenario: 数据库就绪
- **WHEN** 客户端请求 `GET /health/ready` 且数据库连接验证成功
- **THEN** 系统返回 HTTP 200 和稳定的就绪状态 JSON

#### Scenario: 数据库未就绪
- **WHEN** 客户端请求 `GET /health/ready` 且数据库连接验证失败
- **THEN** 系统返回 HTTP 503 和稳定的未就绪状态 JSON

### Requirement: HTTP 服务生命周期
系统 SHALL 使用显式超时配置启动 Gin HTTP 服务，并 SHALL 在收到支持的终止信号后停止接收新请求、在关闭超时内等待进行中的请求完成，然后释放日志与数据库资源。

#### Scenario: 正常启动
- **WHEN** 配置、日志和数据库初始化全部成功
- **THEN** 系统在配置的地址启动 HTTP 服务

#### Scenario: 收到终止信号
- **WHEN** 运行中的服务收到 `SIGINT` 或 `SIGTERM`
- **THEN** 系统在配置的关闭超时内执行优雅关闭并释放资源

#### Scenario: HTTP 服务异常退出
- **WHEN** HTTP 服务返回非正常关闭错误
- **THEN** 系统记录错误并以失败状态结束进程

### Requirement: Turborepo 任务集成
系统 SHALL 将 `apps/api` 注册为 pnpm workspace 包，并 SHALL 通过 Turborepo 暴露 `dev`、`build`、`lint` 和 `check-types` 任务。Go 依赖 SHALL 继续由 `go.mod` 管理，Go 构建产物 SHALL 输出到可缓存的 `dist/**`。

#### Scenario: 运行 API 定向任务
- **WHEN** 开发者通过 Turborepo 对 `api` 包执行 `build`、`lint` 或 `check-types`
- **THEN** 系统执行对应的 Go 工具链命令且任务成功时返回成功状态

#### Scenario: 运行仓库级任务
- **WHEN** 开发者在仓库根目录执行已有的 `build`、`lint`、`check-types` 或 `dev` 管线
- **THEN** Turborepo 将 `api` 与现有 workspace 一起纳入对应任务图

#### Scenario: 缓存 Go 构建产物
- **WHEN** Turborepo 成功构建 `api` 包
- **THEN** 可执行文件生成在 `apps/api/dist` 且 `dist/**` 被声明为该包的构建输出
