## MODIFIED Requirements

### Requirement: 最终设计文档画布交付

v2 画布 Renderer SHALL 接收显式 viewportId，依据 final DesignDocument 的 `resolvedLayouts[viewportId]` 递归绝对定位渲染。通过 Schema 但缺少 Geometry 快照的文档不得作为成功画布结果交付。

#### Scenario: 固定 viewport 渲染

- **WHEN** final DesignDocument 包含指定 viewport 的完整 Geometry
- **THEN** 画布按 Geometry 输出节点位置和尺寸，并保留视觉样式及业务 props
