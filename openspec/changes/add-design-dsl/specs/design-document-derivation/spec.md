## ADDED Requirements

### Requirement: Graph 驱动的 DOM 预览输入
系统 SHALL 仅从已校验的 `DesignDocument` Graph 派生首期 DOM/CSS 渲染输入，并将 Flex 的方向、对齐、间距、内边距和尺寸策略映射为浏览器布局。渲染期 `ResolvedLayout` MUST NOT 写回 DSL；Root MUST NOT 自身渲染。

#### Scenario: 渲染 Flex 设计结构
- **WHEN** 渲染器接收包含 Flex Frame、flow 子项、样式和文本的合法 Graph
- **THEN** 输出保持 `childIds` 顺序、可见性、Flex 布局意图与结构化设计样式，且不修改输入文档

#### Scenario: 渲染 absolute 子项
- **WHEN** Graph 中 absolute 容器的直接子节点具有 `position: "absolute"` 和足以确定位置的 inset
- **THEN** 渲染输入将该子项脱离 Flex 主轴布局并保留其定位意图

### Requirement: React Tailwind Ant Design 单向代码生成
系统 SHALL 仅从已校验 Graph 生成 React、Tailwind CSS 和 Ant Design 代码。生成器 SHALL 将 token 派生为目标主题值，将 `component-instance` 通过 `ComponentBinding` 映射为指定 Ant Design 导出，并保持 `childIds` 的输出顺序。人工修改生成代码 MUST NOT 回写或覆盖 `DesignDocument`。

#### Scenario: 生成受支持组件实例
- **WHEN** Graph 包含绑定到 `react-tailwind-antd` 的 `ui.button`、`ui.input`、`ui.card`、`ui.form` 或 `ui.menu` 实例，以及合法 variant 和 overrides
- **THEN** 生成器输出相应 Ant Design import 与 JSX，并将布局和令牌派生为等价 Tailwind 或主题值

#### Scenario: 拒绝未知代码绑定
- **WHEN** Graph 中组件实例缺少目标绑定、绑定目标不匹配或 overrides 不符合组件定义
- **THEN** 生成器返回可定位的生成错误，且不以不等价的默认 JSX 静默替代

### Requirement: 跨渲染器兼容性边界
系统 SHALL 将跨渲染器兼容性限定为节点层级、可见性、顺序、Flex 布局意图、尺寸策略、主要间距、组件语义/变体和设计令牌一致。系统 MUST NOT 承诺字体、阴影、浏览器环境或复杂 Ant Design 组件的像素级一致。

#### Scenario: 比较不同渲染目标的结构化结果
- **WHEN** 同一合法 Graph 被派生到 DOM 预览输入和 React 代码
- **THEN** 两种输出对节点顺序、可见性、主要 Flex 策略、组件语义和 token 引用保持一致，而不以像素差异判定失败
