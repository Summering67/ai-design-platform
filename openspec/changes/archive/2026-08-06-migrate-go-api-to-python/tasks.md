## 1. 固化双实现基线与迁移规则

- [x] 1.1 确认目标部署环境支持的 Python 小版本和依赖安装方式，并将结论写入 `apps/server/migration/rules.md`，在确认前不使用小版本专属能力
- [x] 1.2 在 `apps/server/migration/rules.md` 记录 `apps/api` 只读基准与 `apps/server` 目标边界，以及 Gin→FastAPI、GORM→SQLAlchemy 2 + psycopg 3、Zap→`logging`、Viper→Pydantic Settings + PyYAML、Go Modules→`uv` 的完整替换规则
- [x] 1.3 从 `apps/api` 的 21 个 Go 源/测试文件、`go.mod/go.sum`、配置、SQL migration、任务配置、4 份 API OpenSpec、Web rewrite 与调用代码生成 `apps/server/migration/dependency-map.md`，为每项记录 `apps/server` 目标、依赖、缺口和环检测结论
- [x] 1.4 从依赖清单生成 `apps/server/migration/queue.md`，为每项分配稳定 ID、波次、Go 来源、Python 目标、前置项、契约、验证类型、状态、阻塞原因和等价证据字段，状态只允许推进至 `verified`
- [x] 1.5 【单元测试】运行现有 Go 单元测试并记录脱敏基线结果；失败项保持阻塞，且不得修改 `apps/api` 修复非本任务问题
- [ ] 1.6 【集成测试】运行现有 Go 集成测试并保存 HTTP、SSE、DesignDocument 与可用 PostgreSQL 场景的冻结 fixture；缺少测试 DSN 时记录风险并阻塞等价结论

## 2. 建立 apps/server Python workspace

- [x] 2.1 新建 `apps/server/AGENTS.md`，定义 FastAPI/Uvicorn/Pydantic Settings/PyYAML/SQLAlchemy 2/psycopg 3/HTTPX/`logging`/`uv` 边界，并明确禁止修改或依赖 `apps/api` 内部文件
- [x] 2.2 在 `apps/server` 创建 package 名 `server` 的 `package.json`、`turbo.json`、`pyproject.toml`、`uv.lock` 及 `src/ai_design_server`/`tests` 布局，锁定运行与开发依赖且不创建并列依赖清单
- [x] 2.3 为 `apps/server` 提供 `dev:standalone`、`build`、`lint`、`check-types` 和 `test` 定向任务，构建输出声明为 `apps/server/dist/**`；本次不添加根 `dev` 会自动执行的 `dev` 脚本
- [x] 2.4 实现 Pydantic Settings + PyYAML 强类型配置，保持默认值<YAML<开发兼容变量<`API_*`、跨字段校验和安全示例；禁止业务模块直接读取环境或 YAML
- [x] 2.5 实现标准 `logging` JSON formatter/Filter、FastAPI 访问日志中间件和集中 exception handler，保持 Zap 等价字段、级别、单次错误记录与脱敏
- [x] 2.6 实现共享 Pydantic DTO、稳定领域错误、UUID/UTC 转换和 HTTP 错误映射，使用 `extra="forbid"` 并将默认 422 转换为既有 400
- [x] 2.7 迁移 DesignDocument v1/v2 解析、Schema 定位和结构化校验错误，只读取 `packages/design-contract` 权威 Schema
- [ ] 2.8 【单元测试】覆盖配置优先级、日志脱敏、DTO 未知字段、FastAPI validation/exception handler、UUID/UTC 和 DesignDocument fixture

## 3. 迁移数据库与 AI 客户端

- [x] 3.1 实现 SQLAlchemy 2 `AsyncEngine`、psycopg 3 async driver、连接池参数、`async_sessionmaker`、ping 超时和 lifespan 关闭；禁止 `metadata.create_all()`、Alembic 或复制 `apps/api/migrations`
- [x] 3.2 逐条将 GORM Model、查询、事务、`ErrRecordNotFound` 与约束冲突映射为 SQLAlchemy typed model/显式 statement、`AsyncSession` 事务和稳定领域错误，并链接原 SQL migration
- [x] 3.3 分离 SQLAlchemy Model 与 Pydantic DTO，禁止隐式 lazy loading 和跨请求/并发任务共享 Session；仅在无法安全表达 PostgreSQL 特性时使用参数化 `text()` 并记录理由
- [x] 3.4 实现 Chat Completions 请求模型、最近完整轮次、总内容上限和失败/中断历史排除算法
- [x] 3.5 实现 HTTPX 上游流客户端、鉴权、独立超时、有界响应、SSE 解析、取消传播和稳定错误转换
- [ ] 3.6 【单元测试】覆盖 AI 消息校验、历史窗口、整轮裁剪、请求转换、上游非 2xx、畸形流、空回复、超时和取消
- [ ] 3.7 【集成测试】使用 HTTPX mock transport 验证上游边界，并使用隔离测试 DSN 验证 SQLAlchemy Engine/Session 生命周期、Model 映射、事务、约束错误和稳定排序

## 4. 迁移认证领域

