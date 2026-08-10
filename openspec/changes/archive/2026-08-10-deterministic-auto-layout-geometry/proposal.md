## Why

Auto Layout 当前只生成部分声明式字段，应用模块与画布 Renderer 对字段的解释不一致，导致 Schema 合法的布局计划无法稳定产生可见布局。需要把 Flex 计划、固定视口 Geometry 和最终渲染消费路径收敛为一个可复验的契约。

## What Changes

- **BREAKING** 收紧 LayoutPlan 与 DesignDocument v2 的布局字段，统一 sizing、position、responsive 和 Geometry 语义。
- 扩展 Auto Layout 输入，加入布局要求、能力、固定视口和独立 measurement 映射。
- 以 `auto_layout.tsx` 的主轴分配思路为参考，实现 Python 纯函数 Flex 计算模块。
- 为每个固定视口生成完整 `resolvedLayouts` Geometry 快照。
- 让 Renderer 只依据 Geometry 定位渲染；位置编辑回写为 `layoutItem.offset`。
- 同步共享类型、fixtures、Agent Prompt、测试和 OpenSpec 主规范。

## Capabilities

### New Capabilities

- `deterministic-layout-geometry`: 固定视口下的确定性 Flex 解析、Geometry 快照和渲染接口。

### Modified Capabilities

- `agent-intermediate-artifacts`: 修改 Auto Layout 输入、LayoutPlan 约束和确定性应用职责。
- `agent-backed-project-generation`: 修改 Auto Layout 的布局输入及最终文档产物。
- `design-document-canvas-delivery`: 修改 Renderer 的 Geometry 消费和 viewport 选择。

## Impact

- 影响 `packages/design-contract` v2 Schema 与类型、`apps/server` Auto Layout Agent、`packages/design-dsl` 类型/派生逻辑和 `packages/ui` 画布 Renderer。
- 不新增运行时依赖，不修改 HTTP/SSE 外部接口。
- 现有 v2 布局 style 双写和节点级 `computedLayout` 将被移除。
