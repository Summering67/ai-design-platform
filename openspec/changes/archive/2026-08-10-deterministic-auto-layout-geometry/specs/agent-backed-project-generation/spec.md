## MODIFIED Requirements

### Requirement: Root Agent 项目生成

Auto Layout 阶段 SHALL 接收 InitialUIDocument、布局要求、布局能力、固定 viewport 和 measurement 输入，在内部生成 LayoutPlan、解析 Geometry，并返回包含完整 `resolvedLayouts` 的 final DesignDocument。

#### Scenario: Geometry 门禁

- **WHEN** 任一固定 viewport 的布局无法解析或快照不完整
- **THEN** Root 不发送 completed result
