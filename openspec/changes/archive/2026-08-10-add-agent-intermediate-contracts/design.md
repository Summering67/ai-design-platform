## Context

当前运行链路为 `StandardizedPRD → initial_document → corrected_document → final_document`。UI Design 的结构化输出 Schema 只声明 object；Specification 先用最终 DesignDocument 校验任意初始化对象，失败时只得到根路径错误，再让模型整份重写；Auto Layout 的 Schema 只约束松散 operations 数组，确定性应用函数实际修改 `style` 和 `props.data-sizing`，与 DesignDocument 已定义的 `layout`、`layoutItem`、`responsive`、`computedLayout` 不一致。

最终画布通过 `deriveV2RenderModel` 校验 DesignDocument，并由 `DesignDocumentRenderer` 递归渲染 `tag`、`props`、`style` 和 children。当前渲染器不读取 `computedLayout`，因此最终文档仅有布局元数据或坐标并不足以形成可见布局；布局应用必须产生渲染器当前可消费的样式投影。

本变更涉及共享 JSON 契约、Python Agent 状态交接、两个 Agent 及 Auto Layout 内部的确定性编译/布局代码。所有跨 Agent 交接值必须是版本化、可序列化且可独立校验的 JSON；内部辅助值不作为独立阶段交接。

## Goals / Non-Goals

**Goals:**

- 为 UI Design、Auto Layout 建立单一职责、明确输入输出和禁止越界事项。
- 让每次模型调用都使用与 prompt 完全一致的严格 JSON Schema。
- 用确定性代码完成可确定的字段注入、节点映射、契约快照、布局应用和完整复验。
- 让错误能定位到 JSON Pointer，并限制模型只修改被授权的字段和节点。
- 保证 Auto Layout Agent 返回的最终 DesignDocument 同时满足 Schema、GenerationContract、引用完整性、稳定 ID 和当前画布渲染契约。

**Non-Goals:**

- 不修改 Requirement Agent、PRD Schema、公开 HTTP API 或 SSE 事件格式。
- 不让模型生成 React、HTML、CSS 文本、目标框架代码或 `computedLayout` 坐标。
- 不在本变更中实现浏览器排版引擎、文本测量、Grid、约束求解器或视觉回归系统。
- 不允许 Auto Layout 创建布局容器、移动、删除或重命名节点；结构调整必须回到 UI Design 阶段产生新的初始 UI JSON。
- 不以放宽 DesignDocument Schema、GenerationContract 或渲染器校验换取通过。

## Decisions

### 1. 以两个 Agent 窄接口替代 Specification 阶段和独立 Final Gate

阶段职责固定如下：

| Agent | 唯一职责 | 输入 | 输出 | 内部实现 | 禁止事项 |
| --- | --- | --- | --- | --- |
| UI Design Agent | 把 PRD 转换为包含图层结构、内容、组件、基础样式和布局规则的初始 UI JSON | StandardizedPRD、固定 GenerationContract、已解决用户输入 | `InitialUIDocument` | 自身完成初始 UI JSON Schema、引用和覆盖校验 | 不生成最终 designSystem 快照、框架代码或 computedLayout |
| Auto Layout Agent | 编译初始 UI JSON，并为已有节点规划、应用 Flex 布局，返回可渲染最终文档 | `InitialUIDocument`、PRD 响应式要求、固定 GenerationContract | 最终 `DesignDocument` 和布局摘要 | 内部确定性编译、生成/校验 `LayoutPlan`、应用布局并完成渲染契约校验 | 不修改节点语义、层级、组件或生成不可推导坐标 |

Root Supervisor 仍只负责任务依赖、状态推进和有限重试。它不补写任何中间产物字段，也不新增 Final Gate 任务。

两个 Agent 复用同一个执行 Harness。Harness 是普通基础设施函数，不是 Agent，也不是流水线阶段。它执行 `调用模型 → 校验候选 → 成功返回 / 生成短错误摘要后重试` 的有界 Loop。Harness 不保存或修改无效候选，不调用下游 Agent 修复，不把校验器的完整响应、Schema、输入文档或堆栈再次塞回模型。

选择该方案是因为完整 DesignDocument 同时包含业务结构、设计系统快照、渲染样式和布局结果，模型不应一次性生成全部字段。UI Design 只负责设计结构，Auto Layout 内部用确定性代码完成编译和布局，再由 Harness 做有限重试。

