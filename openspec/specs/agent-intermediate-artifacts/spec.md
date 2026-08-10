# agent-intermediate-artifacts Specification

## Purpose

定义 UI Design 与 Auto Layout 两个专业 Agent 的中间契约、确定性处理边界、Harness 诊断与模型调用稳定性要求。

## Requirements

### Requirement: 专业 Agent 单一职责边界
系统 SHALL 将 UI Design 和 Auto Layout 限制在声明的专业职责内。UI Design SHALL 只生成通过严格 Schema 的初始 UI JSON；Auto Layout Agent SHALL 在自身内部确定性编译 InitialUIDocument、生成并应用 Flex 布局计划，并对外返回最终 DesignDocument；Root Supervisor SHALL 只负责任务依赖、状态推进和有限重试，不得代替专业阶段补写字段或新增 Specification、Compiler、Layout Engine、Final Gate 阶段。

#### Scenario: UI Design 不生成最终文档字段
- **WHEN** UI Design Agent 根据 StandardizedPRD 生成页面设计
- **THEN** 输出只包含初始 UI JSON Schema 允许的图层结构、内容、组件、基础样式和布局字段，不包含 designSystem、computedLayout 或框架代码

#### Scenario: Auto Layout 不改变业务语义
- **WHEN** Auto Layout Agent 为已校验的 DesignDocument 规划布局
- **THEN** Agent 内部计划只引用已有 nodeId，且最终输出不包含节点创建、删除、移动、内容、组件、props、视觉 style 或不可推导坐标修改

### Requirement: 严格的初始 UI JSON 契约
系统 SHALL 提供版本化 `initial-ui-document.schema.json`，并将其作为 UI Design 模型结构化输出和阶段交接的唯一契约。Schema MUST 禁止未知字段，要求顶层身份、名称、资产集合和根节点，并递归要求稳定节点 ID、kind、name、tag、style、props、layout、layoutItem 和 children；component、text、image 节点 MUST 分别满足组件引用、文本内容和资产引用条件，同时禁止 designSystem、computedLayout 和框架代码字段。

默认 DesignGenerationContract SHALL 注册 Ant Design Components Overview 的 72 项基础能力。UI Design 只能使用该注册目录中的稳定 `ui.*` tag；其中命令式或组合式能力 SHALL 在画布渲染器中使用确定性的静态预览投影，不得在渲染阶段触发消息、通知或其他副作用。

#### Scenario: 合法设计意图进入 Auto Layout
- **WHEN** 模型返回符合 initial-ui-document Schema、ID 唯一且所有组件、Token 与资产引用合法的初始 UI JSON
- **THEN** 系统将初始 UI JSON 以 `initial_ui_document` 写入 Root State 并允许 Auto Layout 执行

#### Scenario: 任意对象被拒绝
- **WHEN** 模型返回缺少版本或根节点、包含未知字段、重复 ID、非法 componentId 或叶子节点 children 的对象
- **THEN** UI Design 门禁返回路径明确的结构化错误且不把该对象写入 Root State

#### Scenario: 使用 Ant Design 基础能力
- **WHEN** UI Design 输出引用默认目录中的任一 Ant Design 基础组件 tag
- **THEN** GenerationContract 接受该 tag，最终 v2 画布渲染器使用对应组件或声明的静态预览投影渲染

### Requirement: Auto Layout 内部确定性编译
Auto Layout Agent 内部 SHALL 使用纯函数把合法初始 UI JSON 与固定 DesignGenerationContract 编译为 DesignDocument v2。编译器 MUST 固定注入版本和 Profile 引用，从 contract 构建设计系统快照，保留稳定 ID，映射 kind/tag、style、layout 和 layoutItem，并补齐 DesignDocument 必需字段；编译器不得新增业务需求、发明组件或 Token、调用模型猜测可确定字段或静默删除业务节点。编译结果只在 Auto Layout 内部流转。

#### Scenario: 草稿确定性编译成功
- **WHEN** 初始 UI JSON 的所有字段都能由固定 GenerationContract 唯一映射
- **THEN** 相同输入重复编译产生等价 DesignDocument，并通过 Schema、Profile、引用、唯一 ID 和 GenerationContract 校验

#### Scenario: Contract 缺少能力
- **WHEN** 草稿引用 contract 未提供且不存在合法唯一替代的组件或 Token
- **THEN** 编译器返回精确路径的能力错误，不发明定义、不降级 Profile 且不输出可进入 Auto Layout 的通过报告

