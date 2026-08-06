## Context

当前后端是 `apps/server` 下的 Python/FastAPI 应用，现有 AI 能力通过兼容 Chat Completions 的客户端提供文本生成，并由项目 generation 链路管理消息、SSE、取消和持久化。仓库已经将 v2 `DesignDocument` 作为设计文档契约，并提供 DesignGenerationContract、DesignSystemProfile 和渲染派生能力，但尚无负责需求理解、结构化 UI 生成、规范修正和自动布局的运行时。

LangGraph 应作为 FastAPI 应用内部的深模块放入 `apps/server/src/ai_design_server/agents`。该模块只拥有 Agent 单次运行状态，不拥有用户、项目、DesignDocument 或消息的持久化事实；FastAPI、项目 generation 和数据库模块只通过 runner 接口调用它，不感知节点、边或 prompt。

顶层数据流由 Root Supervisor 按当前状态动态选择，数据依赖约束可形成以下可执行关系：

```text
ProductRequirementInput
  → Root Supervisor
  → registered specialist tasks selected by the model
  → StandardizedPRD / Initial v2 DesignDocument / ValidationReport / Corrected v2 DesignDocument / Final v2 DesignDocument
  → mandatory deterministic final gate
  → AgentRunResult
```

## Goals / Non-Goals

**Goals:**

- 建立 Root 调度图和四个职责单一、可独立测试的 LangGraph 子图。
- 让所有子图通过版本化 JSON Schema 交接，拒绝自由格式中间结果。
- 复用现有 v2 `DesignDocument` 和 `DesignGenerationContract`，保持设计文档单一事实源。
- 在生成前固定 Profile ID、版本和摘要，并在生成、修正、布局与最终验收中保持不变。
- 支持流式状态事件、超时、调用方取消、有限重试和稳定错误映射。
- 以 Flex 约束和确定性后处理实现可验证的 Auto Layout，而不是只依赖提示词描述布局。

**Non-Goals:**

- 不在本变更中修改现有 FastAPI 公开路由、项目消息行为或数据库结构。
- 不实现 Agent checkpoint、跨进程恢复、人工审批、长期记忆或 LangSmith 托管部署。
- 不实现 Figma 文件导入导出、约束求解器的全部 Figma 私有行为、自由拖拽编辑或协作编辑。
- 不增加第二种 UI 文档格式，不让 Agent 输出绕过 v2 Schema 与 Profile 校验。
- 不在本变更中实现 Web 端 Agent 进度或设计结果展示。

## Decisions

### 在 `apps/server` 内建立 Agent 深模块

目录按应用和领域组织：

```text
apps/server/
├── pyproject.toml
├── uv.lock
├── src/ai_design_server/
│   ├── app.py
│   ├── config.py
│   ├── chat/
│   └── agents/
│       ├── __init__.py
│       ├── graph.py
│       ├── state.py
│       ├── events.py
│       ├── runner.py
│       ├── contracts.py
│       ├── requirement/{graph.py,nodes.py,prompts.py}
│       ├── ui_design/{graph.py,nodes.py,prompts.py}
│       ├── specification/{graph.py,nodes.py,prompts.py}
│       └── auto_layout/{graph.py,nodes.py,prompts.py,layout.py}
└── tests/agents/
    ├── unit/
    └── integration/
```

`apps/server` 继续使用现有 `pyproject.toml` 与 `uv.lock`，只新增 LangGraph 和实际需要的模型适配依赖，复用现有 FastAPI、Uvicorn、Pydantic、HTTPX 与 jsonschema。备选方案是另建 Agent 微服务；当前四个智能体与项目 generation 处于同一业务和取消链路，拆服务会过早引入内部认证、网络重试和部署复杂度，故不采用。

### Root 是模型驱动的 Supervisor，不是固定顺序调度图

Root 以 `StateGraph` 注册四个专业子图和最终门禁，由模型根据当前状态选择下一项任务。它只负责：

- 发现已注册的 Agent 能力及其输入/输出 Schema；
- 检查被选任务的输入是否存在并通过契约校验；
- 创建带父子谱系的任务身份并派发一个或多个可执行子图；
- 根据完成事件、校验报告和剩余目标重新选择任务；
- 对允许重试的结构化输出错误执行至多一次同任务重试；
- 将不可恢复错误、超时和取消收敛为唯一终态；
- 在产生 `result` 前强制调用最终门禁并汇总最终 PRD、校验报告和 UI 文档。