### 2. 新增两个版本化中间 Schema

在 `packages/design-contract/schema/v2/` 新增：

- `initial-ui-document.schema.json`：顶层要求 `version: "1.0.0"`、`id`、`name`、`assets`、`root`。递归节点要求稳定 `id`、`kind`、`name`、`tag`、`style`、`props`、`layout`、`layoutItem`、`children`；text、image、component 节点分别满足文本、资产和组件条件。Schema 允许表达基础样式与声明式布局规则，但禁止 `designSystem`、`computedLayout`、运行时字段和框架代码。所有对象使用 `additionalProperties: false`，组件、Token 和资产引用再由固定 GenerationContract 做语义校验。
- `layout-plan.schema.json`：顶层要求 `version: "1.0.0"`、`viewport`、`operations`。每个 operation 要求 `nodeId`，并至少包含 `layout`、`layoutItem`、`responsive` 之一；布局结构通过本 Schema 内部 `$defs` 与 DesignDocument 的 `flexLayout`、`flexItem`、`responsiveLayout` 保持同源。禁止 `style`、`props`、`children`、内容和 `computedLayout` 字段。

Auto Layout 的内部编译结果和最终结果复用现有 `design-document.schema.json`。`ui-validation-report.schema.json` 仅作为现有 API/SSE 消费方的 deprecated 兼容投影；共享包同步导出两个新增 Schema 的 TypeScript 类型和 fixtures。Python 运行时通过现有 `load_schema` 读取同一源文件。

选择让 LayoutPlan 复用布局定义而不是沿用扁平 operations，是为了消除 `gap` 被错误映射成 `columnGap`、sizing 被写入 props 等语义漂移；不新增 patch Schema。

### 3. UI Design 输出先做 Schema 与语义门禁

UI Design prompt 明确初始 UI JSON 职责，结构化调用直接传入 `initial-ui-document.schema.json`。模型返回后依次校验：

1. JSON Schema；
2. 全树稳定且唯一 ID、深度与节点数限制；
3. 组件、Token 和资产引用均存在；
4. kind 条件和叶子节点约束；
5. PRD 页面与关键内容覆盖。

失败结果不写入 Root State。可重试的结构错误由 Harness 携带有界错误摘要重试一次，不交给 Auto Layout 猜测任意输入结构。现有无约束 `initial_document` 输出路径废弃。

### 4. Auto Layout 内部采用“确定性编译—规划—布局应用—全量复验”

Auto Layout Agent 内部使用纯函数 `compile_initial_ui_document(document, contract) -> DesignDocument`。编译器负责：

- 固定写入 DesignDocument v2 版本和 contract Profile 的 id/version/digest；
- 从 contract 构建设计系统 Token 与组件快照，绝不由模型发明；
- 将 role 映射为 kind，将 componentId 映射为 tag，并补齐合法的 style、props、children 和 assets；
- 将视觉与布局意图映射为契约允许的 DesignDocument 字段；
- 保留 draft ID，拒绝重复 ID 和未知引用；
- 丢弃不存在的字段不是修复手段，因为 draft 已由 Schema 禁止未知字段。

确定性校验收集全部问题，而不是只取第一个异常。内部 `ValidationResult` 必须保留稳定 code、severity、精确 JSON Pointer path、message、repairable、status，以及可选 keyword、expected、脱敏截断的 actual。旧 `UIValidationReport` 只由兼容适配器投影，不承载新的校验语义；编译器只为确实存在多个合法语义候选的错误标记 repairable，并附带允许字段及候选值。

编译结果只在 Auto Layout 内部流转，不写入 Root State。编译失败直接返回精确错误；不得让模型重写 DesignDocument。现有 UIValidationReport 只作为公开 result 的 deprecated 成功兼容投影。

不保留模型输出完整 DesignDocument 的修复路径，因为模型可能改变稳定 ID、Profile 或其他无关字段。

### 5. Auto Layout Agent 内部规划并应用布局

Auto Layout prompt 只允许根据已有节点和 PRD 响应式要求规划 `LayoutPlan`。该计划只在 Agent 内部流转，Agent 对外返回最终 DesignDocument。计划门禁检查：

