## Why

当前 `deriveDomPreview` 只输出节点类型、可见性、通用样式与子节点，文本内容、图片资源引用和组件实例属性在派生过程中丢失；共享 UI 也没有把结构化布局映射为 CSS、渲染基础节点或将组件引用映射到 Ant Design 的能力。需要在同一变更中打通完整的“静态 DSL → DOM 设计稿 MVP”。

## What Changes

- 将 `DesignRenderNode` 定义为按 `kind` 判别的联合类型，保留各节点渲染所需的专属字段。
- Text DesignRenderNode 保留 `text` 与 `typography`。
- Image DesignRenderNode 保留 `assetId`、可选 `alt`，并携带文档中已通过 Profile 资源策略校验的资源描述。
- Component Instance DesignRenderNode 保留 `componentRef`、`variant`、命名 slot、`overrides` 和 Profile 组件语义契约；目标框架 binding 不进入文档或渲染节点。
- Frame DesignRenderNode 保留布局、布局项、样式及严格按 `childIds` 派生的有序子节点。
- 所有 DesignRenderNode 保留 DSL 稳定 ID、可见性、名称、样式、布局项和语义信息；Root 仍不进入渲染节点树。
- `deriveDomPreview` 在派生前校验文档，并沿用现有契约对缺失资源、组件定义或组件绑定等无效引用返回带路径的结构化错误。
- 新增以 ID、版本和内容摘要固定的不可变 `DesignSystemProfile`，在 AI 生成 `DesignTreeDocument` 前确定性派生结构化 `DesignGenerationContract`，提供团队 Token、字体、组件、图标、资源和布局能力约束。
- AI 生成、服务端接收、Tree → Graph 规范化、后续 `DesignOperation[]`、导入、迁移和 Profile 重绑定 SHALL 使用同一固定摘要的 `DesignSystemProfile` 校验，避免任何写入口生成无法渲染或不符合团队规范的 DSL。
- `DesignSystemProfile` 作为团队 Token、typography、组件/variant/命名 slot/overrides、布局、图标与资源策略的唯一事实来源；`DesignDocument` 仅保存 Profile 引用、节点语义引用和已校验 Asset，目标框架 ComponentBinding 只属于 `DesignRenderAdapter`。
- 预览数据中的 Token 引用保持原值；渲染器执行已由设计系统约束过的语义 Token，不负责决定可用组件或设计能力。
- 新增纯函数式布局与样式映射，将 Flex、absolute、尺寸策略、间距、内边距、基础视觉样式和文本排版转换为 React CSS 属性。
- 新增递归 DOM 节点渲染器，支持 Frame、Text、Image、Icon 与 Component Instance，并以稳定节点 ID 作为 React key 和可追踪 DOM 标识。
- 新增可注入的 `ComponentRegistry` 接口，并提供默认 Ant Design 注册表，将 Profile 允许的 `ui.button`、`ui.input`、`ui.card`、`ui.form` 和 `ui.menu` 映射到对应组件，受控转换 `variant`、命名 slot 与 `overrides`。
- 新增可注入的 `LayoutMapper` 接口，并提供默认 CSS 布局映射器；渲染器不直接绑定某一种布局实现。
- 新增 `DesignRenderAdapter` 接口，负责将已约束 DSL 映射为目标设计稿；默认实现提供 CSS 布局、Ant Design 组件、图标和资源解析。
- 新增可复用的 `DesignRenderer`，通过 Props 接收绑定 Profile 引用和校验凭据的 `ValidatedDesignRenderModel` 及目标适配器，不接收裸节点数组或独立 Token 表，不读取接口或应用环境。
- 新公共派生模型统一命名为 `DesignRenderModel`/`DesignRenderNode`，保留 `deriveDomPreview`/`PreviewNode` 兼容入口，避免破坏已有 DSL API。

## Capabilities

### New Capabilities

- `design-system-generation-contract`: 定义 AI 生成前的团队设计系统 Profile、组件/Token/布局能力约束、版本和生成后校验边界。
- `design-preview-data-model`: 定义从合法 `DesignDocument` Graph 无损派生静态 DOM 设计稿所需预览数据的字段、顺序、稳定身份和错误行为。
- `design-dom-preview-renderer`: 定义只执行已约束 DSL 的 `DesignRenderAdapter`、默认 CSS/Ant Design 实现和基础节点渲染。

### Modified Capabilities

无。

## Impact

- 修改 `packages/design-dsl/src/types.ts` 中与预览派生共享的领域类型或辅助类型。
- 在 `packages/design-dsl/src/derive.ts` 新增 `DesignRenderModel`/`DesignRenderNode` 与 `deriveDesignRenderModel`，并保持公开 `PreviewNode` 类型与 `deriveDomPreview` 兼容。
- 在 `packages/design-contract` 增加版本化 DesignSystemProfile 契约及固定团队风格 fixture。
- 在 `packages/design-dsl` 增加 Profile 驱动的 Tree/Graph 约束校验入口。
- 更新 `packages/design-dsl/src/derive.test.ts`，覆盖文本、图片、组件、顺序、稳定 ID、Token 保留和结构化错误。
- 在 `packages/ui` 下新增静态设计稿 `DesignRenderer`、`DesignRenderAdapter` 公共接口、默认 CSS/Ant Design 适配器及对应样式和组件测试。
- `packages/ui` 增加对 `@repo/design-dsl` 公开导出的 workspace 依赖；复用当前已加入的 `antd`，不新增其他第三方依赖。
- 设计文档需要保存所用设计系统的 ID/版本/内容摘要，保证重新校验和渲染时使用内容完全一致的团队约束。
- 不在本变更中实现具体上游模型调用，但必须定义其生成输入和服务端校验边界。
