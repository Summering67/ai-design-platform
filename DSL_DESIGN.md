# AI 设计 DSL 设计

> 当前规范（2026-08）：唯一事实源是 `DesignDocument 2.0.0` 树形 JSON，唯一当前 Schema 为
> `packages/design-contract/schema/v2/design-document.schema.json`。本文后续关于 v1 Graph、
> `DesignTreeDocument`、外部 Profile 和 `DesignOperation` 的描述属于历史设计，实施时以
> `openspec/changes/consolidate-design-dsl-source/` 为准。

## 1. 目标与范围

本 DSL 用于承接 AI 直接生成的 UI 结构，并从同一份结构化数据派生出：

- 可在浏览器中预览和编辑的设计稿；
- React、Tailwind CSS 和 Ant Design 代码。

首期使用 DOM/CSS 渲染设计稿，支持拖拽重排、文本修改、颜色修改、Flex 属性调整和 Ant Design 组件替换。

首期不包含多人协作、服务端版本历史、撤销重做、Canvas/SVG 渲染器，以及 DSL 与手写代码的双向同步。

## 2. 核心原则

### 2.1 DSL 是唯一事实来源

规范化后的 `DesignDocument` 2.0 Tree 保存设计数据，是唯一事实来源。设计稿预览、编辑 Graph、依赖和代码均由它派生，不能将 Graph、DOM、JSX、Tailwind 类名或 DOM 测量结果作为主数据。

```text
AI / 导入
  → DesignDocument 2.0 Tree
  → Schema 与语义校验
  → 可丢弃 Graph 投影
  ├─→ DOM 设计稿渲染器
  └─→ React + Tailwind + Ant Design 代码生成器
```

代码生成是单向派生。首期内，人工修改生成后的代码不会反向覆盖 `DesignDocument`。编辑命令只在派生 Graph 副本上应用，成功后重新生成并校验完整 Tree，再原子替换规范文档；`DesignOperation[]` 只是命令边界，不是事实源。

### 2.2 保存布局意图，不保存布局副产物

常规 UI 使用 Flex 布局，节点保存方向、间距、内边距、对齐和尺寸策略，不保存 Flex 子项的计算坐标。`x`、`y`、实际宽高属于渲染器求解后的 `ResolvedLayout`。

绝对定位仅用于浮层、角标、装饰等脱离主布局流的元素。

### 2.3 设计模型与渲染目标解耦

DSL 中不出现 `div`、`className`、CSS 字符串或 Canvas 绘制指令。DOM/CSS、Canvas/SVG 和代码生成均为可替换的适配器。

### 2.4 跨语言契约优先

Go 与 TypeScript 不直接共享类型包。版本化 JSON Schema 是 DSL 的唯一跨语言契约；前端和后端分别基于它实现解析、校验与领域能力。

```text
packages/design-contract/schema/v2/design-document.schema.json
  ├─→ apps/web 与 packages/design-dsl：TypeScript 类型、编辑与渲染
  └─→ apps/api/internal/design：Go 解析、校验、迁移与持久化
```

JSON Schema 定义传输和持久化格式；TypeScript、Go struct、DOM 状态和 Ant Design JSX 都是其适配器，不能反向成为 DSL 的事实来源。

### 2.5 借鉴 Penpot 的边界

本设计借鉴 Penpot 将页面节点规范化为稳定 ID 对象表、以有序 child ID 表达层级、并通过统一 change/operation 管线维护双向父子引用的做法；不直接复制其内部字段或渲染模型。

Penpot 的 Shape Proxy 是 Graph 上的动态操作接口，`shapeStructure()` 则是面向 AI 的有损摘要，两者不能用于无损往返。本 DSL 因为需要保存 AI 设计意图，额外定义无损 `DesignTreeDocument`：它只作为 `DesignDocument` Graph 的输入/投影视图，不能绕过 `DesignOperation` 直接覆盖运行时 Graph。虚拟 Root 使用 `parentId: null`，而不是依赖自指哨兵，从契约层直接消除 Root 父链循环歧义。

