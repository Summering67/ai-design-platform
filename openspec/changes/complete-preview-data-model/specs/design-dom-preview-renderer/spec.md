## ADDED Requirements

### Requirement: 结构化布局映射

系统 SHALL 在共享 UI 层定义 `DesignRenderAdapter` 及其可注入的 `LayoutMapper` 接口，并提供默认 CSS 实现，将 `ValidatedDesignRenderModel` 中已通过 DesignSystemProfile 校验的 Frame 布局映射为渲染期 React CSS 属性。渲染器 MUST 只依赖适配器接口；映射结果 MUST NOT 写回 `DesignDocument` 或 `DesignRenderNode`。

#### Scenario: 映射 Flex Frame

- **WHEN** Frame DesignRenderNode 包含方向、主轴对齐、交叉轴对齐、间距、内边距和换行配置
- **THEN** 布局映射结果包含等价的 `display`、Flex、gap、padding 和 wrap CSS 属性

#### Scenario: 映射尺寸策略

- **WHEN** 节点的宽度或高度使用 `fixed`、`fill`、`hug` 或 `minmax` 策略
- **THEN** 映射结果分别表达固定逻辑像素、可伸展、内容尺寸或最小/最大尺寸约束

#### Scenario: 映射 absolute 子项

- **WHEN** absolute Frame 的直接子节点包含合法 position 和 inset
- **THEN** Frame 建立定位上下文，子节点脱离常规布局并保留对应 inset

#### Scenario: 替换布局映射器

- **WHEN** `DesignRenderer` 注入符合 `LayoutMapper` 接口的自定义实现
- **THEN** 节点渲染使用自定义映射结果，且不修改 DSL 类型、DesignRenderNode 或递归渲染分派

### Requirement: 渲染阶段 Token 解析

系统 SHALL 在布局和视觉样式映射阶段从 `ValidatedDesignRenderModel` 固定的 Profile Token 视图解析 `{ token: string }` 引用，并 SHALL 将解析结果用于背景、圆角、阴影或排版等受支持属性。仅当 Profile 明确声明可覆盖时，模型才可携带已校验的文档级 Token override。数据派生阶段 MUST 保留原始 Token 引用。

#### Scenario: 解析已定义 Token

- **WHEN** DesignRenderNode 样式引用固定 Profile Token 视图中存在的值
- **THEN** React CSS 属性使用对应 Token 值，且输入 DesignRenderNode 保持不变

#### Scenario: 拒绝未知 Token

- **WHEN** DesignRenderNode 样式引用固定 Profile Token 视图中不存在的键
- **THEN** 映射器返回包含属性路径的结构化错误，且不使用静默默认值

### Requirement: 基础节点递归渲染

系统 SHALL 通过函数式节点策略递归渲染 Frame、Text、Image、Icon 与 Component Instance。渲染器 SHALL 保持 DesignRenderNode 的嵌套顺序，并 SHALL 使用稳定 DSL ID 作为 React key 和 `data-design-node-id`；不可见节点 MUST NOT 进入 DOM。

#### Scenario: 渲染 Frame 与文本

- **WHEN** 预览树包含嵌套 Frame 和 Text 节点
- **THEN** 输出 DOM 保持原始层级和顺序，Frame 应用映射后的布局样式，Text 展示原始文本和排版样式

#### Scenario: 渲染图片

- **WHEN** Image DesignRenderNode 包含合法 Asset source、媒体类型和 alt
- **THEN** 输出图片元素使用对应 source 和 alt，并保留稳定节点 ID

#### Scenario: 跳过不可见节点

- **WHEN** 任意 DesignRenderNode 的 `visible` 为 false
- **THEN** 该节点及其后代不出现在输出 DOM 中，其他兄弟节点顺序保持不变

#### Scenario: 渲染图标节点

- **WHEN** Icon DesignRenderNode 包含受支持图标名称
- **THEN** 输出对应图标或稳定的可访问图标表示，并保留节点身份

### Requirement: Ant Design 组件注册表

系统 SHALL 定义可注入的 `ComponentRegistry` 接口，并提供默认 Ant Design 注册表，将 Profile 允许的 `ui.button`、`ui.input`、`ui.card`、`ui.form` 和 `ui.menu` 分别映射为 Ant Design `Button`、`Input`、`Card`、`Form` 和 `Menu`。目标组件 binding SHALL 由 DesignRenderAdapter 持有，不得写入 DesignDocument 或 DesignSystemProfile。注册项 SHALL 根据 Profile 组件契约受控转换 `variant`、命名 slot 与 `overrides`。递归节点渲染器 MUST NOT 直接依赖 Ant Design 导出。

#### Scenario: 渲染受支持组件

- **WHEN** Component Instance 使用 Profile 允许的 `componentRef`、合法属性，且当前适配器提供匹配的 Ant Design binding
- **THEN** 注册表渲染对应 Ant Design 组件，并保留实例稳定 ID、变体和允许的覆盖属性

#### Scenario: 保留组件内容属性

- **WHEN** Button、Card 或其他受支持组件通过命名内容 slot 或 overrides 提供 Profile 允许的文本、内容或数据属性
- **THEN** Ant Design 组件接收等价的受控 Props，原始 overrides 不被修改

