## ADDED Requirements

### Requirement: Agent 成功说明消息
系统 SHALL 在 Root Agent 成功产生最终设计文档后创建简短助手消息以完成既有项目对话轮次；该消息 MUST NOT 包含或替代 DesignDocument。

#### Scenario: 成功后保留对话轮次
- **WHEN** Agent 运行成功并返回最终文档
- **THEN** 系统保存一条助手完成说明并将生成尝试标记为完成
