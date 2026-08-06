## MODIFIED Requirements

### Requirement: Python HTTP 服务生命周期

系统 SHALL 使用统一 Python 进程入口读取强类型运行配置并以 Uvicorn 承载 FastAPI 应用，SHALL 将配置的监听地址、空闲连接和关闭约束映射到 Uvicorn 支持的进程参数，并 SHALL 在收到 `SIGINT` 或 `SIGTERM` 后停止接收新请求、在关闭超时内等待进行中的请求完成，然后通过 lifespan 释放 HTTP 与数据库资源。客户端断开 SHALL 传播取消信号到 SSE generation 和上游 AI 请求。package 任务 MUST NOT 使用与 `API_*` 配置并列的监听地址事实源。

#### Scenario: 正常启动

- **WHEN** 配置、日志、数据库和应用组装全部成功
- **THEN** Python runtime 在 `API_SERVER_ADDRESS` 指定的地址启动 HTTP 服务，`:port` 形式监听所有接口

#### Scenario: 收到终止信号

- **WHEN** 运行中的 Python runtime 收到 `SIGINT` 或 `SIGTERM`
- **THEN** 系统在配置的关闭超时内执行优雅关闭并释放资源

#### Scenario: SSE 客户端断开

- **WHEN** 客户端在 generation 完成前断开 SSE 请求
- **THEN** 系统取消上游调用并按现有契约终结 generation，不在后台继续运行

### Requirement: Python Turborepo 任务集成

`apps/server` SHALL 使用 `uv` 作为唯一 Python 依赖管理入口，将直接和开发依赖声明在 `pyproject.toml`，将完整版本解析结果提交到 `uv.lock`，并 MUST NOT 使用其他并列依赖事实源。系统 SHALL 将 `apps/server` 注册为 package 名 `server` 的独立 pnpm workspace，提供 `dev`、`dev:standalone`、`build`、`lint`、`check-types` 和 `test`；根 `dev` SHALL 选择 Python `server` 并排除 Go `api`，Server dev 任务 SHALL 在 Turborepo 严格环境模式下获得所需 `API_*` 配置。Python 构建 SHALL 输出可缓存且包含运行所需 Design v2 Schema 的自包含 wheel。

#### Scenario: 运行根开发入口

- **WHEN** 开发者在仓库根目录执行 `dev` 管线
- **THEN** Turborepo 启动 Python `server` 与前端开发任务且不启动 Go `api`

#### Scenario: 环境变量传入 Server

- **WHEN** 根开发入口通过进程环境提供 `API_DATABASE_DSN`、`API_AI_*` 或 `API_AUTH_*`
- **THEN** Server dev 任务可以读取这些值并按强类型配置优先级应用

#### Scenario: 缓存 Python 构建产物

- **WHEN** Turborepo 成功构建 `server` 包
- **THEN** wheel 生成在 `apps/server/dist`、声明为缓存输出，且安装后无需仓库相对路径即可读取 Design v2 Schema

### Requirement: 现有 API 契约等价

`apps/server` SHALL 实现现行 `user-authentication`、`project-conversations`、`ai-chat` 和 DesignDocument 校验行为，并 SHALL 保持与 `apps/api` 相同的公开路由、JSON 字段、HTTP 状态码、错误码、Cookie 属性、SSE 事件顺序与终态、AI 历史选择、请求限制、数据库写入和取消语义。删除 Go runtime 后，持续回归测试 MUST 使用删除前冻结且可审查的契约 fixture，而不是要求 Go 进程继续存在。

#### Scenario: 相同契约 fixture

- **WHEN** Python runtime 接收覆盖成功、校验失败、未认证、冲突、上游失败和中断的冻结请求 fixture
- **THEN** 其状态码、响应字段、错误码、SSE 事件和数据库结果符合现行 OpenSpec

#### Scenario: 删除后运行契约回归

- **WHEN** Go runtime 不再存在且开发者运行 Server 测试
- **THEN** 冻结契约回归仍可独立执行，且不会因缺少 `GO_PARITY_API_URL` 被跳过