### Requirement: 禁止模型重写 DesignDocument
Auto Layout Agent SHALL 复用现有 DesignDocument v2 Schema，并在确定性编译后执行完整校验。编译或最终校验失败时 MUST 返回稳定错误，不得调用模型重写完整 DesignDocument。现有 UIValidationReport 只能作为 deprecated 成功兼容投影，对外主结果 SHALL 是完整 DesignDocument。

#### Scenario: 编译结果无效
- **WHEN** 编译后的 DesignDocument 包含非法引用或不满足固定 GenerationContract
- **THEN** Auto Layout Agent 直接失败，不让模型重写文档且不生成 LayoutPlan

#### Scenario: 布局模型不得修改文档
- **WHEN** LayoutPlan 尝试修改 children、节点 ID、用户确认文案、组件、Profile 或视觉样式
- **THEN** LayoutPlan Schema 或 Auto Layout 门禁拒绝计划，内部编译文档保持不变

### Requirement: 可操作的完整校验报告
Auto Layout Agent 的内部 `ValidationResult` SHALL 收集一次校验中的全部 Schema 和语义问题。每个问题 MUST 包含稳定 code、severity、精确 JSON Pointer path、message、repairable 和 status，并在适用时包含 keyword、expected 与脱敏截断的 actual 摘要。deprecated UIValidationReport 仅由兼容适配器生成，不得成为新的校验字段承载方；内部结果的 passed、计数与实际问题状态 MUST 一致，不得只以根路径通用错误替代可定位错误。

#### Scenario: 同时报告多个错误
- **WHEN** 候选文档同时存在非法组件、重复 ID 和无效布局尺寸
- **THEN** 校验报告分别包含三个问题的准确路径、错误码和修复状态

#### Scenario: 修复后出现新错误
- **WHEN** 应用修复 patch 后原问题消失但完整复验发现新的契约问题
- **THEN** 最终报告保持 failed 并包含新问题，系统不得把原问题标记 fixed 后直接放行

### Requirement: 严格的 LayoutPlan 契约
系统 SHALL 提供版本化 `LayoutPlan` JSON Schema，并将其作为 Auto Layout Agent 内部规划值的唯一契约。每个 operation MUST 引用非空 nodeId，并至少提供 layout、layoutItem 或 responsive 之一；其结构和枚举 MUST 与 DesignDocument 的布局定义一致。Schema MUST 禁止未知字段、内容字段、结构字段、视觉 style、props 和 computedLayout；LayoutPlan 不作为 Root State 或公开 Agent 输出。

#### Scenario: 合法布局计划被应用
- **WHEN** LayoutPlan 只引用现有节点且所有 mode、sizing、断点和非负数值均被 GenerationContract 允许
- **THEN** Auto Layout Agent 在内部接受计划并交给自己的确定性布局模块

#### Scenario: 未知节点计划被拒绝
- **WHEN** LayoutPlan operation 引用输入 DesignDocument 中不存在的 nodeId
- **THEN** 系统返回定位到该 operation nodeId 的错误，不创建猜测节点且不修改文档

### Requirement: 确定性布局应用与渲染投影
Auto Layout Agent 内部的纯函数布局模块 SHALL 将已校验的 LayoutPlan 应用为 DesignDocument 的 layout、layoutItem 和 responsive 字段，并同步生成当前 v2 画布渲染器可消费的合法基础 style 投影。布局模块 MUST 保留节点集合、层级、ID、内容、组件、非布局视觉样式和 Profile；只有在 viewport 与所有测量输入足以确定几何结果时才能写入 computedLayout。Agent 对外 SHALL 只返回应用后的完整 DesignDocument。

#### Scenario: Flex 计划形成可渲染样式
- **WHEN** 计划为容器指定 column、gap、padding 和 fill 尺寸策略
- **THEN** 最终文档同时包含合法布局元数据及对应 display、flexDirection、间距和尺寸样式，并能派生 v2 render model

#### Scenario: 无法确定几何测量
- **WHEN** 节点尺寸依赖当前输入未提供的字体、图片或组件固有测量
- **THEN** 布局引擎省略该节点 computedLayout，不生成猜测坐标，但仍产出通过基础 viewport 渲染门禁的声明式布局

### Requirement: 阶段产物门禁与不可绕过顺序
两个 Agent SHALL 各自完成其输出的 JSON Schema、GenerationContract、引用完整性和渲染可用性校验。Auto Layout 只有在内部编译文档与最终 DesignDocument 均通过完整校验后才能产生 result。系统不得新增 Specification 或独立 Final Gate Agent/任务。

