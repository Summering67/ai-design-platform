## ADDED Requirements

### Requirement: 迁移规则手册

系统 SHALL 在迁移任何生产模块前，在 `apps/server/migration/rules.md` 维护一份版本化迁移规则手册，明确 `apps/api` 只读基准与 `apps/server` Python 目标边界、Gin→FastAPI/Starlette、Go `http.Server`→Uvicorn、GORM→SQLAlchemy 2 Async ORM/表达式 API + psycopg 3、Zap→Python `logging` JSON 日志、Viper→Pydantic Settings + PyYAML、Go Modules→`uv` + `pyproject.toml` + `uv.lock` 的替换矩阵，以及框架、Model/DTO/Session/事务、配置、数据库、安全和等价测试规则。手册 MUST 将现有 OpenSpec、`apps/api/migrations` 和外部调用方视为优先于 FastAPI 或 SQLAlchemy 默认行为的迁移依据，并 MUST 禁止本次变更修改根入口或 `apps/api`。

#### Scenario: 开始迁移生产模块

- **WHEN** 迁移者准备将首个 Go 生产模块加入进行中队列
- **THEN** 仓库中已存在覆盖全部必需主题的迁移规则手册，且该队列项引用适用规则和契约

#### Scenario: 框架默认行为与现有契约冲突

- **WHEN** Python 框架的默认 JSON、Cookie、错误或流式响应行为与现有契约不同
- **THEN** Python 实现显式遵循现有契约，并在规则手册记录映射方式

#### Scenario: 基础栈存在未映射能力

- **WHEN** Gin、GORM、Zap、Viper 或 Go Modules 的现有能力尚未找到目标组件和验证方式
- **THEN** 对应迁移项保持阻塞，不得以 FastAPI 默认行为或未锁定依赖替代

### Requirement: 完整文件依赖清单

系统 SHALL 盘点 `apps/api` 的 Go 生产文件、测试文件、模块元数据、配置、SQL migration、任务配置以及直接关联的 OpenSpec 和 Web 调用方。`apps/server/migration/dependency-map.md` SHALL 为每个对象记录职责、内部依赖、外部依赖、路由、配置、数据库对象、被调用方、测试关系和 `apps/server` Python 目标，并 SHALL 标识缺失目标、未解析引用与依赖环。

#### Scenario: 生成依赖清单

- **WHEN** 迁移队列首次建立或源范围发生变化
- **THEN** 每个范围内对象都能在清单中找到唯一条目，且所有依赖边的两端均可解析

#### Scenario: 发现非 import 依赖

- **WHEN** 文件通过路由注册、配置键、数据库对象、JSON Schema、OpenSpec 或 Web 请求被间接依赖
- **THEN** 清单以对应依赖类型记录该边，而不是仅依赖 Go import 结果

#### Scenario: 依赖图存在环或缺口

- **WHEN** 分析发现依赖环、无 Python 目标或无法解析的依赖
- **THEN** 对应对象被标记为阻塞，且不得进入可迁移状态

### Requirement: 拓扑迁移队列

系统 SHALL 在 `apps/server/migration/queue.md` 从依赖清单建立稳定、可审查的迁移队列。每个队列项 SHALL 包含稳定 ID、`apps/api` 来源、`apps/server` 目标、前置 ID、关联契约、验证类型、状态、阻塞原因和等价证据；队列顺序 SHALL 保证依赖先于消费者迁移，并允许多个 Go 文件映射到一个 Python 模块或一个 Go 文件拆分到多个 Python 模块。

#### Scenario: 依赖尚未验证

- **WHEN** 队列项的任一前置项尚未达到 `verified`
- **THEN** 该队列项保持 `pending` 或 `blocked`，不得进入 `in_progress`

#### Scenario: 所有依赖已经验证

- **WHEN** 队列项的全部前置项达到 `verified` 且不存在其他阻塞原因
- **THEN** 该队列项进入 `ready`，并可按稳定队列顺序开始迁移

#### Scenario: 多对一文件映射

- **WHEN** 多个 Go 文件的职责在 Python 中合并为一个内聚模块
- **THEN** 每个源文件仍具有可追踪队列项，并共同引用同一目标与各自验证证据

### Requirement: 状态与证据门禁

系统 SHALL 只允许队列状态按 `pending → ready → in_progress → verified` 前进。生产项只有在其关联的单元测试或集成测试实际通过、与 Go 基准的契约未漂移且证据已记录后才能标记 `verified`；测试未运行、失败或依赖阻塞时 MUST NOT 宣称完成。`verified` MUST NOT 表示 Go 来源可以删除或根入口可以切换。

#### Scenario: 验证实际通过

- **WHEN** 队列项实现完成且关联的单元测试或集成测试已实际通过
- **THEN** 队列记录执行命令、结果和契约证据，并将该项标记 `verified`

#### Scenario: 验证无法运行

- **WHEN** 所需测试环境或测试 DSN 不可用
- **THEN** 队列记录未运行原因与风险，该项保持未验证状态

### Requirement: 双实现保留与根入口边界

系统 SHALL 完整保留 `apps/api` 的 Go 源码、测试、Go Modules、package/Turbo 配置和运行入口，并 SHALL 将 Python 实现放在独立的 `apps/server` workspace。本次变更 MUST NOT 修改根项目入口、Web `API_BASE_URL` 或部署指向，MUST NOT 删除或退役 Go，实现完成后只 SHALL 生成供后续独立变更使用的根入口替换清单。

#### Scenario: Python 实现通过全部验证

- **WHEN** `apps/server` 全部生产项达到 `verified` 且定向检查、构建与 PostgreSQL 集成测试实际通过
- **THEN** 系统记录双实现等价证据和后续切换清单，同时保持 `apps/api` 与根入口不变

#### Scenario: 根开发流程启动

- **WHEN** 开发者使用当前根项目开发入口
- **THEN** 现有 Go `apps/api` 继续作为后端，`apps/server` 不自动启动或争用相同监听端口

#### Scenario: 请求替换根入口

- **WHEN** 用户在等价验证后决定让根项目使用 `apps/server`
- **THEN** 该操作由新的明确变更处理，并重新验证根任务图、Web 指向、部署和回退路径

### Requirement: 双实现等价验证

系统 SHALL 对 Go 与 Python 实现运行相同的契约 fixture，并比较规范化 HTTP 状态、JSON、Cookie、SSE 事件和数据库结果。写数据库的比较 SHALL 使用相同初始数据的隔离数据库或 Schema，MUST NOT 让两个实现并发修改同一测试记录。

#### Scenario: 比较只读请求

- **WHEN** 同一只读 fixture 分别提交给 Go 和 Python 实现
- **THEN** 两个实现返回契约等价的规范化结果

#### Scenario: 比较写入请求

- **WHEN** 同一写入 fixture 需要分别验证两个实现
- **THEN** 每个实现从相同隔离初始状态执行，测试比较最终数据库状态且不存在跨实现数据干扰

### Requirement: 迁移制品安全

迁移手册、依赖清单、队列和验证证据 MUST NOT 包含密码、Token、API Key、Authorization Header、完整 DSN、真实用户敏感信息或未脱敏请求体。

#### Scenario: 记录配置与测试证据

- **WHEN** 迁移制品需要引用环境变量、数据库连接或上游请求
- **THEN** 制品只记录配置键、脱敏类别和非敏感结果，不记录实际敏感值