模型可以改变四个专业 Agent 的执行顺序、重复调用同一能力或并行调用输入独立的能力，但不能调用未注册能力、绕过数据依赖、Schema/Profile 校验或最终门禁。执行额度、最大任务深度、最大任务数和循环检测由 Runtime 强制执行，不能由 prompt 放宽。

### 每个专业智能体是具有窄输入输出的子图

四个智能体均以构图函数暴露编译后的子图，不把内部节点、prompt 或模型消息暴露给 Root：

- Requirement Agent：原始需求 → `StandardizedPRD`。
- UI Design Agent：`StandardizedPRD + DesignGenerationContract` → 初始 v2 `DesignDocument`。
- Specification Validation Agent：UI 文档 + 固定 Profile 约束 → `ValidationReport + Corrected v2 DesignDocument`。
- Auto Layout Agent：已修正文档 + PRD 响应式需求 + 布局能力 → 最终 v2 `DesignDocument`。

子图默认无跨调用记忆，单次运行状态由父图继承；第一阶段不配置持久化 checkpointer。这样项目对话和设计文档仍由现有后端负责，LangGraph 不形成第二套长期事实源。

### Graph State 与运行依赖分离

Graph State 使用 `TypedDict` 保存可序列化业务状态：run ID、固定 Profile 引用、任务目录、活动任务、已完成任务摘要、标准 PRD、初始/修正/最终 UI 文档、校验报告、重试计数和错误。模型客户端、Schema validator、时钟、事件写入器和取消上下文通过 LangGraph runtime context 注入，不进入 checkpoint/state，也不使用全局可变对象。

所有节点优先使用异步函数和提前返回。除 Pydantic 配置/传输模型及框架要求外，不创建类层级。

### 使用共享 JSON Schema 作为跨智能体交接契约

在 `packages/design-contract/schema/v2` 新增：

- `standardized-prd.schema.json`：目标用户、问题、目标、范围、页面、用户流程、内容、组件需求、交互、状态、响应式要求、可访问性要求、约束、假设和未决问题。
- `ui-validation-report.schema.json`：总体结果、问题列表、严重级别、稳定错误码、JSON Pointer 路径、修复状态和摘要。
- `agent-run-event.schema.json`：run、stage、progress、result、failed、cancelled 事件及其最小载荷。

初始、修正和最终 UI 均使用既有 `design-document.schema.json` v2。Agent 不得自行复制或简化 Schema；`apps/server` 从共享包加载并验证。Schema fixture 同时用于 Python 与 TypeScript 消费方的集成测试。

### UI 生成绑定固定 DesignGenerationContract

调用方必须提供已解析的 `DesignGenerationContract`，其中携带固定 Profile ID、版本和摘要。UI Design Agent 只能使用其中允许的节点、Token、组件、variant、图标和布局能力。所有后续子图必须保持同一 Profile 引用，发现替换、摘要漂移或缺失时立即失败。

GenerationContract/Profile 的现有 fixture 仅作为输入约束来源；Agent 的文档输入输出统一使用 v2，不在 Agent 内复制 legacy Tree 契约或迁移逻辑。

### 规范校验采用“确定性检测—模型修正—确定性复验”

规范校验子图先执行 JSON Schema、Profile、引用、ID、父子关系、组件属性、Token、可访问性和布局能力检查，再把可修正问题与最小必要文档上下文交给模型。模型返回完整候选文档后重新执行全部确定性检查。

错误分为：

- `repairable`：缺少允许的基础样式、可访问性文本、合法组件属性或可确定修复的引用。
- `fatal`：Profile 漂移、未知组件、无法满足的业务约束、结构循环、节点超限或修复后仍不合法。

不得通过删除核心页面、放宽 Profile、替换设计系统或静默忽略问题来宣称通过。报告保留检测到的问题和修复结果；Supervisor 可根据报告重新调用规范校验、UI 设计或 Auto Layout，但最终文档只能在确定性复验通过后进入最终门禁。

### Auto Layout 使用模型规划与确定性布局变换的混合方式

Auto Layout Agent 先根据 PRD、节点语义和 Profile 布局能力生成结构化布局计划，随后由纯函数 `layout.py` 应用计划并验证：

