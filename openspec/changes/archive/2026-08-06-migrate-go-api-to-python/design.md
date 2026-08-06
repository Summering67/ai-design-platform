## Context

`apps/api` 当前约 2,406 行 Go，由 21 个源文件组成。内部 import 形成以下主路径：`config → database/logging`，`chat` 独立依赖外部 HTTP，`auth → database`，`project → database + auth + chat`，`server → config + database + logging + chat + auth + project`，`cmd/server → server`；`design` 目前没有接入运行时路由，但依赖仓库中的 DesignDocument JSON Schema。Web 只通过 `/backend/api` 调用既有 JSON、SSE 和 Cookie 接口，PostgreSQL Schema 由显式 SQL migration 管理。

本次在不修改 `apps/api` 的前提下新增 `apps/server`。两个应用实现相同 API 能力，但当前根入口、Web rewrite 和部署仍指向 Go；Python 只通过定向命令、进程内 ASGI 测试或隔离端口验证。迁移过程必须保持 `ai-chat`、`project-conversations`、`user-authentication` 以及数据库 Schema 的行为不变，并遵守仓库不新增数据库基础设施、不泄露敏感配置、只使用单元测试和集成测试验收的约束。

## Goals / Non-Goals

**Goals:**

- 在编码前形成可审查的迁移规则、完整依赖清单和可执行迁移队列。
- 在 `apps/server` 使用 FastAPI 重建 API，并保持现有路由、JSON 字段、错误码、Cookie、SSE 事件、超时、并发、事务与数据库行为。
- 让每个迁移项都能从 `apps/api` Go 源文件追踪到 `apps/server` Python 目标、依赖、契约和双实现测试证据。
- 完整保留 `apps/api` 作为可运行基准和备份，不改变其源码、依赖、任务或部署入口。
- 让 `apps/server` 可独立构建和定向验证，但不自动加入当前根 `dev` 进程图。

**Non-Goals:**

- 不修改公开 HTTP/SSE 契约、Web 工作台行为、数据库表结构或已应用 migration。
- 不引入后台生成队列、自动重试、注册系统、多用户模型或新的部署基础设施。
- 不在迁移过程中顺带重构 DesignDocument、认证或项目对话领域规则。
- 不修改根项目入口、Web `API_BASE_URL`、当前部署指向或 `apps/api` package/Turbo 配置。
- 不删除、移动、重命名或退役任何 Go 文件、Go Modules 元数据或 `go-api-runtime` 契约。
- 不在本次变更中执行生产切流；后续切换由用户发起的独立变更处理。

## Decisions

### 1. 以三份版本化文档驱动迁移

在 `apps/server/migration/` 创建：

- `rules.md`：双实现边界、迁移原则、禁止事项、代码映射、数据与时间语义、安全、测试和后续切换前置条件。
- `dependency-map.md`：源文件清单、内部/外部依赖、路由与配置消费者、数据库对象、OpenSpec/Web 调用方及环检测结果。
- `queue.md`：稳定队列 ID、源文件、Python 目标、前置 ID、对应契约、测试类型、状态、阻塞原因与完成证据。

Markdown 便于仓库审查，不增加只为读取队列而存在的工具或依赖。队列只允许 `pending → ready → in_progress → verified`；依赖未全部 `verified` 时不得进入 `in_progress`。`verified` 仅表示 `apps/server` 目标通过等价验证，不授权删除或修改 `apps/api` 来源。备选方案是原地改写 `apps/api`，但会丢失可运行基准和逐项比对能力，因此不采用。

### 2. 依赖分析覆盖代码与契约，不只读取 Go import

清单以当前仓库事实为输入，至少覆盖：21 个 Go 源/测试文件、`go.mod/go.sum`、SQL migration、配置示例、API package/Turbo 配置、4 份现行 API OpenSpec、Web rewrite 与 `chat-api.ts` 调用。依赖类型分为 `imports`、`calls`、`routes`、`configures`、`persists`、`validates`、`tests`、`consumed-by`。

迁移拓扑按强依赖排序；测试文件跟随其生产目标，不单独决定生产顺序。所有目标路径均位于 `apps/server`，当前队列波次固定为：

1. 契约基线与三份迁移文档。
2. Python 工程元数据、纯 DTO/错误、配置、日志和 DesignDocument 校验。
3. PostgreSQL 连接、Chat Completions 客户端及其单元测试。
4. 认证领域及 HTTP 边界。
5. 项目/消息/generation 事务、并发、SSE 与停止语义。
6. 路由、健康检查、进程生命周期和 Turborepo 任务。
7. 跨实现契约集成测试、Python 独立 workspace 验证与后续根入口切换清单。

