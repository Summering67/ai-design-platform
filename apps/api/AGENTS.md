# API 后端开发规范

## 作用范围

本文件约束 `apps/api` 下的全部 Go 后端代码，并继承仓库根目录的 `AGENTS.md`。

发生冲突时，优先遵守距离目标文件最近且描述更具体的规则。

## 技术栈

* Go：`1.26.5`
* HTTP 框架：Gin `1.12.x`
* 数据库：PostgreSQL
* ORM：GORM `1.31.x`
* PostgreSQL Driver：`gorm.io/driver/postgres`
* 日志：Zap `1.28.x`
* 配置：Viper `1.21.x`
* 依赖管理：Go Modules
* 任务编排：pnpm workspace + Turborepo

依赖的准确版本以 `go.mod` 为准。

未经当前需求明确要求，不新增后端依赖，不替换既有技术栈。

pnpm 和 Turborepo 只负责任务编排。Go 依赖必须由 `go.mod` 和 `go.sum` 管理。

## 目录职责

```text
apps/api/
├── cmd/
│   └── server/
├── config/
├── migrations/
├── internal/
│   ├── config/
│   ├── database/
│   ├── logging/
│   ├── server/
│   └── <domain>/
├── go.mod
└── go.sum
```

* `cmd/server`：进程入口，只负责调用启动函数和设置退出状态。
* `internal/config`：强类型配置、Viper 加载、默认值和配置校验。
* `internal/database`：GORM、PostgreSQL、连接池和连接生命周期。
* `internal/logging`：Zap 初始化和日志配置。
* `internal/server`：Gin 路由、中间件、健康检查、HTTP 错误转换和 Server 生命周期。
* `internal/<domain>`：领域业务规则、HTTP 边界、数据访问、持久化模型和领域错误。
* `migrations`：可审查、可回滚的 PostgreSQL SQL migration。
* `config`：不包含敏感信息的配置示例。

新增业务能力时，优先放入 `internal/<domain>`。

不要预先创建全局 `handler`、`service`、`repository` 或 `model` 目录。

## 领域模块结构

领域规模较小时，优先使用少量同包文件：

```text
internal/user/
├── handler.go
├── service.go
├── repository.go
├── model.go
├── dto.go
├── errors.go
└── service_test.go
```

* `handler.go`：HTTP 参数解析、输入校验和响应转换。
* `service.go`：业务规则和事务边界。
* `repository.go`：数据库访问和调用方需要的最小接口。
* `model.go`：GORM 持久化模型。
* `dto.go`：HTTP 请求、响应和业务输入输出结构。
* `errors.go`：稳定的领域错误。
* `*_test.go`：对应模块的单元测试。

只有文件职责明显过多或领域规模明显扩大时，才拆分为子包。

## Go 编程规范

* 优先使用函数和小型结构体。
* 不使用无必要的全局可变状态。
* 参数无效、依赖缺失或发生错误时立即返回。
* 使用 `%w` 包装错误并保留错误链。
* 使用 `errors.Is` 和 `errors.As` 判断错误。
* 不使用错误字符串比较判断错误类型。
* 不使用 `panic` 处理正常业务错误。
* 不忽略需要处理的错误。
* 使用 `context.Context` 传递生命周期、超时和取消信号。
* `context.Context` 通常作为函数第一个参数。
* 不将 Gin 的 `*gin.Context` 传入业务逻辑或数据库模块。
* 不为每个结构体机械创建接口。
* 接口定义在调用方，只用于真实存在的替换接缝。
* 不创建只有一层转发逻辑的包装模块。
* 所有 Go 代码必须经过 `gofmt`。
* 导出的标识符应具有清晰名称和必要注释。

## 错误处理规则

领域错误定义在对应领域模块中：

```go
var (
	ErrNotFound = errors.New("user not found")
	ErrConflict = errors.New("user already exists")
)
```

底层错误必须补充操作上下文并保留错误链：

```go
return fmt.Errorf("find user by email: %w", err)
```

Handler 不直接判断 PostgreSQL 或 GORM 内部错误。

数据库错误应在 Repository 或 Service 层转换为稳定的领域错误。

领域错误到 HTTP 状态码和错误码的映射统一放在 HTTP 边界。

默认映射：

* 输入无效：`400`
* 未认证：`401`
* 无权限：`403`
* 资源不存在：`404`
* 状态或唯一约束冲突：`409`
* 内部错误：`500`

HTTP 响应不得包含原始数据库错误、SQL、堆栈、DSN 或内部文件路径。

## HTTP 规则

* Handler 只负责参数解析、输入校验、调用业务逻辑和响应转换。
* Handler 禁止直接调用 GORM。
* Handler 不承载可复用业务规则。
* 业务逻辑不得依赖 Gin。
* HTTP 状态码、错误码和 JSON 字段必须保持稳定。
* 参数无效时立即返回，不继续执行数据库或外部调用。
* 请求 DTO、响应 DTO 和 GORM Model 必须分离。
* 列表接口必须定义分页参数、默认值、最大值和稳定排序。
* 时间字段必须使用明确且统一的格式。
* 修改公开 HTTP 契约时必须同步更新 OpenSpec。

