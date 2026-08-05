## ADDED Requirements

### Requirement: Graph 仅作为可重建编辑投影
系统 SHALL 从已验证的 v2 Tree 建立包含节点索引、父节点索引和子节点顺序的内存 Graph。Graph MUST 可完全丢弃并从规范 Tree 重建，且 MUST NOT 被独立持久化或在冲突时覆盖 Tree。

#### Scenario: 从 Tree 重建 Graph
- **WHEN** 编辑器加载合法 v2 文档
- **THEN** 系统按 children 顺序建立完整 Graph，且每个非 Root 节点只有一个父节点

#### Scenario: 丢弃 Graph 不丢失设计
- **WHEN** 当前编辑 Graph 被清空并从同一规范文档重建
- **THEN** 重建结果包含相同节点、父子关系和顺序

### Requirement: 操作命令原子提交到规范 Tree
编辑命令 SHALL 在隔离的派生 Graph 或 Tree 副本上应用。系统 MUST 在全部命令成功后重新生成完整 v2 Tree，并执行 Schema 与语义校验；只有全部通过才能原子替换规范文档，操作列表和中间 Graph MUST NOT 成为恢复来源。

#### Scenario: 成功提交一批操作
- **WHEN** 一批插入、移动、删除、文本、样式或 props 修改均合法
- **THEN** 系统生成一份新的合法 v2 Tree 并一次性替换旧文档

#### Scenario: 批次中任一操作失败
- **WHEN** 任一操作产生重复 ID、悬空引用、非法样式、非法组件 props 或其他契约错误
- **THEN** 整批操作失败，原规范文档保持字节级或语义级不变

### Requirement: 依赖与 imports 从节点确定性收集
组件依赖和代码 imports MUST 从 component 节点的 `tag`、`packageName` 与 `defaultModule` 确定性派生。规范文档 MUST NOT 保存可与节点信息冲突的 `dependencies` 或生成后的 import 文本。

#### Scenario: 合并重复组件依赖
- **WHEN** 多个节点引用相同包中的相同组件
- **THEN** 依赖收集器输出一项确定排序的去重依赖，且不修改原文档

#### Scenario: 本地元素不产生包依赖
- **WHEN** element 或 text 节点未声明 packageName
- **THEN** 依赖收集器不为该节点生成包 import

### Requirement: 预览和代码是只读派生产物
DOM 预览、`DesignRenderModel`、React/Vue 模板、CSS、className、解析后的 Asset URL 和目标组件 binding MUST 仅从合法 v2 文档派生，MUST NOT 反向写入规范文档或放宽文档校验。

#### Scenario: 派生预览不污染事实源
- **WHEN** 渲染适配器计算 className、默认 props、资源地址或布局测量值
- **THEN** 计算值只存在于派生模型，输入 v2 JSON 保持不变

#### Scenario: 目标适配器不支持节点
- **WHEN** 文档本身合法但选定的 React 或 Vue 适配器不支持某个合法节点能力
- **THEN** 适配器返回目标能力错误，不修改或降级规范文档语义

### Requirement: 派生结果可重复
在规范文档、派生器版本和显式派生选项相同时，Graph、依赖集合、预览输入和代码输出 MUST 保持确定性，不得依赖可变外部 Profile、未声明组件默认值或遍历时生成的随机标识。

#### Scenario: 重复派生相同结果
- **WHEN** 对同一文档使用相同版本和选项连续执行两次派生
- **THEN** 两次输出在规范化比较下完全一致

#### Scenario: 文档固定设计系统语义
- **WHEN**团队外部设计系统配置在文档创建后发生变化
- **THEN** 旧文档仍仅使用其内嵌快照产生与变更前一致的派生语义
