## 1. Go 应用骨架

- [x] 1.1 创建 `apps/api` 独立 Go module、`cmd/server` 与最小 `internal` 目录，并加入 Gin、GORM PostgreSQL Driver、Zap 和 Viper 依赖
- [x] 1.2 添加不含凭据的 `config/config.example.yaml`，记录环境变量覆盖方式和最小启动配置

## 2. 配置与基础设施

- [x] 2.1 实现强类型 Server、Database、Log 配置及 Viper 文件、默认值、`API_` 环境变量加载逻辑
- [x] 2.2 实现配置校验与提前返回，并覆盖环境变量优先和无效配置场景
- [x] 2.3 实现 Zap 初始化与日志级别、运行环境配置，不记录敏感配置
- [x] 2.4 实现 GORM PostgreSQL 初始化、启动 Ping、连接池参数应用和底层连接关闭逻辑，且不调用 `AutoMigrate`

## 3. HTTP 运行能力

- [x] 3.1 创建 Gin Router，并实现基于 Zap 的访问日志与 Recovery 中间件
- [x] 3.2 实现 `GET /health/live` 的固定存活响应
- [x] 3.3 通过最小数据库 Ping 接口实现 `GET /health/ready` 的就绪与未就绪响应，并限制 Ping 超时
- [x] 3.4 使用标准库 `http.Server` 实现显式读写、空闲超时及非正常退出错误传播

## 4. 启动与关闭

- [x] 4.1 在启动流程中按配置、日志、数据库、路由和 HTTP 服务顺序组装依赖，并在初始化失败时提前返回
- [x] 4.2 处理 `SIGINT`、`SIGTERM` 和 HTTP 服务异常，按关闭超时优雅停止服务并释放数据库与 Zap 资源
- [x] 4.3 保持 `cmd/server/main.go` 为最小进程入口，并为启动失败返回非零退出状态

## 5. 验证

- [x] 5.1 添加针对配置优先级、配置校验、存活端点和数据库就绪状态的 Go 测试
- [x] 5.2 格式化 Go 代码并执行 Go module 范围内的测试与静态检查，确认未影响现有前端 workspace

## 6. Turborepo 集成

- [x] 6.1 为 `apps/api` 添加 pnpm workspace 元数据，并映射 `dev`、`build`、`lint` 和 `check-types` Go 命令
- [x] 6.2 添加继承根配置的包级 Turborepo 配置，将 `dist/**` 声明为 Go 构建输出
- [x] 6.3 验证 Turborepo 能识别 `api` 并成功执行定向构建、lint 与类型检查任务
