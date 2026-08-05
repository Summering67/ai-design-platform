## Context

AI 生成的 DSL 不是自由格式的页面 JSON，而是团队设计系统约束下的设计意图。当前仓库已经有 `DesignDocument` Graph、Tree/Graph 转换和基础 DOM 派生，但还没有表达“某个团队允许哪些 Token、组件、变体、图标、资源和布局能力”的生成前契约。

如果只在 `DesignRenderer` 阶段注入主题或组件库，AI 可能先生成团队不支持的 DSL，直到渲染时才失败；这会造成生成结果不稳定，也无法保证不同团队的页面风格一致。本变更因此同时建立生成前的 `DesignSystemProfile` 和渲染期的目标适配边界。

核心链路为：

```text
DesignSystemProfile
  → DesignGenerationContract / 结构化输出约束
  → DesignTreeDocument
  → Schema 校验 + 固定 Profile 校验 + Tree → Graph 规范化
  → DesignDocument
  → DesignRenderModel
  → DesignRenderer + DesignRenderAdapter
```

## Goals / Non-Goals

**Goals:**

- 定义不可变版本化 `DesignSystemProfile`，描述团队 Token、typography、组件、变体、布局能力、图标和资源策略。
- 让 AI 生成前、服务端接收后和 Tree → Graph 规范化都使用同一 Profile 约束。
- 补全 `DesignRenderModel` 的文本、图片、图标、组件属性、稳定 ID 和顺序。
- 定义只执行已约束 DSL 的 `DesignRenderAdapter`，默认提供 CSS/Ant Design 目标实现。
- 将布局、主题、组件、图标和资源能力隔离在可替换适配器中，不让目标库类型进入 DSL 核心。
- 保证同一份 DSL 在不同团队 Profile 下不会被静默解释成不同语义。

**Non-Goals:**

- 不在本变更中实现具体上游模型调用、提示词服务或完整项目数据接口。
- 不实现 Ant Design 之外的第二个目标适配器；只验证接口可替换。
- 不实现画布编辑、协作、历史、撤销重做或代码双向同步。
- 不允许渲染器临时放宽 Profile 约束或修改 DSL 语义。

## Decisions

### DesignSystemProfile 是生成前的事实约束

`DesignSystemProfile` 是独立于单份设计文档的版本化契约，至少包含：

- `id`、`version`、内容摘要和名称；
- 语义 Token、颜色、间距、圆角、阴影和 typography 令牌；
- 允许的 `componentRef`、组件定义、variant 枚举和 overrides schema；
- Flex/absolute、尺寸策略、断点等布局能力；
- 允许的图标名称和资源来源策略。

AI 生成器接收 Profile 的可读摘要和结构化约束，输出的 Tree 必须引用 Profile 中存在的 Token、组件和能力。服务端在持久化前再次校验，不能信任模型已经遵守约束。

Profile 使用 `id + version + digest` 标识，同一 ID 与版本发布后内容不可变。`DesignDocument` 保存所采用的 Profile 引用，服务端生成前解析一次并在当前请求中固定该内容摘要。这样接收 AI 输出、重新渲染和历史审计都能定位完全相同的团队规范；Profile 升级必须显式迁移，而不是隐式改变旧页面风格。历史版本无法解析或摘要不匹配时失败关闭，不回退到团队当前版本。

备选方案是把所有团队约束复制进每份 DSL，或只依赖渲染器运行时配置。前者导致文档膨胀和版本漂移，后者无法约束 AI 输出，均不采用。

### Profile、Document 与 Adapter 的所有权分离

Profile 是团队 Token、typography、组件语义、variant、命名 slot、overrides schema、布局能力、图标目录和资源策略的唯一事实来源。`DesignDocument` 仅保存 Profile 引用、页面节点、语义引用，以及通过 Profile 资源策略校验的具体 Asset 实例。文档级覆盖只有在 Profile 明确声明对应 override schema 时才合法。

Ant Design export、React/Tailwind binding、CSS 属性、图标包实现和 CDN 地址转换属于 `DesignRenderAdapter`，不得进入 Profile 或 DesignDocument 核心契约。由此避免当前 `componentBindings`、文档 Token 表与 Profile 同时成为事实来源。

### DesignGenerationContract 固定单次生成边界

AI 不直接消费无法稳定裁剪的 Profile 实现对象。服务端从固定摘要的 Profile 确定性派生版本化 `DesignGenerationContract`，其中包含允许的节点和字段、Token 引用、组件、variant、slot、override、图标、资源及布局约束。自然语言摘要只用于帮助模型理解，不能替代结构化约束。

### Profile 校验与 Graph 校验分层

现有 `validateTree`/`validateDocument` 继续负责通用结构不变量：ID、父子关系、Root、循环、资源引用和基础节点类型。新增 Profile 校验负责团队语义约束：未知 Token、未注册组件、非法 variant/slot/override、未允许的布局模式、图标或资源策略。

