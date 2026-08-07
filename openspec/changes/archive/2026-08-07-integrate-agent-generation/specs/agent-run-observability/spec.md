## ADDED Requirements

### Requirement: 可见的 Agent 输出
系统 SHALL 将 Agent 运行事件作为 SSE `agent` 事件发送给项目所有者。每个专业阶段完成事件 SHALL 包含已验证结构化输出；事件 MUST NOT 包含提示词、原始模型消息、堆栈、内部路径或凭证。

#### Scenario: 查看阶段返回
- **WHEN** 专业 Agent 完成已验证输出
- **THEN** 前端收到包含阶段、任务身份、尝试次数和 output 的 agent 事件