- [x] 4.1 实现固定用户、七天会话、随机 Token、SHA-256 哈希、恒定时间密码比较、登录、当前用户和单会话退出领域函数
- [x] 4.2 使用领域 `APIRouter` 与 FastAPI `Depends` 实现登录、认证、当前用户和退出路由，保持 `aidp_session` 名称、Path、HttpOnly、SameSite、Max-Age、状态码和错误码
- [ ] 4.3 【单元测试】覆盖登录输入、错误凭据、Token 哈希、会话过期、空 Token、错误映射和 Cookie 属性
- [ ] 4.4 【集成测试】使用 ASGITransport 与隔离测试 DSN 覆盖登录、`/api/auth/me`、单会话退出、多会话隔离和匿名保护边界

## 5. 迁移项目、消息与 generation

- [x] 5.1 实现最近项目与完整历史查询，保持用户归属、最多 20 条、稳定排序及失败/中断临时文本排除
- [x] 5.2 实现首次消息原子创建项目/消息/attempt 与后续消息创建，保持客户端消息 ID 幂等、运行中冲突和租约过期处理
- [x] 5.3 实现上下文轮次选择、助手消息原子提交、generation 完成、失败和中断终结
- [x] 5.4 实现停止与显式重新生成，保持项目所有权、终态幂等、已完成消息冲突和不自动重试规则
- [x] 5.5 使用 `APIRouter` 实现项目 JSON 路由并使用 `StreamingResponse` 实现 generation SSE，保持事件顺序、唯一终态、限制、错误码和断开取消
- [ ] 5.6 【单元测试】覆盖标题、请求限制、历史选择、领域错误映射、SSE 编码、失败/停止终态和重新生成规则
- [ ] 5.7 【集成测试】使用隔离测试 DSN 覆盖项目归属、事务原子性、重复消息、单项目运行唯一约束、租约、完成/失败/中断和稳定排序
- [ ] 5.8 【集成测试】使用 ASGITransport 与 mock 上游覆盖首次生成、后续生成、停止、重新生成、客户端断开及每条流唯一终态

## 6. 组装独立 FastAPI 服务

- [x] 6.1 实现无模块级可变资源的 FastAPI 应用工厂、领域 `APIRouter`、中间件、exception handler、健康检查、认证保护和全部现有路由，不注册旧匿名 `/api/chat`
- [x] 6.2 使用 lifespan 实现配置→日志→SQLAlchemy Engine/Session factory→HTTPX client→领域→路由的启动顺序和逆序资源释放，资源统一存放于 `app.state`
- [x] 6.3 配置 Uvicorn 独立启动入口和生命周期约束，允许通过配置使用与 Go 不同的验证端口，确保流断开传播到上游和数据库终态
- [ ] 6.4 【单元测试】覆盖 live/ready、ping 超时、异常转换、访问日志、`Depends` 路由保护和旧 `/api/chat` 不匹配
- [ ] 6.5 【集成测试】使用 ASGITransport 覆盖 lifespan 启动/关闭、资源释放、流式断开和进行中请求关闭行为

## 7. Go/Python 等价验证

- [ ] 7.1 建立同一份跨实现契约 fixture 清单，覆盖认证、项目、AI、SSE、健康检查和 DesignDocument，并定义状态码、JSON、Cookie、事件和数据库结果的规范化比较规则
- [ ] 7.2 【集成测试】对 Go 与 Python 分别运行只读 fixture，比较规范化响应并把差异记录为阻塞项
- [ ] 7.3 【集成测试】对 Go 与 Python 使用相同初始数据的隔离数据库或 Schema 分别运行写入 fixture，比较最终数据库状态且禁止并发修改同一记录
- [ ] 7.4 【集成测试】使用现有 Web `chat-api.ts` 请求形状直接验证 `apps/server` 的登录、项目读取、生成、停止和重新生成契约，但不修改 Web rewrite 或 `API_BASE_URL`
- [ ] 7.5 【集成测试】检查 `pyproject.toml` 与 `uv.lock` 一致且可复现安装，实际运行 Ruff、mypy、全部 pytest、wheel 构建和 `server` 定向 Turborepo lint/check-types/build
- [ ] 7.6 【集成测试】运行受影响的根 build/lint/check-types，确认两个 workspace 均通过非持久检查；运行当前根 dev 入口的配置级验证，确认只有 Go `apps/api` 注册为默认后端且不存在端口争用

## 8. 保留 Go 并交付后续切换清单

- [ ] 8.1 核对 `apps/api` 的 Go 源码、测试、`go.mod`、`go.sum`、package/Turbo 配置和运行入口未被本变更修改、删除、移动或重命名；发现差异时提前结束并恢复本任务造成的改动
- [ ] 8.2 将全部来源映射、验证证据、未解决差异和最终 `verified` 状态回写 `apps/server/migration/dependency-map.md` 与 `queue.md`，不得使用 `retired` 表示 Go 已退役
- [x] 8.3 在 `apps/server/migration/root-cutover.md` 记录后续根入口替换所需的 package/Turbo/Web/部署配置变更点、验证前置条件、端口策略和回退到 `apps/api` 的方式，但不执行任何入口替换
- [ ] 8.4 【集成测试】在 `apps/api` 保持可构建的同时重新运行 `apps/server` 单元/集成测试和定向任务，确认 wheel 位于 `apps/server/dist/**` 且两个后端可分别独立验证
- [ ] 8.5 同步本变更的 OpenSpec 与 `apps/server` 文档，明确 Python 后端已达到的等价范围、剩余风险，以及根入口仍指向 Go、切换需由用户另行发起新变更
