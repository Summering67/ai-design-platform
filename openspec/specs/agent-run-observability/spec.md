# agent-run-observability Specification

## Purpose

定义项目 generation 中可安全呈现的 Agent 运行状态与输出。

## Requirements

### Requirement: 可见的 Agent 输出
系统 SHALL 将 Agent 运行事件作为 SSE `agent` 事件发送给项目所有者。系统 SHALL 将 DeepSeek 在 thinking 模式下实际返回的非空 `reasoning_content` 增量原样映射为带阶段、任务身份和尝试次数的 `progress` Agent 事件，MUST NOT 使用固定文案、模板或服务端摘要替代真实增量。每个专业阶段完成事件 SHALL 包含已验证结构化输出；reasoning 事件 MUST 与最终结构化输出分离，MUST NOT 写入消息历史、数据库或日志，且事件仍 MUST NOT 包含提示词、原始模型消息、堆栈、内部路径或凭证。

#### Scenario: 实时查看真实模型 reasoning

- **WHEN** DeepSeek 在 Root 或专业 Agent 调用期间流式返回非空 `reasoning_content`
- **THEN** 项目所有者按原始顺序收到包含对应 run、阶段、任务、尝试次数及原始 reasoning 增量的 `progress` Agent 事件

#### Scenario: 查看阶段返回

- **WHEN** 专业 Agent 完成已验证输出
- **THEN** 前端收到包含阶段、任务身份、尝试次数和 output 的 agent 事件

### Requirement: 结构化用户输入请求

Root Supervisor 及所有可调用模型的 Agent SHALL 只能通过结构化 `input_required` 事件请求用户输入。reasoning 文本中的问句 MUST NOT 被解释为用户输入请求。请求 SHALL 包含来源阶段、任务标识、轮次和非空且唯一的问题 ID；每个通用问题 SHALL 提供短标题、完整问题及 2–3 个互斥的标签/说明选项，并可显式允许“其他”回答。发送后当前 generation MUST 停止调度后续 Agent，直到回答被提交。

#### Scenario: Agent 请求用户输入

- **WHEN** 任一 Agent 无法安全推断会影响当前产物的必要信息
- **THEN** 系统持久化 pending input request、将 generation 标记为 `awaiting_input`，并向项目所有者发送结构化 `input_required` 事件

#### Scenario: reasoning 含有疑问句

- **WHEN** reasoning 内容包含模型自问自答或疑问句
- **THEN** 系统仅展示 reasoning，不暂停 generation，也不创建 input request

#### Scenario: 上游没有 reasoning

- **WHEN** 上游只返回最终 `content` 而未返回非空 `reasoning_content`
- **THEN** 系统不生成或发送伪造的 reasoning 内容，并继续处理最终结构化输出

#### Scenario: reasoning 达到输出上限

- **WHEN** 单个任务尝试已转发的 reasoning 达到 Agent 输出字节上限
- **THEN** 系统停止转发该尝试的后续 reasoning、发送一次截断进度状态，并继续消费和校验最终 `content`

#### Scenario: generation 被取消

- **WHEN** 项目所有者停止 generation 或 SSE 客户端断开
- **THEN** 系统停止发送 reasoning、取消上游模型流并按既有契约终结 generation