## 3. 领域模型

| 术语                  | 含义                                                    |
| --------------------- | ------------------------------------------------------- |
| `DesignDocument`      | 一份完整、可持久化的设计文档。                          |
| `DesignTreeDocument`  | 面向 AI 输入和阅读的嵌套树视图，不直接持久化或修改。    |
| `DesignTreeNode`      | 树视图中的嵌套设计节点。                                |
| `StoredNode`          | `DesignDocument` Graph 中持久化的规范化节点。           |
| `RootNode`            | 每页不可编辑的虚拟根节点，`parentId` 固定为 `null`。    |
| `layout`              | 容器如何排列子节点的布局意图。                          |
| `layoutItem`          | 节点作为父布局子项时的尺寸和定位规则。                  |
| `ComponentDefinition` | 可复用组件的框架无关视觉与属性定义。                    |
| `component-instance`  | 对组件定义的实例引用，可拥有变体和覆盖值。              |
| `DesignOperation`     | 一次用户或 AI 对设计稿的增量编辑。                      |
| `ResolvedLayout`      | 渲染器根据 DSL 计算出的几何结果，不作为设计意图持久化。 |
| `EditorState`         | 选中、悬停、拖拽中等编辑器临时状态，不持久化。          |
| `ComponentBinding`    | 框架无关组件标识到 Ant Design 代码的映射。              |

## 4. 文档结构

```ts
type NodeId = string;

interface DesignDocumentMeta {
  version: "1.0.0";
  id: string;
  name: string;
  assets: Record<string, Asset>;
  tokens: DesignTokens;
  componentDefinitions: Record<string, ComponentDefinition>;
  componentBindings: Record<string, ComponentBinding>;
}

/** 唯一持久化事实来源：规范化节点 Graph。 */
interface DesignDocument extends DesignDocumentMeta {
  pages: DesignPage[];
}

interface DesignPage {
  id: NodeId;
  name: string;
  rootId: NodeId;
  nodes: Record<NodeId, StoredNode>;
}

/** 面向 AI 的无损嵌套视图，不直接持久化。 */
interface DesignTreeDocument extends DesignDocumentMeta {
  pages: DesignTreePage[];
}

interface DesignTreePage {
  id: NodeId;
  name: string;
  /** 规范化时创建 RootNode，反向派生时用于保持根 ID 稳定。 */
  rootId: NodeId;
  children: DesignTreeNode[];
}

type DesignTreeNode =
  | DesignTreeFrameNode
  | TextNode
  | ImageNode
  | IconNode
  | ComponentInstanceNode;

type LeafNode = TextNode | ImageNode | IconNode | ComponentInstanceNode;

interface NodeBase {
  id: NodeId;
  name?: string;
  visible?: boolean;
  style?: StyleSpec;
  layoutItem?: LayoutItemSpec;
  semantic?: SemanticSpec;
}

interface FrameNode extends NodeBase {
  kind: "frame";
  layout?: FlexLayoutSpec | AbsoluteLayoutSpec;
}

interface DesignTreeFrameNode extends FrameNode {
  children: DesignTreeNode[];
}

interface TextNode extends NodeBase {
  kind: "text";
  text: string;
  typography: TypographySpec;
}

interface ImageNode extends NodeBase {
  kind: "image";
  assetId: string;
  alt?: string;
}

interface IconNode extends NodeBase {
  kind: "icon";
  name: string;
}

interface ComponentInstanceNode extends NodeBase {
  kind: "component-instance";
  componentRef: string;
  variant?: Record<string, string>;
  overrides?: Record<string, unknown>;
}

interface RootNode {
  id: NodeId;
  kind: "root";
  parentId: null;
  childIds: NodeId[];
}

type StoredFrameNode = FrameNode & {
  parentId: NodeId;
  childIds: NodeId[];
};

type StoredLeafNode = LeafNode & {
  parentId: NodeId;
  childIds?: never;
};

type StoredNode = RootNode | StoredFrameNode | StoredLeafNode;

interface Asset {
  id: string;
  hash: string;
  mimeType: string;
  intrinsicSize?: { width: number; height: number };
  source: string;
}
```

