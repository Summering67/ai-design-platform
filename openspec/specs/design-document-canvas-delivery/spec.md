# design-document-canvas-delivery Specification

## Purpose

定义最终设计文档到工作台画布的交付、门禁与渲染。
## Requirements
### Requirement: 最终设计文档画布交付

v2 画布 Renderer SHALL 接收显式 viewportId，依据 final DesignDocument 的 `resolvedLayouts[viewportId]` 递归绝对定位渲染。通过 Schema 但缺少 Geometry 快照的文档不得作为成功画布结果交付。

#### Scenario: 固定 viewport 渲染

- **WHEN** final DesignDocument 包含指定 viewport 的完整 Geometry
- **THEN** 画布按 Geometry 输出节点位置和尺寸，并保留视觉样式及业务 props

### Requirement: Geometry viewport 渲染

v2 画布 Renderer SHALL 接收显式 viewportId，并只使用 `resolvedLayouts[viewportId]` 为节点生成相对父节点的绝对定位；缺少 viewport 或节点 Geometry 时必须返回稳定错误，不得回退到 CSS Flex。

#### Scenario: Geometry 定位渲染

- **WHEN** Renderer 收到包含指定 viewport 完整 Geometry 的 DesignDocument
- **THEN** 每个节点按对应 Geometry 绝对定位，并保留视觉样式与业务 props