备选方案是按文件名一一映射；它会固化 Go 的偶然拆分，且无法在 Python 中保持浅模块边界，因此目标文件允许多对一或一对多，但队列必须保留完整来源追踪。

### 3. Python runtime 使用 FastAPI + Uvicorn + Pydantic + SQLAlchemy + psycopg + HTTPX

Python 包采用 `apps/server/src/ai_design_server` 布局和函数式模块边界：FastAPI/Starlette 提供 ASGI、`APIRouter`、中间件、Cookie 与 `StreamingResponse`；Uvicorn 承载进程；Pydantic/Pydantic Settings 负责严格 DTO 与强类型配置；SQLAlchemy 2 typed ORM/表达式 API 负责持久化模型、查询和事务，psycopg 3 作为 PostgreSQL async driver；HTTPX 负责带取消和超时的上游流；`jsonschema` 复用仓库权威 DesignDocument Schema。应用服务优先使用函数和小型不可变数据结构，只有框架模型、协议或资源持有者使用类。

现有 Go 技术栈必须按以下矩阵迁移，不允许在实现阶段静默更换目标：

| 当前技术 | Python/FastAPI 目标 | 必须保留的行为 |
| --- | --- | --- |
| Gin | FastAPI/Starlette | 路由、认证保护、严格请求解析、Cookie、错误映射与 SSE |
| Go `http.Server` | Uvicorn + FastAPI lifespan | 监听地址、超时约束、信号、优雅关闭与资源释放 |
| GORM + PostgreSQL Driver | SQLAlchemy 2 `AsyncEngine`/typed ORM/表达式 API + psycopg 3 async driver | 表/约束、事务、错误分类、稳定排序、租约与连接生命周期 |
| Zap | Python 标准 `logging` + 自定义 JSON formatter | 结构化字段、级别、请求日志、单次错误记录与敏感信息过滤 |
| Viper | Pydantic Settings + PyYAML | YAML、`API_*`、开发兼容变量、优先级、默认值与启动校验 |
| Go Modules | `uv` + `pyproject.toml` + `uv.lock` | 直接/开发依赖声明、完整版本锁定、可复现安装与无漂移检查 |
| `go test` / `go vet` | pytest + Ruff + mypy | 单元/集成测试、静态检查与类型检查 |

Gin→FastAPI 的边界映射固定如下：

- Gin 路由组映射为领域 `APIRouter`，路由注册只发生在应用工厂，不允许领域模块反向导入应用入口。
- Gin 认证中间件映射为 FastAPI `Depends` 依赖；依赖只解析并返回当前用户，不在依赖函数中隐藏业务事务或吞掉领域错误。
- Gin Handler 映射为薄路径函数，只负责 Pydantic 输入、路径参数、依赖调用和响应转换；业务函数不得接收 FastAPI `Request`。
- `json.Decoder.DisallowUnknownFields` 映射为 Pydantic `extra="forbid"`，FastAPI 默认 422 校验响应必须经异常处理器转换为现有 HTTP 400 与 `invalid_request`。
- Gin 错误写入映射为领域异常到 FastAPI exception handler 的集中转换，响应不得暴露 Pydantic、psycopg、HTTPX 或内部堆栈细节。
- 启动和关闭资源映射为应用工厂提供的 FastAPI `lifespan`；SQLAlchemy `AsyncEngine`、Session factory 与 HTTPX client 存放在 `app.state`，禁止模块级可变单例。
- Gin 流写入映射为 `StreamingResponse`；流生成器在发送增量前后检查请求断开，并将取消传播到 HTTPX 与 generation 中断逻辑。

备选 Flask 需要额外拼装异步流、依赖注入和生命周期边界；Django 引入本次不需要的 ORM、管理后台和项目结构，因此均不采用。FastAPI 与现有严格 JSON、依赖保护和 SSE 边界更直接，但框架默认的 422 和 OpenAPI 行为不得改变现有公开契约。

数据库采用 SQLAlchemy 2 的 typed declarative model、`AsyncEngine`、`async_sessionmaker` 和显式 `select`/`update` 表达式；psycopg 3 仅作为 PostgreSQL async driver。现有 GORM Model、链式查询、事务、`ErrRecordNotFound`、唯一冲突、稳定排序和连接池配置必须在依赖清单中逐条映射到 SQLAlchemy model/statement、`session.begin()` 事务和稳定领域错误。

