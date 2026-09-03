## ADDED Requirements

### Requirement: 结构化请求保留稳定前缀
系统 MUST 将结构化模型请求的稳定角色说明与响应 Schema 放在动态业务上下文之前，并使用确定性序列化，使相同 purpose 和 Schema 的请求产生相同前缀。

#### Scenario: 相同契约处理不同业务输入
- **WHEN** 两次结构化请求使用相同 purpose 和响应 Schema 但业务输入不同
- **THEN** 两次请求的 system 消息完全相同，差异仅出现在后续动态消息

### Requirement: 指令与校验反馈位于动态请求末尾
系统 MUST 从业务上下文中分离阶段指令与 Harness 校验反馈，并将它们作为最后的文本消息追加，其中阶段指令 MUST 是该消息的最后字段。

#### Scenario: Harness 在失败后重试
- **WHEN** 首次请求失败且 Harness 使用短校验反馈重试
- **THEN** 重试请求在业务上下文结束前与首次请求保持相同，并在末尾追加校验反馈和阶段指令

### Requirement: 多模态 Codegen 复用共享输入前缀
系统 MUST 按共享规则、共享文档上下文、原始画布图片、阶段上下文、额外阶段图片、最终指令的顺序构造多模态内容，并使生成与修复请求使用相同模型 purpose。

#### Scenario: 生成候选后执行修复
- **WHEN** Codegen 使用同一 DesignDocument、画布图片和 CodePlan 先生成再修复候选
- **THEN** 生成与修复请求在候选和诊断等修复专属内容出现前保持相同内容块前缀，且各自的阶段指令均位于末尾

#### Scenario: 执行视觉审查
- **WHEN** Codegen 为某个 viewport 添加候选预览图片
- **THEN** 预览图片位于最终视觉审查指令之前，最终指令仍为最后一个内容块

### Requirement: 缓存优化不改变模型调用契约
系统 MUST 保持现有 ModelPort interface、模型响应包络解析和业务输出 Schema 不变。

#### Scenario: 调用现有结构化模型能力
- **WHEN** 现有 Agent 通过 ModelPort 发起文本或多模态结构化请求
- **THEN** 调用参数与返回业务对象的结构保持兼容