健康检查：

* 存活检查：`GET /health/live`
* 就绪检查：`GET /health/ready`

存活检查只判断进程能否响应。

就绪检查可以验证数据库等关键依赖，但必须设置独立超时。

## 数据库规则

* PostgreSQL 是唯一关系型数据库。
* 数据访问统一通过 GORM PostgreSQL Driver。
* GORM Model 不得直接作为 HTTP 请求或响应 DTO。
* 事务范围由业务逻辑决定。
* Handler 中禁止开启、提交或回滚事务。
* 数据完整性优先通过 PostgreSQL 约束、唯一索引和外键保障。
* 生产环境禁止使用 GORM `AutoMigrate`。
* 查询必须传入 `context.Context`。
* GORM 查询必须使用 `WithContext(ctx)`。
* 避免无界查询。
* 列表查询必须分页并使用稳定排序。
* 批量操作必须考虑事务、最大批量和部分失败。
* 不在循环中执行可以合并的重复查询。
* 不解决当前需求之外的历史表结构或查询问题。

Repository 接口应保持最小化，并由业务逻辑调用方定义。

禁止创建包含所有 CRUD 方法的通用 Repository。

## Migration 规则

数据库结构变更使用显式 SQL migration，存放在：

```text
apps/api/migrations
```

默认命名格式：

```text
YYYYMMDDHHMMSS_description.up.sql
YYYYMMDDHHMMSS_description.down.sql
```

要求：

* `up.sql` 描述正向变更。
* `down.sql` 提供可执行的回滚方案。
* 表、字段、索引和约束名称必须明确。
* 高风险变更必须考虑已有数据和回滚影响。
* 不使用 GORM `AutoMigrate` 代替 migration。
* 不修改已经应用的 migration，应新增后续 migration。
* 仓库已有 migration 工具时继续使用现有工具和命名规则。
* 未经明确要求，不新增 migration 工具。

涉及数据库结构变更时，必须同步更新 GORM Model、Repository、相关测试和 OpenSpec。

## 配置规则

* Viper 只能在 `internal/config` 中使用。
* 其他模块只能接收解析并校验后的强类型配置。
* 环境变量使用 `API_` 前缀。
* 环境变量优先级高于 YAML 配置文件。
* 必需配置缺失或无效时必须阻止服务启动。
* 默认值只用于安全且适用于所有环境的配置。
* 不为密码、密钥和生产地址提供默认值。
* `config.example.yaml` 只能包含安全示例和非敏感默认值。
* 新增或修改配置键时，必须同步更新配置结构、校验、示例文件和 OpenSpec。

## 日志规则

* 服务运行日志统一使用 Zap。
* 不使用 `log.Printf` 或 `fmt.Printf` 记录服务日志。
* 日志必须使用结构化字段。
* HTTP 访问日志至少包含方法、路由、状态码和耗时。
* 已存在 request ID 时应写入日志。
* 错误日志应包含必要业务上下文。
* 不得记录密码、Token、完整 DSN、Authorization Header、请求体或敏感查询参数。
* 同一个错误只记录一次。
* 正常业务拒绝不应全部记录为 error 级别。
* 高频路径不得记录无价值的逐条日志。

## 生命周期规则

* 使用标准库 `http.Server` 承载 Gin Router。
* 必须配置读取、写入、空闲和关闭超时。
* 初始化顺序保持为配置 → 日志 → 数据库 → 路由 → HTTP Server。
* 任一步初始化失败时立即返回并释放已创建资源。
* 必须处理 `SIGINT` 和 `SIGTERM`。
* 关闭时先停止接收 HTTP 请求，再关闭数据库连接，最后同步日志。
* 优雅关闭必须设置最大等待时间。
* `http.ErrServerClosed` 不作为异常启动失败处理。

## 后端测试规则

优先测试：

* 配置解析和配置校验
* 领域业务规则
* 领域错误到 HTTP 错误的映射
* Handler 参数校验和响应转换
* 缺陷修复对应的回归场景

测试方式：

* 业务规则使用单元测试。
* HTTP Handler 使用 `httptest`。
* 数据库依赖通过最小接口替换。
* 普通单元测试不要求连接真实 PostgreSQL。
* 测试名称必须说明输入场景和预期行为。

当前没有统一的 PostgreSQL 集成测试环境，不得虚构集成测试结果。

## 后端质量检查

Go 原生检查入口：

```bash
go test ./...
go vet ./...
```

Turborepo 检查入口：

```bash
pnpm lint --filter=api
pnpm check-types --filter=api
pnpm build --filter=api
```

具体运行要求、失败处理和结果汇报遵守仓库根目录的 `AGENTS.md`。
