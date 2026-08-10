## MODIFIED Requirements

### Requirement: 严格的 LayoutPlan 契约

LayoutPlan SHALL 删除模型 viewport，使用输入声明的 viewport ID；sizing SHALL 使用 fixed/fill/hug 加可选 min/max；layoutItem.position SHALL 为 auto/absolute，且 offset 与 inset 组合必须满足语义约束。模型不得输出 Geometry、CSS 或 DesignDocument。

#### Scenario: 未知 viewport 被拒绝

- **WHEN** LayoutPlan 引用输入未声明的响应式 viewport
- **THEN** Schema 或语义门禁拒绝该 operation

### Requirement: 确定性布局应用与渲染投影

Auto Layout 内部 SHALL 使用纯函数 Flex 模块解析已校验 LayoutPlan，并为每个固定 viewport 生成完整 `resolvedLayouts`；缺少测量或 Geometry 不完整时不得产生成功 result。

#### Scenario: 多视口解析

- **WHEN** 输入包含多个固定 viewport 和对应 responsive 覆盖
- **THEN** 每个 viewport 都产生独立完整 Geometry 快照
