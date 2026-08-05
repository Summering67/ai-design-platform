## ADDED Requirements

### Requirement: 可判别的静态渲染节点

系统 SHALL 从合法 `DesignDocument` Graph 派生按 `kind` 判别的 Frame、Text、Image、Icon 与 Component Instance `DesignRenderNode`。每个渲染节点 SHALL 保留原始稳定 `id`、可见性以及存在于 DSL 中的名称、样式、布局项和语义数据；Root MUST NOT 作为渲染节点输出。

#### Scenario: 保留节点稳定身份

- **WHEN** 合法 Graph 中包含具有稳定 ID 和通用设计属性的可渲染节点
- **THEN** 派生结果包含相同 ID 和通用属性，且不会生成替代 ID 或输出 Root 节点

#### Scenario: 保留节点类型边界

- **WHEN** 调用方按 DesignRenderNode 的 `kind` 读取节点数据
- **THEN** 每种节点只暴露其通用字段和该节点种类的专属渲染字段

### Requirement: 保留文本与图标内容

Text DesignRenderNode SHALL 保留原始 `text` 和 `typography`；Icon DesignRenderNode SHALL 保留原始图标 `name`。派生过程 MUST NOT 将字体属性或其中的 Token 引用转换为 CSS 值。

#### Scenario: 派生文本节点

- **WHEN** 合法 Graph 包含带文本内容、字体属性和 Token 引用的 Text 节点
- **THEN** 对应 DesignRenderNode 原样保留 `text` 与 `typography`，包括尚未求值的 Token 引用

#### Scenario: 派生图标节点

- **WHEN** 合法 Graph 包含 Icon 节点
- **THEN** 对应 DesignRenderNode 保留图标名称供后续渲染器解析

### Requirement: 解析图片资源

Image DesignRenderNode SHALL 保留 `assetId` 和可选 `alt`，并 SHALL 携带文档资源表中由 `assetId` 指向且已通过 Profile 资源策略校验的 Asset 数据，以便渲染器获得资源来源和媒体类型。

#### Scenario: 派生图片节点

- **WHEN** 合法 Graph 包含引用已存在 Asset 的 Image 节点
- **THEN** 对应 DesignRenderNode 保留 `assetId`、`alt` 以及该 Asset 的资源数据

### Requirement: 保留组件实例属性

Component Instance DesignRenderNode SHALL 保留 `componentRef`、`variant`、命名内容 slot 和 `overrides`，并 SHALL 携带从固定 DesignSystemProfile 解析的组件语义契约。目标 Component Binding 属于 DesignRenderAdapter，MUST NOT 从 DesignDocument 派生或进入 DesignRenderNode。派生过程 MUST NOT 将组件实例提前转换为 React、Ant Design 或其他框架组件。

#### Scenario: 派生组件实例

- **WHEN** 合法 Graph 包含具有变体、命名 slot 和覆盖属性的 Component Instance，且其 `componentRef` 存在于文档固定的 DesignSystemProfile
- **THEN** 对应 DesignRenderNode 原样保留组件引用、变体、命名 slot、覆盖属性和 Profile 组件语义契约，不携带目标框架 binding

### Requirement: 保留 Graph 子节点顺序

系统 SHALL 严格按照 Root 和 Frame 的 `childIds` 顺序递归派生 DesignRenderNode 树，并 SHALL 为叶节点输出空子节点集合。派生过程 MUST NOT 排序、去重或修改输入 Graph。

#### Scenario: 保留嵌套节点顺序

- **WHEN** Root 或 Frame 的 `childIds` 以确定顺序引用多个不同种类节点
- **THEN** 对应 DesignRenderNode 按完全相同的顺序出现，嵌套层级和稳定 ID 保持不变

#### Scenario: 派生不修改原文档

- **WHEN** 调用方对合法 Graph 执行预览派生
- **THEN** 派生完成后的输入 Graph 与调用前保持一致

### Requirement: 结构化派生失败

系统 MUST 在派生前校验 `DesignDocument`，并 MUST 将无效 Root、父子关系、资源引用或组件引用等问题作为带 `code`、`path` 和 `message` 的 `ContractError[]` 返回。常规无效输入 MUST NOT 通过未结构化异常暴露。

#### Scenario: 无效文档返回校验错误

- **WHEN** `deriveDomPreview` 接收不满足 Graph 不变量的文档
- **THEN** 返回失败 `Result` 和可定位的结构化错误，且不返回部分 DesignRenderModel

#### Scenario: 未知资源返回引用错误

- **WHEN** Image 节点引用文档资源表中不存在的 `assetId`
- **THEN** 返回包含该节点 `assetId` 路径的 `unknown_asset` 错误，且不返回部分预览树

#### Scenario: 未知组件返回引用错误

- **WHEN** Component Instance 的 `componentRef` 不存在于文档所固定的 DesignSystemProfile
- **THEN** 返回包含该节点 `componentRef` 路径的 `unknown_component` 错误，且不返回部分 DesignRenderModel

### Requirement: 生成经过 Profile 固定的渲染模型

系统 SHALL 将 DesignRenderNode、固定的 Profile ID/版本/内容摘要、Profile Token 视图、已校验 Asset 和校验凭据组合为 `ValidatedDesignRenderModel`。`DesignRenderer` MUST 只接受该模型，不接受调用方手工构造的裸节点数组或独立 Token 表。公开新入口 SHALL 命名为 `deriveDesignRenderModel`。

#### Scenario: 渲染模型绑定原 Profile

- **WHEN** 合法 DesignDocument 使用其保存的 Profile 引用派生渲染模型
- **THEN** 结果携带完全相同的 Profile ID、版本和内容摘要，且后续不能替换 Profile 而绕过重新校验

### Requirement: 保留旧派生入口兼容性

系统 SHALL 保留 `deriveDomPreview` 和 `PreviewNode` 作为 `deriveDesignRenderModel` 与 `DesignRenderNode` 的兼容入口或类型别名，不直接破坏已有 DSL API。兼容入口的参数、`Result` 成功/失败结构和既有公共字段 MUST 保持兼容；新增调用方 SHALL 使用 Render 命名。

#### Scenario: 旧调用方继续派生

- **WHEN** 现有调用方继续调用 `deriveDomPreview(document)` 并读取既有 PreviewNode 字段
- **THEN** 调用仍可工作并获得与新派生内核一致的节点语义，无需迁移到 DesignPreview 或 DesignPreviewRuntime
