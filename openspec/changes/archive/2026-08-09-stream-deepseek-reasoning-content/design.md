## Context

Agent 模型当前通过 `ChatOpenAI.ainvoke` 等待完整响应，Root 与各专业 Agent 只能在调用前后发出状态事件。DeepSeek thinking 会在最终 `content` 前通过 Chat Completions 流的 `delta.reasoning_content` 返回推理文本，但当前安装的 `langchain-openai` 消息块转换不会保留该提供方扩展字段，因此仅把 `ainvoke` 替换为 `astream` 无法可靠取得 reasoning。

现有 generation 已具有前台 SSE、Agent 事件队列、任务/阶段/尝试身份、客户端取消传播和 lifespan 管理的共享 HTTPX client。变更应复用这些边界，并保持最终结构化输出与 DesignDocument 契约不变。

## Goals / Non-Goals

**Goals:**

- 实时、逐增量转发 DeepSeek 实际返回的 `reasoning_content`，不以固定文案或服务端摘要替代。
- 将 reasoning 精确关联到 Root 或专业 Agent 的阶段、任务和尝试次数。
- 保持最终 `content` 的 JSON 累积、解析、Schema 校验、重试、超时与取消语义。
- 在工作台中提供可访问、可折叠且与消息历史分离的临时 reasoning 展示。
- 对 reasoning 的传输和内存占用设置既有输出上限，并禁止日志与持久化。

**Non-Goals:**

- 不把 reasoning 当作助手最终答复、DesignDocument 或可恢复的项目历史。
- 不为不支持 `reasoning_content` 的模型伪造思考内容。
- 不新增 generation 路由、数据库字段、后台任务或运行时依赖。
- 不保证模型推理文本是系统真实执行轨迹，也不对其正确性背书。

## Decisions

### 1. 使用共享 HTTPX client 直接消费 Chat Completions SSE

Agent 模型适配器将接收 lifespan 管理的 HTTPX client，显式发送 `stream: true` 与 `thinking: {"type":"enabled"}`，逐条解析上游 `data:` 帧。`delta.reasoning_content` 立即交给 reasoning sink，`delta.content` 仅在服务端累积，流结束后沿用现有 JSON 对象校验。

选择直接解析是因为当前 `langchain-openai` 会在消息块转换时丢弃 DeepSeek 扩展字段；继续依赖其 `astream` 会让实现依赖未声明的兼容行为。复用现有 HTTPX client 可保持连接生命周期、取消和依赖边界一致，也无需直接新增 OpenAI SDK 依赖。

### 2. 通过显式调用级 reasoning sink 传递增量

模型端口的结构化调用与任务选择调用将接受可选异步 reasoning sink。Supervisor 为每次 Root 选择和每个子 Agent 尝试创建带 `stage`、`taskId`、`attempt` 的 sink，并显式传入下层 Agent 图。

选择调用级回调而不是修改全局模型实例或使用模块级状态，是为了让同一进程内并发 generation 相互隔离，并让取消自然沿 await 链传播。各测试替身也能直接注入 reasoning 增量验证事件顺序。

### 3. 复用 Agent `progress` 事件承载原始增量

每个上游 reasoning chunk 映射为现有 `agent` SSE 中的 AgentRunEvent：`event=progress`，payload 为 `{"status":"reasoning","delta":"<原始增量>"}`。事件沿用 generation、run、task、stage 和 attempt 身份，不新增顶层 SSE 类型或 Agent event enum。

服务端 MUST 保持 chunk 文本原样，不生成、改写或总结 reasoning。空增量不发送；达到既有 Agent 输出字节上限后停止转发后续 reasoning，并发送一次 `status=reasoning_truncated` 进度事件，但最终 `content` 仍继续消费和校验。

### 4. 前端按任务与尝试聚合，不创建聊天消息

Web 使用 `runId + taskId + attempt` 作为 reasoning 条目身份，按事件顺序追加 `delta`。共享 Workspace 接收结构化 reasoning 列表，在生成区域按阶段展示可折叠内容；当前正在输出的条目展开，阶段完成后折叠，用户仍可重新展开。

reasoning 状态只存在于当前页面的 generation 生命周期。completed 后可以保留到页面离开或下一次 generation 开始；failed、interrupted、主动停止和组件卸载时清理，不从项目历史恢复，也不插入 `messages`。

### 5. 安全边界以传输范围和数据最小化为主

reasoning 仅随已认证项目 generation 的前台 SSE 返回给项目所有者，不写数据库、不写日志、不进入错误 payload。上游请求不得包含 API Key、Authorization、数据库信息或其他服务端凭据；因此 reasoning 即使复述输入，也不应获得这些敏感值。

真实 reasoning 可能复述用户需求、系统提示或 Schema，这是选择原样展示的固有取舍。UI 将明确标注其为“模型思考过程”，不把它描述为系统审计日志或事实来源。

## Risks / Trade-offs

- [真实 reasoning 可能暴露提示结构或复述用户输入] → 仅返回给项目所有者，不持久化或记录，并确保上游输入不含服务端秘密。
- [高频小 chunk 导致大量 React 更新和 SSE 开销] → Web 在动画帧或短批次内合并增量，但不得改写文本或改变顺序。
- [reasoning 很长导致内存增长] → 服务端按既有 Agent 输出上限截断展示流并发出一次截断状态，最终结构化输出继续处理。
- [上游返回畸形 SSE、只有 content 或没有 reasoning] → 保持现有失败映射；没有 reasoning 时 UI 不创建伪造条目，最终 content 仍可正常完成。
- [直接 HTTPX 解析扩大模型适配层职责] → 将上游帧解析保持为模型模块内部的纯解析函数，并用单元测试覆盖 reasoning、content、终止帧和畸形帧。

## Migration Plan

1. 先扩展模型端口与 HTTPX 流解析，并以单元测试锁定 reasoning/content 分流行为。
2. 接入 Supervisor reasoning sink 与 Agent progress 事件，使用集成测试验证身份、顺序、上限和取消。
3. 扩展 Web generation 状态与 Workspace Props，使用单元测试和组件测试验证聚合、折叠和清理。
4. 保持现有最终结果路径并运行 Server 与 Web 的相关检查。若需回滚，可恢复非流式模型适配器并移除 reasoning UI；无数据迁移或持久化兼容问题。

## Open Questions

无。默认展示 DeepSeek 返回的全部有界 reasoning，并明确标注为模型输出。