两层校验都返回 `Result`/`ContractError[]`，Profile 错误包含 Profile ID、版本、内容摘要和 DSL 路径。首次 Tree、后续 `DesignOperation[]`、导入、迁移和 Profile 重绑定都按“Schema → Profile 解析与语义校验 → 原子应用或规范化 → Graph 校验 → 持久化”的顺序执行。只有全部校验通过才产生新的可持久化 Graph。

### RenderModel 与渲染器命名分离

DSL 是事实来源，渲染数据是派生中间模型，公开新模型统一命名为 `DesignRenderModel` 与 `DesignRenderNode`，目标 UI 组件称为 `DesignRenderer`，运行时目标接口称为 `DesignRenderAdapter`，不再新增 `DesignPreview` 或 `DesignPreviewRuntime`。现有 `deriveDomPreview` 函数与 `PreviewNode` 类型作为兼容别名保留，其参数、`Result` 结构和既有公共字段不发生破坏性变化；新调用方使用 `deriveDesignRenderModel`。

### DesignRenderAdapter 只负责目标执行

`DesignRenderAdapter` 聚合以下可替换能力：

- `themeResolver`：把已通过 Profile 校验的语义 Token 和 typography 转为目标样式值；
- `layoutMapper`：把已允许的 Flex/absolute/尺寸意图转为目标布局属性；
- `componentRegistry`：把已注册的 `componentRef` 转为目标组件；默认映射 Ant Design；
- `iconRegistry`：把已允许的图标名称转为目标图标；
- `assetResolver`：把已允许的 Asset 描述转为安全资源地址或占位。

`DesignRenderer` 只依赖这些接口，不直接 import Ant Design、图标包或 CDN 客户端。适配器不得增加 DSL 未声明的语义，也不得把目标库默认值反向写回文档。每个适配器必须声明目标标识、支持的 Profile 范围和能力集合；不兼容时失败，不自动套用默认实现。

### 团队风格由 Profile 决定，适配器执行 Profile

主题值、组件白名单和布局能力由 Profile 决定；适配器只把这些已约束值映射到目标。Token 解析顺序固定为“Profile 锁定值 → Profile 明确允许的文档级 override → 结构化错误”，未知值或未授权的同名覆盖不得静默回退。

这样更换团队风格时，优先替换 Profile；更换渲染目标时，替换 `DesignRenderAdapter`。两者是不同变化轴，不能用一个 UI 组件注册表同时承担生成约束和目标渲染。

## Risks / Trade-offs

- [Profile 与 JSON Schema 可能漂移] → Profile 本身进入版本化 `packages/design-contract`，使用固定 fixture 验证 AI 输入边界、Tree 校验和 TypeScript/Go 兼容性。
- [Profile 版本升级影响旧设计稿] → DesignDocument 持久化 Profile ID/版本/内容摘要，版本发布后不可变；升级必须显式迁移，旧文档继续使用原 Profile。
- [AI 输出绕过 Profile 直接写 Graph] → 所有外部 Tree 和 Operation 写入口都先经过通用校验与 Profile 校验，渲染器不承担补救职责。
- [适配器默认值造成视觉偏差] → 适配器只执行 Profile 已允许的语义；缺失映射返回结构化错误，不静默使用目标库默认样式。
- [多个适配器接口增加运行时配置复杂度] → 统一收敛到 `DesignRenderAdapter`，每个能力提供默认实现，调用方只替换差异部分。
- [目标组件库属性注入风险] → 组件注册表逐组件使用白名单转换，禁止直接展开未知 overrides、事件处理器或任意对象。

## Migration Plan

1. 在 `packages/design-contract` 增加版本化 `DesignSystemProfile` Schema 与团队 fixture。
2. 在 `packages/design-dsl` 增加 Profile 类型、Profile 校验入口和 DesignRenderModel 专属字段；保留 `deriveDomPreview` 兼容入口。
3. 更新 Tree/Graph/Operation 契约，使文档保存 Profile ID/版本/内容摘要，并在所有写入口执行 Profile 校验。
4. 在 `packages/ui` 定义 `DesignRenderAdapter`，实现默认主题、CSS 布局、Ant Design、图标和 Asset 适配器。
5. 实现只依赖适配器的 `DesignRenderer`，只接收携带 Profile 引用与校验凭据的 `DesignRenderModel`，并验证适配器能力兼容性。
6. 使用单元测试和集成测试验证生成约束、Graph 校验、默认渲染和自定义适配器替换。

回滚时可以保留旧文档的通用 Graph 和 `deriveDomPreview` 入口；新增 Profile 引用和渲染适配器只对启用本变更的文档生效。

## Open Questions

- AI 上游是否支持 JSON Schema/结构化输出，需要在接入生成 API 的后续变更中确定。
- Profile 历史版本采用永久保留还是文档级不可变快照，需要在持久化变更中选择；无论采用哪种方式，都必须保证 `id + version + digest` 可重放且不可变。
