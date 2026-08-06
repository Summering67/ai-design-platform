## ADDED Requirements

### Requirement: 分层规范校验
规范校验智能体 SHALL 对初始 v2 `DesignDocument` 执行 JSON Schema、Profile、DesignGenerationContract、引用完整性、节点层级、组件属性、Token、布局能力、PRD 覆盖和可访问性检查，并输出符合版本化 `UIValidationReport` Schema 的报告。

#### Scenario: 发现多类问题
- **WHEN** 初始文档同时包含未知 Token、非法组件 variant 和缺少图片替代文本
- **THEN** 报告分别记录稳定错误码、严重级别、JSON Pointer 路径、是否可修复和说明

#### Scenario: 文档完全合法
- **WHEN** 初始文档满足全部结构、Profile、PRD 和可访问性约束
- **THEN** 报告标记通过，修正后文档与输入保持语义和稳定 ID 一致

### Requirement: 有界且安全的自动修正
规范校验智能体 SHALL 只修正被规则标记为 `repairable` 的问题。修正 MUST 保持 Profile 引用、页面和节点稳定 ID、用户确认文案、业务流程和组件语义；不得通过删除核心内容、放宽 Profile 或忽略问题获得通过状态。

#### Scenario: 修正允许的缺失属性
- **WHEN** 图片节点缺少必需替代文本且 PRD 提供了图片语义
- **THEN** 智能体补充相符的替代文本，并在报告中把问题标记为已修复

#### Scenario: 拒绝修正 Profile 漂移
- **WHEN** 初始文档的 Profile 摘要与运行固定摘要不同
- **THEN** 智能体返回 fatal 报告，不替换摘要、不迁移 Profile，也不输出可进入下一阶段的文档

### Requirement: 修正后执行完整复验
每次候选 v2 修正文档产生后，系统 MUST 重新执行全部确定性校验，而不是只复验原问题。只有零 fatal、零未修复 error 且所有契约校验通过时，修正后文档才能进入 Auto Layout。

#### Scenario: 修复引入新错误
- **WHEN** 候选修正解决未知 Token 但同时造成重复节点 ID
- **THEN** 完整复验拒绝候选结果，并在报告中记录新错误

### Requirement: 报告与文档结果一致
UIValidationReport SHALL 同时记录检测总数、修复数、未修复数、最终结论和每项问题状态。报告标记通过时 MUST 提供通过复验的完整修正文档；报告标记失败时 Root MUST NOT 使用候选修正文档继续编排。

#### Scenario: 存在不可修复错误
- **WHEN** 校验发现契约不支持但 PRD 强制要求的核心组件能力
- **THEN** 报告标记失败并保留能力不足问题，Root 不调用 Auto Layout 智能体