Flex 引擎对标 Figma Auto Layout 的水平/垂直流、Wrap、Padding、Gap、Alignment、嵌套容器，以及 Fixed、Hug contents、Fill container 等尺寸语义。所谓图层层级管理仅指沿既有父子树递归计算布局；Auto Layout 不得创建、删除、重排或重新挂载图层。Grid 暂不属于本变更范围。参考：https://help.figma.com/hc/en-us/articles/360040451373-Guide-to-auto-layout

- operation 的 nodeId 唯一且存在；
- 所有 mode、sizing、响应式断点和数值满足 GenerationContract；
- 不允许负尺寸、互斥约束、未知断点或叶子容器布局；
- 未出现任何内容、结构、组件、视觉或坐标字段。

Auto Layout Agent 内部的纯函数布局模块把计划写入节点的 `layout`、`layoutItem` 和 `responsive`，并把当前渲染器需要的基础布局转换为合法 `style`：例如 flex mode 映射为 display、direction 映射为 flexDirection、wrap 映射为 flexWrap、gap/padding/尺寸策略映射为相应 CSSProperties 兼容字段。布局样式只覆盖布局 Agent 拥有的字段，其余视觉 style 保持不变。

`computedLayout` 只有在输入包含明确 viewport、固定/可推导尺寸且无需字体或浏览器测量时才能由确定性算法生成；无法可靠测量时保持省略，不能填伪坐标。当前交付成功不依赖 computedLayout，而依赖最终文档能产生有效 render model 和渲染样式投影。

选择该策略是因为当前 React 渲染器直接消费 style。仅生成 computedLayout 会得到 Schema 合法但视觉无布局的文档；让模型计算坐标又不可复验且容易受内容测量影响。

### 6. Root State 使用两个 Agent 的明确产物名

`completed` 状态改为：

```text
prd
  → initial_ui_document
  → final_document
```

每个跨 Agent 值写入状态前通过产出 Agent 自己的 Schema/语义门禁。Auto Layout Agent 返回前完成 DesignDocument Schema、Profile、GenerationContract、引用/唯一 ID/层级、布局一致性和 `deriveV2RenderModel` 等价校验。任何一步失败都不发送 completed result。

内部字段更名是有意的破坏性变更，用来避免 `initial_document` 继续暗示 UI Design 已经输出最终文档。公开 result 仍包含 `prd`、`validation`、`document`，HTTP/SSE 契约不变。

### 7. Harness 只执行有限校验 Loop

UI Design 和 Auto Layout 的模型调用通过共享 Harness 执行。每次尝试都从原始、已校验输入重新生成候选，并由所属 Agent 的校验函数判定。失败候选立即丢弃，Harness 不进行字段补写、节点变换、DesignDocument 重写或坐标计算。

重试反馈使用单个短字符串，仅包含稳定错误码、可用时的 JSON Pointer 路径和截断原因；不得包含完整异常、完整校验报告、无效候选、Schema 或原始输入副本。Loop 默认最多两次模型尝试，耗尽后抛出最后一个稳定错误，由现有 Root 失败路径处理。

因此职责保持不变：UI Design 自行重新生成初始节点结构；Auto Layout 自行重新生成 LayoutPlan，Harness 永远不重写 DesignDocument 或生成坐标。

### 8. UI Design 失败使用结构化诊断 Trace

Harness 为每次模型尝试记录服务端诊断事件，包含 stage、attempt、成功/失败状态、failure phase、耗时、输出字节数、问题数量，以及 prompt、Schema、GenerationContract 和模型名称指纹。Schema 校验一次收集最多 20 个可定位问题，每个问题包含稳定 code、JSON Pointer、keyword、expected 和脱敏截断的 actual；这些完整问题只写入内部日志，不进入 Root State、HTTP/SSE 或模型重试输入。

失败候选仅在 DEBUG 日志级别输出受控快照。快照递归移除 password、token、authorization、cookie、api_key、dsn、body 等敏感字段，并设置长度上限。生产环境保持 INFO 时不会记录候选内容。INFO/WARNING 诊断事件保留可聚合的成功状态、attempt 和 failure phase，可用于计算首次通过率、重试成功率、失败路径频率和重试耗尽率。

