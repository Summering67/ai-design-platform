## ADDED Requirements

### Requirement: Tree 到 Graph 的确定性规范化
系统 SHALL 仅将通过 Tree Schema、结构、布局与组件校验的 `DesignTreeDocument` 规范化为 `DesignDocument` Graph。每页 SHALL 有唯一不可编辑 Root，Root 的 `parentId` MUST 为 `null`；普通节点 MUST 有唯一父节点；`childIds` 的顺序 SHALL 保留树顺序、图层顺序、Flex 排列顺序与代码输出顺序。

#### Scenario: 规范化合法嵌套设计
- **WHEN** 合法 Tree 包含页面根 ID 和按顺序嵌套的 Frame、文本、图片、图标与组件实例
- **THEN** 系统保留全部合法节点 ID，创建或保留对应 Root，并生成父子关系双向一致的有序 Graph

#### Scenario: 拒绝非法树与布局组合
- **WHEN** Tree 出现重复节点 ID、非法子节点、未知资源或组件引用，或 absolute 父节点的直接子节点未提供合法 absolute 定位
- **THEN** 系统返回可定位错误且不生成部分 Graph

### Requirement: Graph 校验与无损反规范化
系统 SHALL 在使用或持久化 Graph 前验证 Root 唯一性、从 Root 的可达性、无循环、无孤儿、无重复 child、引用存在性和 `parentId`/`childIds` 双向一致性。系统 SHALL 从每页 Root 按 `childIds` 顺序反规范化为 Tree，并在任意损坏 Graph 上失败而非静默跳过节点。

#### Scenario: Graph 往返保留设计意图
- **WHEN** 系统将合法 Tree 规范化、反规范化并再次规范化
- **THEN** canonicalize 后的两个 Graph 保留 document、page、root 与 node ID、父子关系、节点顺序、样式、布局、文本、资源、语义、组件和令牌引用，且不引入或删除节点

#### Scenario: 反规范化拒绝损坏 Graph
- **WHEN** Graph 缺少引用的 child、存在循环或包含不可从 Root 到达的节点
- **THEN** 系统返回可定位错误，且不输出不完整 Tree

### Requirement: 原子 DesignOperation 应用
系统 SHALL 将后续编辑和 AI 修改表示为 `DesignOperation[]`，并在文档副本上预校验和应用整批操作，最终 Graph 校验通过后一次性提交。系统 MUST 支持插入子树、移动、删除、设置文本、样式字段 set/unset、布局完整替换、布局项完整替换和组件替换；任何操作失败 MUST 保持原文档不变。

#### Scenario: 成功应用混合操作批次
- **WHEN** 操作批次引用有效页面和节点，且移动、样式、文本、布局与组件修改均符合 Schema 和 Graph 规则
- **THEN** 系统返回一次性更新后的合法 Graph，未涉及字段保持不变

#### Scenario: 操作批次失败不产生半更新
- **WHEN** 批次中的任一操作存在节点 ID 冲突、期望父节点不匹配、非法索引或无效组件引用
- **THEN** 系统返回该操作的可定位错误，且输入 Graph 与提交前完全一致

### Requirement: API 侧设计文档边界
系统 SHALL 在 `apps/api/internal/design` 中限制设计文档输入大小、校验版本和 Schema、执行支持的迁移及调用方权限检查，并且只将规范化后的 `DesignDocument` Graph 交给持久化边界。API 侧 MUST NOT 执行 DOM 布局或生成 JSX。

#### Scenario: API 拒绝无效文档而不持久化
- **WHEN** API 边界接收超过限制、版本不支持或未通过契约校验的文档
- **THEN** 系统在写入持久化层之前返回稳定且不暴露内部细节的错误
