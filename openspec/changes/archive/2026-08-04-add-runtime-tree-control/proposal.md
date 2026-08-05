## Why

仓库缺少可供编辑器和业务界面复用的运行时 Tree 控件，调用方需要自行处理展开、选择、勾选、搜索、异步加载、拖拽和大数据渲染，导致行为与状态模型分散。需要提供一个参考 Semi Design 使用体验、但符合本仓库函数式 React 与共享 UI 边界的通用 Tree 模块。

## What Changes

- 在 `packages/ui` 新增运行时 Tree 控件及公开类型，以递归 `TreeNodeData[]` 作为稳定输入接口。
- 提供展开、选择和勾选的受控与非受控模式，并明确父子勾选关联、禁用节点和叶节点行为。
- 提供搜索过滤、自动展开匹配路径、仅显示匹配分支和自定义节点匹配能力。
- 提供异步子节点加载及稳定的 loading、loaded 和失败重试行为。
- 提供拖拽落点意图事件，由调用方更新 `treeData`，控件不在内部持久化业务数据。
- 提供节点标签、图标、整行内容和空状态的组合式渲染扩展点。
- 使用现有虚拟列表能力支持大规模展开树，并提供按节点 key 定位滚动的运行时句柄。
- 提供符合 WAI-ARIA Tree 模式的语义、焦点管理和键盘交互。

## Capabilities

### New Capabilities

- `runtime-tree-control`: 定义通用运行时 Tree 的数据接口、受控状态、交互事件、搜索、异步加载、拖拽、虚拟化、渲染扩展和可访问性行为。

### Modified Capabilities

无。

## Impact

- 新增 `packages/ui/src/components/tree.tsx` 及必要的同目录内部实现与公开类型。
- 复用 `packages/ui` 现有的 React、样式工具、图标、输入框和 `react-virtuoso` 依赖，不新增运行时依赖。
- 通过现有 `@repo/ui/components/*` 子路径导出规则提供 `@repo/ui/components/tree`。
