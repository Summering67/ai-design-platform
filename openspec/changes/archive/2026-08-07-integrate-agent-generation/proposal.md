## Why

当前项目 generation 只转发聊天模型的文本，已实现的多 Agent 运行器既不会由用户输入触发，也不会将设计文档和阶段输出交付给画布。用户无法了解 Root 的调度与各专业 Agent 的已验证返回结果，也无法看到最终设计。

## What Changes

- 项目级 generation 改由 Root Agent 执行，使用当前用户消息作为需求输入并在前台 SSE 请求内完成。
- 服务端为项目 generation 提供默认 DesignGenerationContract，并将 Agent 运行事件按 SSE 原样交付；阶段完成事件包含该阶段已验证的结构化输出。
- 最终 `DesignDocument 2.0.0` 作为唯一成功终态的一部分返回前端，并在项目中持久化以便刷新后恢复。
- Web 消费 Agent 事件，展示运行阶段及各阶段返回的 JSON，同时将最终设计文档渲染到画布。
- 不再把项目 generation 的上游输出当作助手聊天文本流；助手消息改为成功生成的简短完成说明。

## Capabilities

### New Capabilities

- `agent-backed-project-generation`: Root Agent 驱动的项目生成、阶段结果 SSE 与最终设计文档持久化。
- `agent-run-observability`: 面向工作台的 Agent 阶段事件和已验证模型输出展示。
- `design-document-canvas-delivery`: 将最终规范设计文档交付并渲染到项目画布。

### Modified Capabilities

- `project-conversations`: 项目读取与 generation 成功结果增加规范设计文档，并以 Agent 运行替换聊天文本上游。
- `ai-chat`: 项目级 SSE generation 的事件和前端编排改为 Agent 运行语义。

## Impact

- 后端：`project` 路由/服务/数据库、Agent runner 与生命周期依赖、DTO 和测试。
- 前端：工作台 SSE 状态、设计文档读取与画布渲染；共享 UI 的画布 Props。
- 数据库：项目新增最终规范设计文档字段，不新增第三方依赖。
