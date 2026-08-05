## ADDED Requirements

### Requirement: 显式判别旧文档格式
迁移入口 MUST 根据版本和结构显式判别现有 v1 Graph、v1 Tree 或 v2 Tree，不得仅凭 `version: "1.0.0"` 假定唯一旧结构。未知、混合或歧义结构 MUST 被拒绝。

#### Scenario: 判别 v1 Graph
- **WHEN** 文档包含页面 nodes 对象表、rootId 和父子引用
- **THEN** 迁移器将输入识别为 v1 Graph，并使用 Graph 迁移策略

#### Scenario: 判别 v1 Tree
- **WHEN** 文档包含页面 children 嵌套树且不包含 Graph 对象表
- **THEN** 迁移器将输入识别为 v1 Tree，并使用 Tree 迁移策略

#### Scenario: 拒绝混合格式
- **WHEN** 输入同时包含互相冲突的 Graph 与 Tree 主结构或不满足任一已知格式
- **THEN** 迁移器返回格式判别错误且不产生 v2 文档

### Requirement: 确定性迁移为自包含 v2 文档
迁移器 SHALL 保留可映射的文档 ID、名称、Asset、稳定节点 ID、节点顺序、文本、组件和样式，并解析固定 Profile 生成内嵌 `designSystem` 快照。成功结果 MUST 是通过完整 Schema 和语义校验的 `DesignDocument` 2.0。

#### Scenario: 迁移合法 v1 Graph
- **WHEN** v1 Graph 连通、无循环、Profile 可按声明摘要解析且全部字段存在确定映射
- **THEN** 迁移器按 childIds 顺序生成合法 v2 children 树，并返回目标版本 2.0.0

#### Scenario: 迁移合法 v1 Tree
- **WHEN** v1 Tree 节点唯一、Profile 可解析且全部字段存在确定映射
- **THEN** 迁移器保留原嵌套顺序并生成合法自包含 v2 文档

### Requirement: 迁移失败保持原数据不变
迁移 MUST 在隔离副本上完成。缺失或摘要不匹配的 Profile、重复 ID、多个父节点、循环、悬空 Asset、未知节点类型、无法映射的样式或组件 binding、非 JSON 值以及最终 v2 校验失败，均 MUST 使整次迁移失败且不得写入部分结果。

#### Scenario: Profile 无法固定
- **WHEN** 旧文档引用的 Profile 不存在或内容摘要不匹配
- **THEN** 迁移失败并返回 Profile 标识、版本、摘要和相关 JSON 路径

#### Scenario: Graph 结构损坏
- **WHEN** 旧 Graph 存在循环、多个父节点、重复 childId 或不可达节点
- **THEN** 迁移失败并保持原持久化 payload 不变

#### Scenario: 不支持的旧字段
- **WHEN** 旧文档包含无法确定映射到 v2 的样式、组件 binding 或运行时值
- **THEN** 迁移器返回稳定的不兼容错误，不通过默认值静默丢弃语义

### Requirement: 迁移结果包含可审计元数据
每次迁移结果 MUST 包含原始格式、原始版本、目标版本、迁移器版本和结构化警告；错误 MUST 包含稳定错误码及源 JSON 路径。成功持久化 v2 后，系统 MUST 通过现有备份或审计边界保留原始 v1 payload，但在线读取只使用 v2 文档。

#### Scenario: 成功迁移返回审计信息
- **WHEN** v1 文档成功迁移并持久化
- **THEN** 结果记录源格式、1.0.0、2.0.0、迁移器版本及所有非破坏性警告

#### Scenario: 迁移后再次读取
- **WHEN** 已成功迁移的设计再次被读取
- **THEN** 系统直接验证和读取 v2 文档，不重复运行 v1 迁移

### Requirement: 切换后仅写入 v2
运行时切换完成后，新增和修改设计的持久化边界 MUST 只接受完整合法的 v2 文档。v1 输入只能进入显式迁移接口，不能继续通过普通写入口产生新的旧格式数据。

#### Scenario: 普通写入口收到 v1
- **WHEN** 调用方在普通创建或更新入口提交 v1 Graph 或 v1 Tree
- **THEN** 系统返回需要迁移的版本错误且不写入数据

#### Scenario: v2 写入成功
- **WHEN** 调用方提交完整合法且权限允许的 v2 文档
- **THEN** 系统原子持久化该文档并将其作为后续读取的唯一设计状态
