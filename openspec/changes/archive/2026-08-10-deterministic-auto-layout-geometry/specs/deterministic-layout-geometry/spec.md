## ADDED Requirements

### Requirement: 固定视口确定性布局

系统 SHALL 使用已校验的 LayoutPlan、固定 viewport 和独立 measurement 映射生成完整的 `resolvedLayouts`。相同输入 MUST 产生等价 Geometry；缺少必要 measurement、约束冲突、非法尺寸或不完整节点快照时 MUST 返回稳定错误。

#### Scenario: Flex 容器解析

- **WHEN** 容器包含 padding、gap、固定尺寸和 flexGrow 子节点
- **THEN** 系统按主轴可用空间分配尺寸，并按 children 原顺序输出稳定 x/y/width/height

#### Scenario: 缺少测量

- **WHEN** hug 或 baseline 节点缺少所需 measurement
- **THEN** 系统拒绝生成成功 Geometry，不使用模型估算

### Requirement: Geometry 渲染消费

Renderer SHALL 接收固定 viewportId，只消费对应 `resolvedLayouts` 中的 Geometry，并将每个节点渲染为相对父节点的绝对定位。缺少 viewport 或节点 Geometry 时 SHALL 返回稳定错误，不回退到另一套布局语义。

#### Scenario: 成功渲染

- **WHEN** final DesignDocument 包含完整 viewport Geometry
- **THEN** Renderer 为节点追加 position、left、top、width、height 和 boxSizing，并保留业务 props 与视觉 style

#### Scenario: 快照缺失

- **WHEN** 指定 viewport 没有完整 Geometry
- **THEN** Renderer 拒绝渲染并返回可定位错误

### Requirement: 位置编辑回写

位置编辑 SHALL 将目标 Geometry 与原 Geometry 的差值写回 `layoutItem.offset`，随后重新计算全部受影响 viewport。系统 MUST NOT 将手工 Geometry 作为长期布局事实。

#### Scenario: 拖动自动布局节点

- **WHEN** 用户拖动 position=auto 的节点
- **THEN** 系统更新 offset、重新解析 Geometry，并保持该节点原有 Flex 占位
