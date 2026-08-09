## Why

当前 UI Design、Specification 与 Auto Layout 链路存在职责重叠：Specification 被迫自由重写整份文档，Auto Layout 的计划又与实际可渲染字段脱节。流水线应收敛为 UI Design 与 Auto Layout 两个 Agent，并把确定性编译、Flex 布局应用和最终校验收回 Auto Layout Agent 内部。

## What Changes

- 新增严格的 `initial-ui-document.schema.json`，约束 UI Design Agent 输出包含图层结构、组件、内容、基础样式和布局规则的初始 UI JSON。
- 废弃当前仅声明为 generic object 的初始化 UI JSON 契约，不保留其宽松字段兼容路径。
- 新增严格的 `LayoutPlan` JSON Schema，约束 Auto Layout Agent 只引用现有节点并提出合法的布局、尺寸与响应式计划。
- 删除 Specification Agent 流水线阶段；Auto Layout Agent 内部以确定性编译器把 Initial UI JSON 转换为 DesignDocument，再生成并应用 LayoutPlan。
- 修改两个 Agent prompt 及其结构化输出调用，使 prompt 职责与传入的 JSON Schema 和阶段输出一致。
- 增强校验问题结构，保留可操作的 JSON Pointer 路径、关键字、期望值与实际值摘要；每次修复后执行完整 Schema、GenerationContract、引用和稳定 ID 复验。
- Auto Layout Agent 在自身内部应用 `LayoutPlan`，生成合法的 `layout`、`layoutItem`、`responsive` 和渲染器可消费的 `style`；仅在具备确定性测量输入时生成 `computedLayout`，模型不得生成几何坐标。
- 两个 Agent 各自负责自己的 Schema、GenerationContract、引用完整性和渲染可用性校验，不新增独立 Compiler、Layout Engine 或 Final Gate 阶段。
- 新增两个 Agent 共用的执行 Harness 与有限校验 Loop：Harness 只负责调用、校验、丢弃无效候选、生成短错误摘要并重试同一个 Agent，不修改任何业务产物，也不构成第三个 Agent。
- 为 UI Design Harness 增加结构化诊断 Trace、多 Schema 错误收集、prompt/Schema/GenerationContract 指纹、DEBUG 级脱敏候选快照和可离线回放的诊断函数；公开错误与模型重试仍只使用短摘要。
- 为模型 thinking/fallback 子调用增加绝对时限、稳定失败分类和脱敏 Trace，并真正执行 Agent 总时限；是否进入 fallback 不再决定错误能否重试。
- **BREAKING**：Root 链路改为 `PRD → initial_ui_document → final_document`；LayoutPlan 和编译后的中间 DesignDocument 只在 Auto Layout Agent 内部流转。

## Capabilities

### New Capabilities

- `agent-intermediate-artifacts`: 定义两个专业 Agent 的职责、输入输出边界，以及初始 UI JSON、`LayoutPlan` 两个新增版本化契约。

### Modified Capabilities

- `agent-backed-project-generation`: 将项目生成流水线改为两个 Agent，并由 Auto Layout 内部完成编译、布局应用和自身校验。
- `design-document-canvas-delivery`: 要求交付画布的最终 DesignDocument 通过与实际 v2 渲染器一致的渲染契约验证。

## Impact

- 影响 `packages/design-contract` 的 v2 Schema、类型生成与 fixtures。
- 影响 `apps/server` 的 UI Design、Auto Layout prompt、节点、状态交接，以及 Auto Layout 内部的编译/布局逻辑；移除 Specification 任务阶段。
- 影响 `apps/server` 的 Agent 执行 Harness；重试反馈只包含有长度上限的错误码、路径和简短原因，不回传完整错误响应或无效候选。
- 新增的诊断数据只写入服务端结构化日志，不改变 HTTP/SSE 契约；候选快照经过字段脱敏和长度限制，且仅在 DEBUG 日志级别输出。
- 模型调用日志只记录阶段、耗时、状态、响应字节数、流事件数、稳定错误码和 HTTP 状态，不记录响应正文、请求正文或认证信息。
- 影响 `packages/design-dsl` 的 v2 渲染模型校验复用边界，以及 `packages/ui` 画布渲染契约的集成测试。
- 需要同步更新 Agent 单元测试、流水线集成测试、契约 fixtures 和 OpenSpec 主规格；不新增外部依赖、配置或公开 HTTP API。
