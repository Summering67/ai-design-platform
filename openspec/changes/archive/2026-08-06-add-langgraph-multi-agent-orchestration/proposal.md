## Why

当前后端只有面向通用对话的单模型调用，无法把产品需求稳定转换为受设计系统约束、可校验且具备响应式布局的 UI 设计文档。需要引入 LangGraph 多智能体编排，以显式状态、确定性交接契约和可独立验证的子图承载从需求解析到 Auto Layout 的完整生成链路。

## What Changes

- 在现有 Python/FastAPI 应用 `apps/server` 内新增 `ai_design_server.agents` 深模块，承载 LangGraph Runtime、模型适配、流式运行接口和生命周期管理。
- 新增 Root 调度智能体，负责工具选择、状态推进、错误收敛、有限重试和最终结果汇总，不承担任一专业智能体的领域生成逻辑。
- 新增需求解析智能体，把产品需求文本转换为版本化、可校验的标准化 PRD JSON Schema 输出。
- 新增 UI 设计智能体，基于 PRD JSON 与固定版本的 `DesignGenerationContract` 生成初始 v2 `DesignDocument`，覆盖图层结构、组件引用、基础样式和布局意图。
- 新增规范校验智能体，对初始 v2 UI 文档执行 Schema、设计系统 Profile 和跨节点语义校验，输出结构化校验报告及修正后的 v2 `DesignDocument`；无法安全修正时失败关闭。
- 新增 Auto Layout 编排智能体，基于 Flex 约束完成自动排版、响应式断点适配和图层层级整理，输出最终 v2 `DesignDocument`，能力边界对标 Figma Auto Layout 的方向、间距、内边距、对齐、尺寸策略、换行和嵌套容器语义。
- 在 `packages/design-contract` 增加标准 PRD、规范校验报告和 Agent 运行事件的 v2 JSON Schema；初始、修正和最终 UI 均复用现有 v2 `DesignDocument`，不创建并列 UI 文档事实源。
- 为 Root Supervisor 和四个子图增加节点行为测试、结构化输出测试、动态调度测试、失败与取消测试，以及完整运行集成测试。

## Capabilities

### New Capabilities

- `multi-agent-design-orchestration`: 定义 Root 调度图、子图交接、运行状态、事件流、取消、失败和有限重试行为。
- `product-requirement-normalization`: 定义需求解析智能体的输入约束、标准 PRD Schema、缺失信息表达和结构化输出校验。
- `ui-design-agent`: 定义 UI 设计智能体如何从标准 PRD 和设计生成契约产生初始 v2 `DesignDocument`。
- `ui-specification-validation-agent`: 定义规范校验智能体的校验范围、报告格式、可修正规则和修正后文档约束。
- `auto-layout-agent`: 定义 Auto Layout 智能体的 Flex 排版、响应式适配、层级管理和确定性输出要求。

### Modified Capabilities

无。

## Impact

- 修改 `apps/server/pyproject.toml` 与 `uv.lock`，增加 LangGraph 及其实际使用的模型适配依赖；继续复用现有 FastAPI、Uvicorn、Pydantic、HTTPX 和 jsonschema 运行时。
- 在 `apps/server/src/ai_design_server/agents` 新增 Root、四个专业子图、共享状态、契约加载、事件和 runner，并由现有 FastAPI lifespan 构建和注入依赖。
- 修改 `packages/design-contract`，新增 Python 与 TypeScript 可共同消费的标准 PRD、校验报告和运行事件 Schema、固定 fixture 与公开导出。
- 复用 `packages/design-contract/schema/v2/design-document.schema.json`；GenerationContract/Profile 仅作为既有输入约束，Agent 的 UI 输入输出统一使用 v2 文档契约。
- 本变更不修改现有公开 HTTP 路由、数据库结构或 Web 交互；多 Agent runner 先形成可由后端 generation 层调用的稳定模块接口，项目级公开接入留给后续显式变更。
