# agent-backed-project-generation Specification

## Purpose

定义由 Root Agent 驱动、UI Design 与 Auto Layout 两个专业 Agent 执行的项目级设计生成。
## Requirements
### Requirement: Root Agent 项目生成

Auto Layout 阶段 SHALL 接收 InitialUIDocument、布局要求、布局能力、固定 viewport 和 measurement 输入，在内部生成 LayoutPlan、解析 Geometry，并返回包含完整 `resolvedLayouts` 的 final DesignDocument。

#### Scenario: Geometry 门禁

- **WHEN** 任一固定 viewport 的布局无法解析或快照不完整
- **THEN** Root 不发送 completed result

### Requirement: Auto Layout Geometry 交付

Auto Layout SHALL 在返回 final DesignDocument 前，为每个固定 viewport 生成完整 `resolvedLayouts`，并将 layout/layoutItem/responsive 作为布局事实。缺少 Geometry 的文档不得发送 completed 事件。

#### Scenario: Geometry 快照完整

- **WHEN** Auto Layout 完成所有已声明 viewport 的布局解析
- **THEN** final DesignDocument 为每个 viewport 提供覆盖全部可见节点的 `resolvedLayouts`，并允许发送 completed 事件

### Requirement: Auto Layout 响应式文档契约
最终 DesignDocument v2 Schema SHALL 接受由 Auto Layout Agent 内部合法 LayoutPlan 和布局模块写入的响应式 layout、layoutItem、flexWrap、sizing 和可选 computedLayout 字段；所有枚举与尺寸模式 MUST 受 GenerationContract 限制。Auto Layout Agent MUST 同步提供当前画布可消费的基础 style 投影，并在返回前完成最终文档校验。

#### Scenario: Auto Layout 写入响应式能力
- **WHEN** Auto Layout 计划在合法断点为已有节点提供方向、换行和尺寸覆盖
- **THEN** Auto Layout Agent 内部布局模块写入对应响应式字段，最终文档通过 DesignDocument v2 Schema 和自身渲染契约校验

#### Scenario: 模型尝试写入坐标
- **WHEN** Auto Layout 模型输出包含 computedLayout、x、y、width 或 height 几何结果而非 LayoutPlan 允许的尺寸意图
- **THEN** LayoutPlan Schema 拒绝输出且最终文档保持不变