SQLAlchemy 持久化 Model 与 Pydantic 请求/响应 DTO 严格分离；关系默认不得依赖隐式 lazy loading，查询显式加载所需数据；事务边界由领域服务控制，FastAPI `Depends` 只提供请求级 `AsyncSession`，不得自动提交或吞掉异常。`IntegrityError`、`NoResultFound` 等 SQLAlchemy 异常必须在数据库/领域边界转换，不得泄露到 Handler、响应或日志。

现有 `apps/api/migrations/*.sql` 继续是两个后端共同的数据库 Schema 唯一事实源，`apps/server` 只引用这些 migration，不复制或修改它们。实现不得调用 `metadata.create_all()`、不得使用自动建表，也不新增 Alembic 作为并列 migration 系统。只有 PostgreSQL 特有锁或表达式无法安全表达时才允许通过 SQLAlchemy 的参数化 `text()`，并必须在依赖清单说明原因和集成测试证据。

配置由 Pydantic Settings 组装强类型模型，PyYAML 只负责安全读取 YAML 原始值；显式合并层负责保持“默认值 < YAML < 开发兼容变量 < `API_*`”顺序，业务模块不得读取环境变量或 YAML。日志使用标准库 `logging`，由集中 JSON formatter 和 Filter 生成稳定字段并脱敏；不引入与 Zap 并列的多个日志门面。

依赖与工具统一由 `uv` 管理：运行与开发依赖声明在 `pyproject.toml`，完整解析结果提交到 `uv.lock`，安装、检查、测试和构建均从锁文件解析。Ruff 执行格式/静态检查，mypy 执行类型检查，pytest 执行单元测试与集成测试，wheel 输出到 `apps/server/dist/**`。`requirements.txt`、Pipenv、Poetry 或未锁定的裸 `pip install` 不作为并列依赖事实源。

### 4. 外部契约冻结，内部按领域重建

`apps/server/src/ai_design_server` 按 `config.py`、`database.py`、`logging.py`、`chat/`、`auth/`、`project/`、`design/`、`server.py` 和 `main.py` 分层；FastAPI path operation/APIRouter 只解析输入和转换响应，业务函数不依赖 FastAPI，请求断开与取消信号通过显式参数传递到数据库和 HTTPX。

以下内容作为冻结基线：现有路由与方法、未知字段拒绝、状态码和错误码、`aidp_session` 属性与七天固定期限、UUID/UTC 时间语义、PostgreSQL 表/索引/约束、generation 单项目串行化与租约、SSE 事件顺序与唯一终态、AI 历史窗口和内容限制、环境变量优先级及健康检查 JSON。Python 不直接复用 Go 内部类型；以 OpenSpec、SQL migration、Web 消费代码和固定 fixture 为边界事实。

### 5. 使用单元与集成测试建立等价证据

先保存 Go 基线测试结果和契约 fixture，再为 Python 建立对应测试矩阵。单元测试覆盖配置、FastAPI/Pydantic 错误映射、消息窗口、Token 哈希、DTO 严格校验、SSE 编解码和 DesignDocument 校验；集成测试通过 HTTPX `ASGITransport` 覆盖 FastAPI 路由、`Depends`、lifespan、Cookie、流式断开、HTTPX mock transport、PostgreSQL 事务/约束、generation 并发与停止。跨实现验证对同一 fixture 分别运行 Go 与 Python 边界，比较规范化状态码、JSON、Cookie、SSE 事件和数据库结果。

涉及写数据库的跨实现测试必须使用隔离数据库或独立 Schema，并在每个实现运行前恢复相同初始 fixture，禁止让两个后端并发修改同一测试记录。网络级并行验证使用不同监听端口；优先使用 Go `httptest` 与 Python ASGITransport，避免端口争用。

不使用浏览器、E2E、视觉回归或人工 UI 验收。需要真实 PostgreSQL 的集成测试只接受显式测试 DSN，缺失时报告未运行而不得宣称通过；Go 删除门禁要求这些数据库集成测试已有实际通过证据。

### 6. 双实现 workspace 与根入口隔离

`apps/api` 继续使用 package 名 `api` 和当前 `dev/build/lint/check-types`。`apps/server` 使用独立 package 名 `server`，提供 `dev:standalone`、`build`、`lint`、`check-types` 和 `test`；当前阶段不提供会被根 `turbo run dev` 自动发现的 `dev` 脚本，避免根开发流程同时启动两个默认监听相同地址的后端。

