## 1. 契约与类型

- [x] 1.1 收紧 LayoutPlan sizing、position、responsive 和语义校验。
- [x] 1.2 为 DesignDocument 增加 resolvedLayouts，移除布局 style 双写与节点级 computedLayout。
- [x] 1.3 同步 TypeScript 类型、导出和 v2 fixtures。

## 2. Auto Layout 输入与算法

- [x] 2.1 扩展 Auto Layout 状态和模型输入，加入布局要求、能力、viewports 和 measurements。
- [x] 2.2 重写 Auto Layout Prompt，固定决策顺序和禁止输出项。
- [x] 2.3 实现函数式 Python Flex 解析器，覆盖主轴、交叉轴、grow/shrink、wrap、hug/fill、absolute、offset、嵌套和多 viewport。
- [x] 2.4 将解析结果写入完整 resolvedLayouts，并实现位置 offset 回写函数。

## 3. Renderer 与交付门禁

- [x] 3.1 修改 v2 Renderer 使用显式 viewportId 和 Geometry absolute style。
- [x] 3.2 增加最终文档 Geometry 完整性与渲染可用性校验。
- [x] 3.3 更新 Workspace 的固定 viewport 选择。

## 4. 测试与规范

- [x] 4.1 增加 Schema、语义门禁和 Flex 黄金测试。
- [x] 4.2 增加 Auto Layout 与 Renderer 集成测试及重复计算确定性测试。
- [x] 4.3 同步主 OpenSpec、AGENTS 约束和相关文档。
- [ ] 4.4 运行 server、design-contract、design-dsl、ui 的相关 lint、类型检查、测试和构建。