诊断函数是纯函数，可对保存的脱敏候选和相同 Schema 离线重放；Harness 仍只把不超过 240 字符的短错误摘要交给下一次模型尝试。

### 9. 模型子调用和 Agent 运行使用绝对截止时间

模型适配器把一次结构化生成分为 `thinking` 与可选 `fallback` 子调用。每个子调用除 HTTP 连接/读取超时外，MUST 使用 `AIConfig.request_timeout` 作为整个子调用的绝对截止时间；持续 reasoning 或 content 活动不得延长该截止时间。只有 thinking 返回空内容或非法 JSON 时才进入关闭 thinking 的 fallback，网络、HTTP 与协议错误直接以稳定错误返回 Harness。

模型边界区分请求绝对超时、连接超时、读取超时、限流、认证失败、其他 HTTP 错误、非法流、空响应和非法 JSON。临时网络错误、限流、服务端错误、空响应和非法 JSON保持可重试；认证失败和其他确定性客户端 HTTP 错误不可重试。是否已经使用 fallback 不得改变错误本身的 retryable 语义。每个子调用只记录 phase、状态、耗时、响应字节、流事件数量、稳定错误码、retryable、模型标识和可选 HTTP 状态，不记录正文或认证信息。

Root Runner MUST 使用 `AgentConfig.total_timeout` 包住完整图执行；reasoning/activity 只能避免 node inactivity timeout，不能突破总时限。Harness 完成自身有界尝试后不得再由 Supervisor 对同一专业 Agent 产物进行一轮重复模型重试，避免 thinking/fallback、Harness 和 Root 重试相乘。

## Risks / Trade-offs

- [风险] GenerationContract 当前主要提供 Token ID 而非完整可渲染 Token 值，确定性编译可能只能产生有限的视觉样式 → 编译器只使用 contract 中实际存在的快照数据；缺少必要值时返回可定位的契约能力错误，不允许模型发明。实现时用现有默认 contract fixture 固化最低可渲染结果。
- [风险] 当前渲染器忽略 `layout`、`layoutItem` 和 `responsive` → 布局引擎同步生成基础 style 投影，并用 TypeScript 集成测试证明最终文档能派生 render model；更完整的响应式渲染能力作为独立后续变更。
- [风险] 收窄 draft 可能损失自由视觉表达 → Schema 保留有限的视觉意图和 Token 引用；新增表达能力必须先扩展契约，而不是塞入任意字段。
- [风险] 重试反馈过长会使模型复刻无效响应或偏离原任务 → Harness 只传递定长短摘要，且不回传候选和完整错误对象。
- [风险] 确定性编译无法覆盖模糊映射 → 返回明确失败并由 Root 结束当前运行，不让模型重写文档兜底。
- [风险] Schema 内复制布局 `$defs` 可能漂移 → 契约测试比较 LayoutPlan 与 DesignDocument 对应定义的枚举和结构；后续可在 Schema 构建流程支持跨文件引用时再去重。
- [取舍] 本阶段不保证像素级几何结果 → 优先保证结构、契约和实际画布渲染链路正确，无法确定测量的行为记录为风险而不是伪造坐标。

## Migration Plan

1. 先提交两个中间 Schema、fixtures、类型导出和契约单元测试，并将 UIValidationReport 标记 deprecated，不改变现有兼容输出。
2. 接入初始 UI JSON 输出门禁，并把确定性编译器迁入 Auto Layout Agent，切换 Root State 字段及流水线集成测试。
3. 接入 LayoutPlan Schema，以及 Auto Layout Agent 内部的确定性布局投影，删除松散 operations 兼容路径。
4. 运行 server、design-contract、design-dsl 和 UI 相关单元/集成检查。

变更在同一发布中完成内部字段切换，不保留双写。回滚时整体恢复旧 Agent 节点和状态字段；已交付的最终 DesignDocument 格式仍是 v2，无持久化中间产物需要迁移。

## Open Questions

- `computedLayout` 所需的字体、图片固有尺寸和组件测量不在当前运行输入中，因此本变更默认只在完全可推导时生成。若产品要求所有节点都必须包含 computedLayout，需要另行引入确定性测量能力和对应契约。
- 当前画布对响应式布局元数据的消费有限；本变更保证基础 viewport 的可渲染布局。完整断点切换渲染应在独立变更中明确渲染端职责。
