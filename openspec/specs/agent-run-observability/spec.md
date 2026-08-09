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

#### Scenario: 上游没有 reasoning

- **WHEN** 上游只返回最终 `content` 而未返回非空 `reasoning_content`
- **THEN** 系统不生成或发送伪造的 reasoning 内容，并继续处理最终结构化输出

#### Scenario: reasoning 达到输出上限

- **WHEN** 单个任务尝试已转发的 reasoning 达到 Agent 输出字节上限
- **THEN** 系统停止转发该尝试的后续 reasoning、发送一次截断进度状态，并继续消费和校验最终 `content`

#### Scenario: generation 被取消

- **WHEN** 项目所有者停止 generation 或 SSE 客户端断开
- **THEN** 系统停止发送 reasoning、取消上游模型流并按既有契约终结 generation