`DesignPage.nodes` 是唯一的持久化节点图；`childIds` 的顺序同时表示图层、Flex 排列和代码输出顺序。AI 首次输入和完整人工查看使用 `DesignTreeDocument`，由内核在 Tree 与 Graph 之间转换，不能直接写入 `nodes` 表。后续 AI 编辑只提交 `DesignOperation[]`，避免用整棵 Tree 覆盖人工修改后的 Graph。

每页的 `rootId` 指向不可编辑的 `RootNode`，所有顶层节点均挂在该根下。Root 不参与渲染，没有样式、布局或语义属性，并以 `parentId: null` 明确终止父链；普通节点的 `parentId` 必须指向 Root 或 Frame。节点 `id` 必须稳定且在页面内唯一，用于选择、拖拽、编辑、代码节点追踪，以及后续的撤销、协作和增量渲染。

## 5. 跨语言共享与版本策略

### 5.1 契约位置

```text
packages/design-contract/
├── schema/
│   └── v1/
│       ├── design-document.schema.json
│       ├── design-tree-document.schema.json
│       └── design-operation.schema.json
└── fixtures/
    └── v1/
        ├── login-page.document.json
        └── login-page.tree.json

packages/design-dsl/                 # TypeScript 编辑内核
apps/api/internal/design/             # Go 解析、校验、迁移、持久化
```

`design-document.schema.json` 定义唯一持久化 Graph；`design-tree-document.schema.json` 定义 AI 首次输入和完整树视图；`design-operation.schema.json` 定义后续唯一写入协议。三者属于同一版本化 DSL 契约，但职责不能混用。`packages/design-contract` 只包含语言无关的 JSON Schema、固定样例和迁移说明，不包含 React、Go、Tailwind 或 Ant Design 代码。

### 5.2 两端职责

| 位置                       | 职责                                                                                                |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| `packages/design-dsl`      | 从 Schema 同步 TypeScript 类型；维护 Tree ↔ Graph 转换、编辑图、`DesignOperation`、DOM 渲染输入与前端错误展示。 |
| `apps/api/internal/design` | 解析 JSON，检查文档大小、`version`、Schema 和业务权限；执行迁移并只持久化规范化后的 `DesignDocument` Graph。   |
| `packages/design-contract` | 提供 Tree、Graph、Operation 的结构、枚举、必填项与版本契约；使用往返 fixture 验证前后端兼容性。                |

后端不负责 DOM 布局、Ant Design 预览或 JSX 生成；前端临时的选择、拖拽、缩放和悬停状态也不得写入 DSL。

### 5.3 兼容性

文档以 SemVer `version` 标识格式版本，例如 `"1.0.0"`：

- 导入版本高于当前支持版本，或主版本不兼容时，拒绝或要求显式确认；
- 较低的次版本可以迁移后导入，并向调用方返回警告；
- 每次改变 JSON 结构都必须新增或更新 Schema、Go 校验、TypeScript 类型和跨端 fixture；
- 数据库存储原始版本和迁移后的当前文档，保证迁移可审计且可重试。

### 5.4 Zod 的后续使用

首期不以 Zod 定义 DSL。后期若属性面板或 AI 输出需要前端即时校验，可由 JSON Schema 生成或同步 Zod schema。Zod 仅是 React 侧 adapter，不能维护为第二份独立契约。

## 6. 布局模型

### 5.1 Flex 容器