#### Scenario: 拒绝未知组件或错误绑定

- **WHEN** `componentRef` 未注册，或适配器内部 Component Binding 的来源/导出名称与注册项不匹配
- **THEN** 注册表返回带组件引用路径的结构化渲染错误，不使用普通 div 或其他组件静默替代

#### Scenario: 拒绝不支持的组件属性

- **WHEN** variant 或 overrides 包含对应注册项白名单之外的属性或非法值
- **THEN** 注册表返回结构化渲染错误，且不得把未知对象直接展开到 Ant Design 组件或原生 DOM

#### Scenario: 替换组件库注册表

- **WHEN** `DesignRenderer` 注入符合 `ComponentRegistry` 接口的非 Ant Design 实现
- **THEN** Component Instance 通过该实现渲染，且不修改 `componentRef`、DesignRenderNode 类型或递归渲染器

### Requirement: 可复用静态设计稿组件

共享 UI SHALL 导出 `DesignRenderer` block，通过 Props 接收 `ValidatedDesignRenderModel` 以及可选 `DesignRenderAdapter`。该模型 SHALL 携带 Profile ID、版本、内容摘要和不可伪造或可重新验证的校验凭据；手工构造的裸 DesignRenderNode 数组不得进入渲染入口。适配器 SHALL 聚合 `ThemeResolver`、`LayoutMapper`、`ComponentRegistry`、`IconRegistry` 和 `AssetResolver`，并声明目标标识、支持的 Profile 范围和能力集合。该组件 MUST NOT 读取应用路由、接口、环境变量或持久化状态。

#### Scenario: 渲染完整静态预览

- **WHEN** `DesignRenderer` 接收由合法且 Profile 校验通过的登录页 Graph 派生的 ValidatedDesignRenderModel
- **THEN** 组件输出包含布局、文本、图片和 Ant Design 组件的完整静态 React DOM 结构

#### Scenario: 呈现结构化渲染错误

- **WHEN** Token、布局、图标或组件映射失败
- **THEN** `DesignRenderer` 提供可访问的错误状态，并通过公开错误边界保留结构化错误信息

### Requirement: 团队风格运行时适配

系统 SHALL 定义可注入的 `DesignRenderAdapter`，使已由 DesignSystemProfile 确定的主题、布局、组件、图标和资源目标实现可以替换。DSL 节点类型、稳定 ID、节点顺序和 Graph 校验 MUST NOT 因渲染适配器变化而变化；适配器 MUST NOT 放宽 Profile 约束。

#### Scenario: 使用默认运行时

- **WHEN** `DesignRenderer` 未传入渲染适配器
- **THEN** 仅当默认 CSS/Ant Design 适配器声明支持文档 Profile 与全部必需能力时使用该适配器，否则返回 `adapter_incompatible` 结构化错误

#### Scenario: 注入团队运行时

- **WHEN** 调用方为同一 Profile 注入不同目标的渲染适配器
- **THEN** 设计稿使用注入的目标实现，同时继续遵守 Profile 的 Token、组件、图标和布局约束

### Requirement: 语义 Token 与 typography 主题解析

`ThemeResolver` SHALL 将 DesignSystemProfile 允许的语义 Token 和 Text typography 映射为渲染期视觉值，并 SHALL 按“Profile 锁定值 → Profile 明确允许且已校验的文档级 override → 结构化错误”的顺序解析。解析器 MUST NOT 修改原始 Token 或 Text DesignRenderNode。

#### Scenario: Profile 提供团队视觉值

- **WHEN** 两个 DesignSystemProfile 对同一 `surface.canvas`、`radius.md` 或 typography Token 提供不同值
- **THEN** 相同 DSL 在生成前被约束为对应 Profile，并在渲染时产生相应视觉 CSS，节点结构和语义保持一致

#### Scenario: 未知语义 Token

- **WHEN** Profile 未定义某个 Token，或文档提供 Profile 未授权的同名覆盖
- **THEN** 返回包含 Token 路径的结构化错误，不静默使用默认颜色、间距或字体

### Requirement: 可替换的图标与资源解析

系统 SHALL 通过 `IconRegistry` 将 Icon 名称解析为团队图标组件或可访问表示，并 SHALL 通过 `AssetResolver` 按 Profile 资源策略将 Asset 描述解析为安全的实际资源地址或占位结果。两者 MUST NOT 修改 DesignRenderNode。

#### Scenario: 替换渲染目标图标库

- **WHEN** 同一 Profile 下两个渲染适配器为同一 Icon 名称注入不同的 `IconRegistry`
- **THEN** 输出不同的图标实现，但节点 ID、顺序和可访问名称保持一致

#### Scenario: 注入资源 CDN 解析器

- **WHEN** 运行时注入将 Asset source 转换为团队 CDN 地址的 `AssetResolver`
- **THEN** Image 使用解析后的安全地址和原始 alt，且 DSL Asset 数据保持不变

#### Scenario: 资源或图标解析失败

- **WHEN** Icon 或 Asset 无法由当前注册表/解析器解析
- **THEN** 返回带节点路径的结构化错误或受控可访问占位结果，不把任意对象直接写入 DOM
