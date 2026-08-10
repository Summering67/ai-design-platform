## Context

`auto_layout.tsx` 提供了容器可用尺寸、固定尺寸、gap、flexGrow 和主轴偏移的最小算法参考。生产链路位于 Python Auto Layout Agent，当前 `apply_layout` 只投影少量 style，Web Renderer 也不会读取完整布局元数据。

## Decisions

### 1. 单一事实来源

`layout`、`layoutItem` 和 `responsive` 是设计事实；`resolvedLayouts` 是固定 viewport 的派生快照。模型不得生成 Geometry。编辑器把拖动差值转换为 `layoutItem.offset` 后重新解析。

### 2. 输入与解析

Auto Layout 接收 InitialUIDocument、筛选后的布局要求、布局能力、固定 viewports 和独立 measurements。模型只看到前四项；measurements 只供确定性计算使用。

解析器按父到子的顺序处理 fixed/hug/fill、margin、padding、gap、grow/shrink/basis、justify/align、wrap、absolute 和 offset，并以 0.001 CSS px 稳定舍入。缺少必要测量或约束冲突直接失败。

### 3. 视口与渲染

每个 contract 声明的 viewport 生成一个完整 Geometry 快照。Renderer 接收 viewportId，只读取对应快照并追加 absolute left/top/width/height 样式；缺失快照不回退到 CSS Flex。

### 4. 兼容边界

本变更直接收紧当前 v2 契约，不保留旧布局 style 双写路径；`auto_layout.tsx` 保持为用户的未跟踪参考文件，不被修改或提交。

## Interfaces

```text
AutoLayoutInput = {
  initialUiDocument,
  layoutRequirements,
  layoutCapabilities,
  viewports: [{ id, width, height }],
  measurements: { [nodeId]: { width, height, baseline? } }
}

resolvedLayouts[viewportId] = {
  viewport,
  nodes: { [nodeId]: { x, y, width, height } }
}
```

## Risks

- 文本和第三方组件没有 measurement 时无法生成 hug/baseline Geometry；系统应返回稳定错误，而不是估算。
- 固定视口快照不支持任意宽度拖拽；后续如需连续响应式，需要另一个前端解析器变更。
- Python Schema 与 TypeScript Renderer 类型需通过契约测试保持同步。