```ts
interface FlexLayoutSpec {
  mode: "flex";
  direction: "row" | "column";
  justify?: "start" | "center" | "end" | "between";
  align?: "start" | "center" | "end" | "stretch";
  gap?: number;
  padding?: Insets;
  wrap?: boolean;
}

/** 节点自身在父布局中的尺寸和定位意图。 */
interface LayoutItemSpec {
  width?: Sizing;
  height?: Sizing;
  grow?: number;
  shrink?: number;
  position?: "flow" | "absolute";
  inset?: Partial<{ top: number; right: number; bottom: number; left: number }>;
}

type Sizing =
  | { mode: "fixed"; value: number }
  | { mode: "fill" }
  | { mode: "hug" }
  | { mode: "minmax"; min: number; max?: number };
```

数值使用逻辑像素，不能保存 `"16px"` 等 CSS 字符串。DOM 渲染器将布局直接映射到 CSS Flex；未来 Canvas/SVG 渲染器通过统一的布局求解器得到相同的结构和尺寸策略。

### 5.2 绝对定位容器

```ts
interface AbsoluteLayoutSpec {
  mode: "absolute";
}
```

`layout` 只描述容器如何排列 children，不保存容器自身的宽高；节点自身的尺寸统一由 `layoutItem.width` 和 `layoutItem.height` 表达，包括挂在虚拟 Root 下的顶层 Frame，从而避免 `layout.width` 与 `layoutItem.width` 两个事实来源。

虚拟 Root 使用绝对布局语义。Absolute 容器的直接 child 必须使用 `layoutItem.position: "absolute"` 和足以确定位置的 `inset`；Flex 容器的 child 默认使用 `position: "flow"`，只有显式设置为 `"absolute"` 时才脱离主轴排布。规范化器必须拒绝与父布局不匹配的定位组合。

## 7. 样式、语义与设计令牌

样式必须是结构化数据或令牌引用，禁止存入 CSS 片段。

```ts
interface SemanticSpec {
  role?:
    | "page"
    | "header"
    | "navigation"
    | "main"
    | "section"
    | "form"
    | "list";
  content?: "heading" | "paragraph" | "label" | "action";
}

interface StyleSpec {
  background?: ColorValue;
  border?: BorderSpec;
  radius?: number | TokenRef;
  shadow?: ShadowSpec | TokenRef;
  opacity?: number;
}
```

令牌集中保存在 `DesignDocument.tokens`。代码生成器将令牌输出为 CSS 变量、Tailwind 主题值或 Ant Design 主题配置，避免在每个节点中重复色值、圆角和字号。

## 8. Ant Design 组件体系

DSL 同时允许原子节点与组件实例：

- 原子节点保证任何 AI 生成的界面都能表达和编辑；
- `component-instance` 优先映射为 Ant Design 组件，以得到可维护的业务代码。

```ts
interface ComponentDefinition {
  id: string;
  propsSchema: Record<string, PropSpec>;
  appearance: DesignTreeNode;
}

interface ComponentBinding {
  componentRef: string;
  target: "react-tailwind-antd";
  codeBinding: {
    importFrom: "antd";
    exportName: string;
  };
}
```

组件标识是框架无关的，例如 `ui.button`。`ComponentBinding` 才将其映射到 Ant Design；`appearance` 则是框架无关视觉描述。未来 Canvas/SVG 渲染器即使不运行 Ant Design，也可以通过该描述显示组件的默认外观。

示例：

```ts
{
  id: "submit",
  kind: "component-instance",
  componentRef: "ui.button",
  variant: { type: "primary" },
  overrides: { children: "登录" },
  layoutItem: { width: { mode: "fill" } }
}
```

代码生成器可将其转换为：

```tsx
<Button type="primary" className="w-full">
  登录
</Button>
```

## 9. 编辑模型

设计稿编辑器不能直接修改 DOM；它应将用户动作转换为 `DesignOperation` 并应用到文档。