#### Scenario: 内部编译文档无效
- **WHEN** Auto Layout 内部编译的 DesignDocument 未通过完整复验
- **THEN** Auto Layout 不调用布局模型且 Root 不产生成功 result

#### Scenario: Auto Layout 返回不可渲染文档
- **WHEN** Auto Layout Agent 应用布局后最终 DesignDocument 无法派生 v2 render model
- **THEN** Auto Layout Agent 返回失败且 Root 不发送成功 result

### Requirement: 非 Agent 的执行 Harness 与有限 Loop
系统 SHALL 为两个专业 Agent 提供共用的执行 Harness。Harness MUST 是普通调用与校验基础设施，不得注册为第三个 Agent 或新增流水线阶段。Harness SHALL 使用有界 Loop 调用同一个 Agent、校验候选、丢弃失败候选，并仅向下一次尝试传递有长度上限的错误码、JSON Pointer 路径和简短原因。

Harness MUST NOT 修改 UI Design 节点结构、重写 Auto Layout 内部 DesignDocument、修改 LayoutPlan 或生成坐标；MUST NOT 将完整异常、完整校验报告、无效候选、Schema 或输入文档副本作为重试反馈再次发送给模型。

#### Scenario: Schema 失败后短摘要重试
- **WHEN** 专业 Agent 的第一次候选未通过 Schema 或语义校验
- **THEN** Harness 丢弃候选，并使用短错误摘要重新调用同一个 Agent；原始业务输入保持不变

#### Scenario: Harness 不越过专业边界
- **WHEN** UI Design 节点结构、Auto Layout 内部编译文档或布局计划无效
- **THEN** Harness 不修改该产物且不调用其他 Agent 代修；有限重试耗尽后返回稳定失败

### Requirement: UI Design 可观测诊断
UI Design Harness SHALL 为每次尝试生成服务端结构化诊断 Trace，至少包含 stage、attempt、status、failure phase、耗时、输出字节数、问题数量、模型标识，以及 prompt、Schema 和 GenerationContract 指纹。Schema 失败 SHALL 一次收集多个带 JSON Pointer、keyword、expected 和脱敏 actual 摘要的问题；完整问题不得进入模型重试、Root State 或公开 HTTP/SSE 响应。

失败候选快照 MUST 递归移除敏感字段并限制长度，且只能在 DEBUG 日志级别记录。诊断事件 MUST 可按 status、attempt、failure phase 和首个问题路径聚合，并提供纯函数供脱敏候选离线回放相同 Schema 校验。

#### Scenario: UI Design Schema 多错误诊断
- **WHEN** UI Design 候选同时缺少必需字段并包含未知字段
- **THEN** 内部 Trace 保存多个精确问题和契约指纹，模型下一次尝试只收到短错误摘要

#### Scenario: 生产日志不泄露候选
- **WHEN** 服务端未启用 DEBUG 日志且 UI Design 候选校验失败
- **THEN** 诊断事件记录失败分类和指标字段，但不记录 PRD、GenerationContract、完整候选或敏感字段

### Requirement: 模型调用截止时间与失败分类
系统 SHALL 为每次 thinking 或 fallback 模型子调用执行不可被流活动延长的绝对截止时间，并为完整 Agent 图执行总截止时间。模型边界 MUST 区分超时、限流、认证、HTTP 服务错误、非法流、空响应与非法 JSON；是否进入 fallback MUST NOT 决定错误是否可重试。模型调用 Trace 只能包含阶段、状态、耗时、响应大小、流事件数、稳定错误码、模型标识和可选 HTTP 状态，不得包含请求或响应正文及认证信息。

#### Scenario: reasoning 持续输出仍达到绝对时限
- **WHEN** 模型在整个请求时限内持续发送 reasoning 或 content 但未完成结构化响应
- **THEN** 当前子调用在绝对截止时间结束并返回可重试的 `model_request_timeout`，不得因 activity 持续运行到上游网关时限

#### Scenario: fallback 失败仍保留原因语义
- **WHEN** thinking 返回空响应或非法 JSON 后 fallback 遭遇临时读取超时
- **THEN** 系统记录 `fallback` 阶段和读取超时错误，Harness 可在有界次数内重试；不得统一折叠为不可重试的 `model_unavailable`

#### Scenario: Agent 总时限不被活动刷新
- **WHEN** Agent 持续产生 reasoning/activity 事件但完整运行超过 `AgentConfig.total_timeout`
- **THEN** Root 取消图执行并返回稳定 `agent_timeout`，且不产生成功结果
