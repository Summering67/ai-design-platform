## Context

项目 generation 当前调用 Chat Completions 并把文本增量作为 assistant 消息。Agent Runtime 已有 Root、子图和版本化运行事件，但没有 HTTP 调用方。工作台已有 v2 `DesignDocumentRenderer`，画布仍使用占位节点。

## Goals / Non-Goals

**Goals:**

- 让用户消息在同一前台 SSE 请求内启动 Root Agent。
- 将阶段、已验证输出和终态以 Agent 事件交付前端，最终文档渲染到画布。
- 保持现有项目、生成尝试、停止和重新生成的归属与取消语义。

**Non-Goals:**

- 不持久化 Agent 中间输出、提示词或推理过程。
- 不增加长期记忆、后台队列、数据库字段或新的公开路由。
- 不在刷新后恢复未重新生成的画布文档。

## Decisions

- 在现有项目 generation SSE 中增加 `agent` 事件，其 data 为版本化 `AgentRunEvent`；保留 `generation` 与现有唯一终态。这样不增加第二套取消和授权边界。替代方案是独立 Agent API，但会重复项目并发和取消处理。
- Root 运行使用服务端内置的默认 GenerationContract；客户端不提交 Profile 或契约，避免浏览器改变受信任设计约束。
- Root 在每个专业任务完成后将已通过校验的结构化输出放入 `progress.payload.output`。这回答“AI 返回了什么”，但不发送 system prompt、原始模型消息或异常详情。
- 最终 `result.payload.document` 通过 `completed.document` 转发到前端；前端仅将其保留在当前工作台状态并传给共享 `Workspace` 的 v2 渲染器。
- 成功时仍创建一条简短助手消息用于保持现有项目轮次与重试契约；其内容不复制或伪装为 Agent 的结构化结果。

## Risks / Trade-offs

- [刷新后画布清空] → 最终文档只在本次 SSE 中交付；文档持久化单独变更。
- [阶段输出体积较大] → Agent Runtime 已执行输出字节上限；前端只显示可折叠 JSON。
- [模型只生成结构化结果] → UI 通过阶段名称和结果面板提供可见进度，而非模拟聊天增量。