根 `pnpm`/Turborepo 配置、Web rewrite、`API_BASE_URL` 与部署入口均保持不变。Python 等价验证完成后，只生成一份后续切换清单，包含根入口变更点、端口/环境配置、验证证据和回退到 `apps/api` 的方式；本变更不执行清单。若用户后续切换，必须建立独立 OpenSpec change 并重新验证受影响入口。

## Risks / Trade-offs

- [Go 与 Python 的 JSON、时间、Cookie 或取消语义细节不同] → 使用冻结 fixture 和边界集成测试逐项比对，不以框架默认值替代显式配置。
- [SSE 断开后异步任务继续运行] → 流生成器监听请求取消，取消 HTTPX 上游并在事务中把 generation 终结为 interrupted。
- [FastAPI 默认返回 422 或自动序列化细节造成契约漂移] → 所有请求模型使用 `extra="forbid"`，集中覆盖 validation/exception handler，并用冻结 fixture 验证 400/401/404/409/500 响应。
- [lifespan 或 Depends 隐藏资源与事务边界] → lifespan 只持有进程级资源，Depends 只解析请求级身份/资源，事务继续由领域服务显式控制。
- [GORM 隐式行为在 SQLAlchemy 中遗漏] → 将每个 Model、查询、事务、预加载和错误分支映射到 typed ORM/显式 statement，并用真实 PostgreSQL 集成测试覆盖约束和并发语义。
- [AsyncSession 被跨请求共享或发生隐式 IO] → 每个请求使用独立 Session，禁止并发任务共享 Session 和隐式 lazy loading，事务由领域服务显式开启。
- [SQLAlchemy Model 与既有 migration 漂移] → SQL migration 保持 Schema 唯一事实源，禁止 `create_all`/Alembic，并以真实 PostgreSQL 元数据和行为集成测试校验映射。
- [Viper 与 Pydantic Settings 的来源优先级不同] → 使用显式来源合并，不依赖框架默认顺序，并以相同配置 fixture 做单元测试。
- [Zap 字段或脱敏策略在 logging 中漂移] → 集中 JSON formatter/Filter，禁止模块自定义格式，并以固定日志记录做单元测试。
- [Go Modules 替换后依赖不可复现] → `pyproject.toml` 与 `uv.lock` 同步提交，CI/任务入口检查锁文件一致性且禁止浮动安装。
- [SQLAlchemy 映射或事务错误破坏并发约束] → 复用既有 migration，不改 Schema，并用真实 PostgreSQL 集成测试覆盖唯一索引、锁、租约和原子提交。
- [迁移队列失真或漏掉非 import 依赖] → 将路由、配置、Schema、OpenSpec、Web 消费与测试边一起纳入清单，并在每次队列状态变化时校验来源覆盖和环。
- [两个 workspace 在根 dev 中争用同一端口] → `apps/server` 当前只暴露 `dev:standalone`，不修改根入口；并行网络验证使用隔离端口。
- [两个实现并发写同一测试数据导致错误差异] → 使用隔离数据库/Schema 和相同初始 fixture，按实现分别执行并比较规范化结果。
- [等价验证被误解为已完成生产切换] → 队列只到 `verified`，明确禁止本变更修改根入口、Web 指向或删除 Go。
- [Python 运行时吞吐与内存特征不同] → 本次以契约正确性为准，保留显式超时、连接池与有界响应；性能基准未建立时记录为风险，不擅自改变并发模型。

## Migration Plan

1. 固化现有 OpenSpec、SQL、Web 调用与 Go 测试基线，在 `apps/server/migration` 创建并审查三份迁移治理文档。
2. 在 `apps/server` 建立 Python 工程和基础模块，按队列前置关系逐项实现；每项只有在对应单元测试或集成测试通过后标记 `verified`。
3. 完成 auth、project、chat、design、server 的全部等价实现，并运行跨模块契约集成测试和 PostgreSQL 集成测试。
4. 注册独立 `server` workspace，构建 `apps/server/dist/**` wheel并验证定向任务，同时确认根 `dev` 仍只使用 Go API。
5. 对两个实现运行相同 fixture，记录等价证据、未解决差异和隔离数据库结果。
6. 保留 `apps/api` 全部内容，交付后续根入口替换清单；等待用户另行发起切换。

## Open Questions

- 目标部署环境可用的 Python 小版本与安装方式需要在实现第一项中确认并锁定；在确认前不得选择依赖该小版本独有语法或二进制包。
- 当前仓库未提供统一 PostgreSQL 集成测试环境；实现阶段必须确认可用的隔离测试 DSN，若无法提供则双实现数据库等价结论保持阻塞并明确风险。