- Flex 方向、主轴/交叉轴对齐、间距、内边距和换行；
- hug、fill、fixed 等受契约允许的尺寸策略；
- 嵌套容器、兄弟顺序和稳定节点 ID；
- 响应式断点下的方向、间距、可见性和尺寸覆盖；
- 图层层级、父子引用、非容器叶子节点和最大嵌套深度。

布局阶段不得改变业务文案、组件语义、Profile 引用和稳定节点 ID；确需增加布局容器时使用确定性派生 ID，并记录到运行结果。最终结果再次经过 Schema、Profile 和结构门禁。备选方案是让模型直接重写整份文档；该方案难以保证 ID 稳定和局部变更，故不采用。

### Runner 接口只暴露稳定事件

`agents/runner.py` 提供异步流式函数接口，接收原始产品需求、固定 `DesignGenerationContract`、run ID 和资源限制，只产出符合 `agent-run-event` 的事件，不暴露 LangGraph 节点名、模型原始响应、prompt、内部路径或上游错误。FastAPI lifespan 构建 Graph 和共享依赖，具体路由或 generation 调用方只依赖 runner 函数。

调用方断开、显式取消或超时时，取消信号必须传播到父图、当前子图和上游模型请求，并只产生一个 `cancelled` 或 `failed` 终态。运行输入、事件和输出设置字节、节点、深度、重试和总耗时上限。

### 配置和密钥只由 Agent Runtime 加载

模型 BaseURL、API Key、Model、节点超时、总运行超时和资源上限只在 `apps/server/config.py` 解析。Agent 业务模块只接收已校验配置和 lifespan 注入的模型依赖，不直接读取环境变量或 YAML。示例配置不包含真实凭证；日志不得记录 prompt 全文、产品需求正文、模型原始响应、Authorization Header 或 API Key。

## Risks / Trade-offs

- [LangGraph 增加现有 FastAPI 进程的内存与关闭复杂度] → Graph 在 lifespan 中构建一次，单次运行状态隔离，取消信号传播到所有子图和模型请求，并设置节点、字节和总运行上限。
- [正在进行的生成契约变更尚未完成] → 实施前先完成 `complete-preview-data-model` 的相关契约任务，并通过共享 fixture 锁定 Profile 与 Schema 版本。
- [模型结构化输出仍可能无效] → 每个交接点执行 JSON Schema 校验，规范校验和 Auto Layout 采用确定性后处理，有限重试后失败关闭。
- [Auto Layout 无法完全复刻 Figma] → 明确 MVP 只覆盖可契约化的 Flex、尺寸、换行、对齐、嵌套和响应式语义；未覆盖行为作为显式错误而非猜测。
- [无 checkpointer 时进程重启会丢失运行] → 第一阶段由调用方重新发起幂等 run；跨进程恢复与人工中断单独设计，避免提前引入持久化事实源。
- [大型 UI 文档导致 Token 与延迟膨胀] → 设置页面、节点、深度、字节和总运行时间上限，并只向修正节点传递必要上下文。
- [模型修正破坏稳定 ID 或业务语义] → 修正前后执行不可变字段对比，违规结果拒绝进入下一阶段。
- [runner 暂未接入公开 generation] → 通过模块级集成测试完成可执行闭环，后续以单独 OpenSpec 变更决定 SSE 事件和设计文档持久化，避免本变更隐式修改公开契约。

## Migration Plan

1. 核对并冻结现有 v2 DesignDocument、DesignSystemProfile 和 DesignGenerationContract fixture。
2. 新增共享 PRD、校验报告、运行事件 Schema 及跨语言 fixture。
3. 在 `apps/server` 中建立 Agent 配置、模型适配、契约加载和 runner 接口，并由 FastAPI lifespan 构建共享只读依赖。
4. 分别实现并验证四个子图，再接入模型驱动 Root Supervisor。
5. 通过完整流水线集成测试后保留现有公开 generation 行为；后续接入 runner 时再同步更新公开契约。

回滚时移除 `apps/server` 的 Agent 模块注册及新增依赖即可；现有 FastAPI 路由、数据库和公开契约未变化。共享新增 Schema 保留不会改变旧文档语义。

## Open Questions

- 现有项目 generation 后续是整体切换到 Root runner，还是新增独立设计 generation 类型，需要结合 Web 展示与持久化契约另立变更决定。
- 最终 v2 `DesignDocument` 的项目级持久化位置、版本历史和与 assistant 消息的关联尚未定义，不在本变更中假设数据库结构。