```ts
type PropertyPatch<T> = {
  [K in keyof T]-?:
    | { property: K; action: "set"; value: Exclude<T[K], undefined> }
    | { property: K; action: "unset" };
}[keyof T];

type DesignOperation =
  | {
      type: "insert-subtree";
      pageId: NodeId;
      parentId: NodeId;
      index: number;
      subtree: DesignTreeNode;
    }
  | {
      type: "move-node";
      pageId: NodeId;
      nodeId: NodeId;
      parentId: NodeId;
      index: number;
      expectedParentId?: NodeId;
    }
  | {
      type: "remove-node";
      pageId: NodeId;
      nodeId: NodeId;
      expectedParentId?: NodeId;
    }
  | { type: "set-text"; pageId: NodeId; nodeId: NodeId; text: string }
  | {
      type: "patch-style";
      pageId: NodeId;
      nodeId: NodeId;
      patches: PropertyPatch<StyleSpec>[];
    }
  | {
      type: "set-layout";
      pageId: NodeId;
      nodeId: NodeId;
      layout: FlexLayoutSpec | AbsoluteLayoutSpec | null;
    }
  | {
      type: "set-layout-item";
      pageId: NodeId;
      nodeId: NodeId;
      layoutItem: LayoutItemSpec | null;
    }
  | {
      type: "replace-component";
      pageId: NodeId;
      nodeId: NodeId;
      componentRef: string;
    };
```

操作处理器是 DSL 的唯一写入口。它必须先校验全部操作、在副本上应用变更、成功后一次性提交；任何一步失败均不得留下半更新文档。`insert-subtree` 明确接收嵌套树并在一次事务中规范化为多个 `StoredNode`；节点 ID 冲突、重复或非法引用时整次操作失败。

`set-layout` 和 `set-layout-item` 使用完整替换语义，`null` 明确表示删除；`patch-style` 的每个字段通过 `set` 或 `unset` 区分“设置值”“删除值”和“未涉及该字段”，不能使用 JSON 中不存在的 `undefined` 暗示删除。首期可只在客户端应用这些操作。后续可以在保持核心节点 Graph 稳定的前提下扩展操作信封、版本、冲突与合并协议，以支持撤销重做、历史或协作；不承诺 `DesignOperation` Schema 永远无需演进。

## 10. 规范化、校验与往返

AI 首次生成可读的嵌套 `DesignTreeDocument`。系统先校验 Tree，再将其规范化为唯一持久化的 `DesignDocument` Graph；渲染器、代码生成器和 Operation handler 只消费 Graph。

```ts
interface ContractWarning {
  code: string;
  path: string;
  message: string;
}

interface NormalizeResult {
  document: DesignDocument;
  warnings: ContractWarning[];
}

interface DenormalizeResult {
  tree: DesignTreeDocument;
  warnings: ContractWarning[];
}

interface DesignNormalizer {
  normalize(tree: DesignTreeDocument): NormalizeResult;
  denormalize(document: DesignDocument): DenormalizeResult;
}
```

### 10.1 Tree → Graph

规范化必须按以下顺序执行：

1. **Tree Schema 校验**：节点类型、属性值、令牌、资源、组件引用和 `version` 合法。
2. **Tree 结构校验**：所有 `rootId` 和节点 `id` 在页面内唯一，不存在嵌套重复 ID 或非法 child 类型。
3. **布局校验**：仅 Frame 具有 `layout`；Flex child 默认处于 flow；Absolute parent 的 child 具有合法 absolute 定位；尺寸策略符合父布局。
4. **组件校验**：实例引用的组件定义、绑定及覆盖属性符合定义。
5. **规范化**：为每页创建 `parentId: null` 的 `RootNode`；递归写入普通节点；将 `children` 转换成有序 `childIds`；为普通节点写入唯一 `parentId`。
6. **Graph 校验**：Root 存在且唯一；普通节点可从 Root 到达；`parentId` 与 `childIds` 双向一致；不存在循环、孤儿、重复 child、空引用和非法子节点。

规范化是结构转换，不得静默删除、合并或重命名已有节点，也不得重新分配合法 ID。结构优化如有需要，必须作为首次导入前的显式可选步骤，或作为返回 `idRemap` 的独立 Operation；后续编辑期间默认禁止自动合并容器，以保持节点身份稳定。

