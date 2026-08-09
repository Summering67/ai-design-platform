# agent-run-observability Specification

## Purpose

定义项目 generation 中可安全呈现的 Agent 运行状态与输出。

## Requirements

### Requirement: 可见的 Agent 输出
系统 SHALL 将 Agent 运行事件作为 SSE `agent` 事件发送给项目所有者。用于调度、追问和设计文档生成的结构化模型调用 MUST 开启 thinking，将非空 `reasoning_content` 作为进度事件发送，并单独消费最终 `content` 执行 JSON Schema 校验。若首次流只有 reasoning 而没有合法 content，系统 SHALL 关闭 thinking 重试一次以取得正式结构化输出。每个专业阶段完成事件 SHALL 包含已验证结构化输出；reasoning 事件 MUST NOT 写入消息历史、数据库或日志，且事件 MUST NOT 包含提示词、原始模型消息、堆栈、内部路径或凭证。

#### Scenario: 结构化调用传输 reasoning

- **WHEN** Root 或专业 Agent 调用兼容 Chat Completions 的模型
- **THEN** 请求开启 thinking，系统流式发送真实 reasoning 增量，并只将最终 content 用作结构化结果

#### Scenario: 只有 reasoning 时恢复正式输出

- **WHEN** 开启 thinking 的结构化调用结束后没有返回合法 content
- **THEN** 系统关闭 thinking 重试一次，且不将 reasoning 文本当作正式结果

#### Scenario: 查看阶段返回

- **WHEN** 专业 Agent 完成已验证输出
- **THEN** 前端收到包含阶段、任务身份、尝试次数和 output 的 agent 事件

#### Scenario: Root 完成一次任务选择

- **WHEN** Root 成功取得并校验本轮待执行任务
- **THEN** 系统发送 `reasoning_completed` 进度状态，使本轮已缓冲 reasoning 可安全展示

### Requirement: 结构化用户输入请求

Root Supervisor 及所有可调用模型的 Agent SHALL 只能通过结构化 `input_required` 事件请求用户输入。reasoning 文本中的问句 MUST NOT 被解释为用户输入请求。请求 SHALL 包含来源阶段、任务标识、轮次和非空且唯一的问题 ID；每个通用问题 SHALL 提供短标题、完整问题及 2–3 个互斥的标签/说明选项，并可显式允许“其他”回答。发送后当前 generation MUST 停止调度后续 Agent，直到回答被提交。

#### Scenario: Agent 请求用户输入

- **WHEN** 任一 Agent 无法安全推断会影响当前产物的必要信息
- **THEN** 系统持久化 pending input request、将 generation 标记为 `awaiting_input`，并向项目所有者发送结构化 `input_required` 事件

#### Scenario: reasoning 含有疑问句

- **WHEN** reasoning 内容包含模型自问自答或疑问句
- **THEN** 系统不暂停 generation，也不创建 input request；只有合法 `input_required` 才能请求用户回答

#### Scenario: 上游没有 reasoning

- **WHEN** 上游只返回最终 `content` 而未返回非空 `reasoning_content`
- **THEN** 系统不生成或发送伪造的 reasoning 内容，并继续处理最终结构化输出

#### Scenario: reasoning 达到输出上限

- **WHEN** 单个任务尝试已转发的 reasoning 达到 Agent 输出字节上限
- **THEN** 系统停止转发该尝试的后续 reasoning、发送一次截断进度状态，并继续消费和校验最终 `content`

#### Scenario: generation 被取消

- **WHEN** 项目所有者停止 generation 或 SSE 客户端断开
- **THEN** 系统停止发送 reasoning、取消上游模型流并按既有契约终结 generation
