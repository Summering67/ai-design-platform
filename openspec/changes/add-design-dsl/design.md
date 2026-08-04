## Context

现有仓库包含 Next.js Web 与 Go API，但没有可表达设计意图的共享数据模型。`DSL_DESIGN.md` 已定义首期边界：AI 首次提交嵌套 Tree，内核将其规范化为 Graph；随后 AI 和编辑器只能提交操作数组；预览和代码生成仅消费 Graph。该能力横跨语言无关契约、TypeScript 编辑内核、Go API 校验边界和派生适配器，且 Go 与 TypeScript 不共享类型包。

## Goals / Non-Goals

**Goals:**

- 以 v1 JSON Schema 作为 Tree、Graph 与 Operation 的唯一跨语言传输和持久化契约。
- 保证 Tree → Graph → Tree → Graph 往返保留节点身份、顺序及全部设计意图。
- 保证操作先完整校验、在副本中执行，并以成功后单次提交维持 Graph 一致性。
- 为 DOM/CSS 预览和 React、Tailwind CSS、Ant Design 输出建立仅从 Graph 派生的稳定接口。

**Non-Goals:**

- Canvas/SVG 渲染、自研 Flex 求解器、像素级跨渲染器一致性。
- 协作、版本历史、撤销重做、DSL 与人工修改代码的双向同步。
- 将 DOM、JSX、Tailwind 类名、CSS 文本、DOM 测量值或编辑器临时状态写入 DSL。
- 在本次变更中交付完整产品级画布界面或 AI 提示词编排。

## Decisions

### Schema 优先且按版本隔离契约

在 `packages/design-contract/schema/v1/` 定义 `design-document`、`design-tree-document` 和 `design-operation` 三份 JSON Schema，并在 `fixtures/v1/` 保存登录页 Tree 与其预期 Graph。Schema 用显式判别字段表示节点、布局和操作联合类型，数值保持逻辑像素，样式只允许结构化值或 token 引用。

采用 JSON Schema 而非共享 TypeScript 类型或以 Zod 为事实来源，因为它可被 Go、TypeScript 和未来 AI 输入边界共同验证。Zod 若后续需要，只能是前端适配器；TypeScript、Go struct 与渲染状态都不得反向定义契约。

### Graph 是唯一持久化事实，Tree 仅为投影与输入

每页维护 `rootId` 和 `nodes: Record<NodeId, StoredNode>`；Root 固定为 `parentId: null`，普通节点以 `parentId` 和有序 `childIds` 建立双向关联。规范化器先验证 Tree，再创建或保留 Root，递归写入节点；反规范化从 Root 按 `childIds` 重建 Tree。校验器拒绝重复 ID、循环、孤儿、双向关系不一致、非法父节点和不匹配的定位组合。

选择 Graph 而非持久化嵌套 Tree，是为了用稳定 ID 支撑选中、拖拽、增量更新和后续协作；Tree 仍保留给 AI 的完整可读上下文。Root 不用自指哨兵，避免父链循环歧义。

### 操作是后续唯一写入口，并按文档副本原子应用

`insert-subtree`、移动、删除、文本、样式、布局、布局项和组件替换均携带页面与节点定位信息。处理器在复制的文档上顺序预检并应用全部操作，最终重新校验 Graph；任一失败即返回可定位错误且原文档不变。`set-layout` 和 `set-layout-item` 使用完整替换，`null` 表示删除；`patch-style` 以 `set`/`unset` 区分设置与移除。

选择操作数组而非完整 Tree 覆盖，以避免 AI 覆盖人工局部修改并为历史或协作预留演进空间。首期不实现操作信封、冲突合并或撤销栈。

### 布局保存意图，DOM 是首期布局执行者

Frame 仅持有 Flex 或 absolute 容器布局；子节点通过 `layoutItem` 描述尺寸策略、弹性与定位。Root 使用 absolute 语义，absolute 父节点要求直接子节点显式 absolute 且 inset 足以确定位置；Flex 子节点默认 flow。`ResolvedLayout` 仅是渲染期结果，不入 Schema、Graph 或往返 fixture。

选择浏览器 CSS Flex 而非立即实现 LayoutResolver，是因为首期只需要 DOM 预览；接口预留而不提前实现 Canvas/SVG 求解器，避免把未验证的渲染需求固化进核心。

### 组件定义与目标代码绑定分离

组件实例引用框架无关 `componentRef`，定义提供属性约束和视觉 Tree，绑定将其映射到 `react-tailwind-antd` 的 Ant Design 导出。生成器依据 token、布局和组件绑定生成代码；不支持的节点或绑定必须返回结构化生成错误，不能静默降级为不等价 JSX。

这让 DOM 预览可使用组件默认外观，代码输出可导入 Ant Design，并为未来其他渲染目标保留空间。当前 Web 不依赖 Ant Design；若实际生成代码需要在仓库中直接运行，实施时再确认并最小化新增依赖。

### Go 仅承担 API 侧的版本、Schema、迁移和持久化边界

`apps/api/internal/design` 接收 JSON，限制大小并校验版本、Schema 与调用者权限，然后迁移低次版本并只将当前 `DesignDocument` Graph 交给持久化层。Go 不承担 DOM 布局或 JSX 生成。高于支持版本和不兼容主版本均拒绝；可迁移低次版本返回警告并记录原始版本与规范化结果以支持审计和重试。

这使两端以 fixture 验证行为一致而非共享实现；当前 API 不新增设计文档 HTTP 路由，路由与存储细节留给承接设计编辑器的后续变更。

## Risks / Trade-offs

- [JSON Schema 与两端适配实现发生漂移] → 固定 fixture 在 TypeScript 和 Go 中执行 Schema、Tree→Graph 与 Graph→Tree→Graph 契约测试。
- [Graph 被外部调用方直接修改] → 仅导出只读输入与 `applyOperations` 写入口；渲染和生成器接收已校验 Graph。
- [复杂组件或字体无法跨渲染器像素一致] → 验收限定为层级、顺序、Flex 意图、组件语义和设计令牌一致。
- [操作批次部分失败导致脏状态] → 在副本执行并在最终 Graph 校验通过后才提交。
- [v1 Schema 过早扩大] → 严格限制为 DOM/Flex、基础节点和已列组件，后续能力通过版本化 Schema 演进。

## Migration Plan

1. 新增契约包、v1 Schema 和固定 fixture，不影响现有运行时文档。
2. 接入 TypeScript 内核及其单元测试，再接入 Go 校验与 fixture 测试。
3. 接入 DOM 预览输入和代码生成适配器；仅在具备受控入口时连接未来编辑器或 AI 流程。
4. 发生回滚时移除该新能力的调用入口；已有 v1 JSON 保持原始格式，不改写既有项目或现有对话数据。

## Open Questions

- 设计文档的数据库表、HTTP 路由、AI 输出协议和实际编辑器页面由后续产品变更确定；本变更只提供可接入的领域与适配器边界。
