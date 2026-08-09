## Why

当前项目生成只在子 Agent 完成后返回结构化结果，DeepSeek thinking 期间没有可见内容，用户会把数十秒等待误判为卡死。DeepSeek 已通过流式 `reasoning_content` 提供真实模型推理文本，系统需要在不伪造进度、不持久化中间内容的前提下将其安全地实时呈现给当前项目所有者。

## What Changes

- Agent 模型适配层显式启用 DeepSeek thinking，并以流式方式分别消费 `reasoning_content` 与最终 `content`。
- 将真实 reasoning 增量关联到 generation、阶段、任务和重试次数，通过既有 SSE `agent` 通道实时发送。
- Web 工作台按子 Agent 聚合并以可折叠区域展示真实 reasoning，阶段完成后保留本次 generation 内的内容，不将其混入助手消息。
- 保持最终结构化 `content` 的完整累积、JSON 解析与 Schema 校验行为。
- 为 reasoning 流增加大小限制、取消传播和安全边界；不持久化、不写日志，也不回放已结束 generation 的 reasoning。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-run-observability`: 允许将 DeepSeek 明确返回的 `reasoning_content` 作为有界、按任务标识的实时 Agent 进度发送，同时继续禁止提示词、凭证、堆栈和其他原始上游内容。
- `ai-chat`: 工作台新增对真实 reasoning 增量的实时聚合与可访问展示，并保持其与持久化助手消息、最终设计文档分离。

## Impact

- 后端：`apps/server` 的模型端口、DeepSeek Chat Completions 流解析、Agent 事件发射、取消和输出限制。
- 前端：`apps/web` 的 SSE 事件消费、generation 临时状态，以及 `packages/ui` 工作台对话区域的 reasoning 展示。
- 契约：修改 `agent-run-observability` 与 `ai-chat` 规格；不新增公开 HTTP 路由，不修改数据库结构。
- 依赖：优先复用现有 HTTPX 与 SSE 基础设施，不预期新增运行时依赖。