### 10.2 Graph → Tree

反向派生必须从每页 `rootId` 开始，按照 `childIds` 顺序递归生成 `DesignTreeNode.children`。Root 本身不出现在 `children` 中，但其 ID 保留在 `DesignTreePage.rootId`，确保再次规范化时根身份不变。

反向派生是完整设计意图的无损视图，不等同于为了节省 AI 上下文而生成的摘要。若需要有损摘要，应定义独立的 `DesignSummaryTree`，且禁止将其传给 `normalize()` 或用于覆盖 `DesignDocument`。

遇到缺失 parent、缺失 child、循环、孤儿或非法节点时，`denormalize()` 必须失败并返回可定位错误，不能静默跳过损坏节点。

### 10.3 往返不变量

Tree 与 Graph 必须满足以下可测试契约：

```ts
const graph = normalize(tree).document;
const restoredTree = denormalize(graph).tree;
const rebuiltGraph = normalize(restoredTree).document;

assertDeepEqual(
  canonicalize(rebuiltGraph),
  canonicalize(graph),
);
```

`canonicalize()` 只能规范化 Record 键顺序、可省略默认值等不影响语义的表示差异，不能改变节点 ID、父子关系或设计字段。往返必须保证：

- 保留 document、page、root 和 node ID；
- 保留父子关系与 `childIds` 顺序；
- 保留所有样式、布局、文本、资源、语义、组件和令牌引用；
- 不引入 `ResolvedLayout`、DOM 测量值或 `EditorState`；
- 不产生、删除、合并或移动节点；
- 对同一合法输入产生确定性输出。

契约 fixture 必须同时保存 Tree 与期望 Graph，并在 TypeScript 和 Go 两端执行 `Tree → Graph`、`Graph → Tree → Graph` 测试。

`ResolvedLayout` 与 `EditorState` 不参与持久化 Schema 或 Tree ↔ Graph 往返。前者可从 DOM 布局结果重新计算并接受运行时有限数值校验；后者只属于当前编辑会话。

## 11. 渲染与生成接口

```ts
interface DesignRenderer {
  render(
    document: DesignDocument,
    target: "dom" | "canvas" | "svg",
  ): RenderResult;
}

interface CodeGenerator {
  generate(
    document: DesignDocument,
    target: "react-tailwind-antd",
  ): GeneratedCode;
}
```

首期只实现 `dom` 与 `react-tailwind-antd`。后续新增 Canvas/SVG 适配器时，不修改 `DesignDocument`、`DesignOperation` 或代码生成器接口。

首期以浏览器 CSS Flex 为布局真相，只预留 `LayoutResolver` interface；不提前实现自研 Flex 求解器。Canvas/SVG 加入时，再以相同的布局意图接入专用 resolver。

## 12. 跨渲染器兼容性

DOM 与 Canvas 的文本排版、字体加载、阴影和复杂 Ant Design 组件不能保证像素级一致。跨渲染器验收目标应为：

- 节点层级、可见性和顺序一致；
- Flex 布局方向、尺寸策略和主要间距一致；
- 组件语义和变体一致；
- 色彩、圆角、边框和排版令牌一致。

不承诺不同渲染器在所有字体与浏览器环境中获得完全相同的像素结果。

## 13. 首期验收边界

- AI 能生成合法的 Flex UI `DesignTreeDocument`，并规范化为 `DesignDocument` Graph。
- `DesignDocument` 可在 DOM/CSS 画布中渲染和编辑。
- 编辑结果通过 `DesignOperation` 回写 DSL，并重新渲染。
- Tree → Graph 与 Graph → Tree → Graph 往返 fixture 在 TypeScript 和 Go 两端结果一致。
- Ant Design 的 Button、Input、Card、Form、Menu 等组件可作为实例生成。
- DSL 可生成 React、Tailwind CSS 和 Ant Design 代码。
- 不实现 Canvas/SVG、协作、历史、撤销重做或代码反向同步。
