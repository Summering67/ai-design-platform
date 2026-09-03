## MODIFIED Requirements

### Requirement: 可见的 Agent 输出
系统 SHALL 将 Agent 运行事件作为 SSE `agent` 事件发送给项目所有者。用于调度、追问和设计文档生成的结构化模型调用 MUST 开启 thinking，将非空 `reasoning_content` 作为带运行状态的进度事件发送，并单独消费最终 `content` 执行 JSON Schema 校验。reasoning 进度事件 SHALL 允许已认证前端在当前 generation 内临时展示原始增量，完成事件 SHALL 结束对应条目的运行态并固定其完成摘要，而不是作为首次允许展示的门禁。若首次流只有 reasoning 而没有合法 content，系统 SHALL 关闭 thinking 重试一次以取得正式结构化输出。UI Design 阶段 SHALL 产出初始化 UI JSON 对象，不要求其通过最终 DesignDocument Schema；Specification 阶段 SHALL 将该对象规范化为通过 DesignDocument Schema 与 DesignGenerationContract 校验的文档。reasoning 事件 MUST NOT 写入消息历史、数据库或日志，且事件 MUST NOT 包含提示词、原始模型消息、堆栈、内部路径或凭证。

#### Scenario: 结构化调用传输 reasoning

- **WHEN** Root 或专业 Agent 调用兼容 Chat Completions 的模型
- **THEN** 请求开启 thinking，系统流式发送带运行状态的真实 reasoning 增量，并只将最终 content 用作结构化结果

#### Scenario: reasoning 传输期间临时展示

- **WHEN** 已认证前端在当前 generation 内收到非空 reasoning 进度增量
- **THEN** 该增量具备临时展示资格，且不需要等待阶段完成事件

#### Scenario: 只有 reasoning 时恢复正式输出

- **WHEN** 开启 thinking 的结构化调用结束后没有返回合法 content
- **THEN** 系统关闭 thinking 重试一次，且不将 reasoning 文本当作正式结果

#### Scenario: 查看阶段返回

- **WHEN** 专业 Agent 完成已验证输出
- **THEN** 前端收到包含阶段、任务身份、尝试次数和 output 的 agent 事件

#### Scenario: 规范化初始化 UI JSON

- **WHEN** UI Design Agent 返回尚未通过最终文档契约的初始化 UI JSON 对象
- **THEN** 系统完成 UI Design 阶段并由 Specification Agent 将其修正为通过 DesignDocument Schema 与 DesignGenerationContract 校验的文档

#### Scenario: Root 完成一次任务选择

- **WHEN** Root 成功取得并校验本轮待执行任务
- **THEN** 系统发送 `reasoning_completed` 进度状态，使对应临时 reasoning 结束运行态并固定完成摘要
