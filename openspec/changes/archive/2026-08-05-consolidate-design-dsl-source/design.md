## Context

当前仓库把设计数据分散在 v1 Graph Schema、Tree Schema、Operation Schema、Profile Schema、GenerationContract Schema、手写 TypeScript 类型和 Go 校验中。它们没有生成关系，已经出现 Schema 强制旧字段、TypeScript 将其标为可选或废弃、Go 又执行另一组必填规则的漂移。

semi-d2c 的核心经验是使用一棵包含 `tag`、`style`、`props`、`children` 等信息的 `TreeNode` 作为 D2C 中间产物，再由插件派生 CSS、模板和依赖。该模型适合作为本次收敛的结构参考，但原始类型包含 `any`、函数、运行时标记和可被生成过程修改的字段，不能原样作为可持久化跨语言契约。

本变更跨越契约包、TypeScript 编辑内核、Go 接收边界和 UI 渲染适配器。现有 v1 数据与新模型含义不兼容，因此规范版本升级为 `2.0.0`。

## Goals / Non-Goals

**Goals:**

- 只保留一份当前权威 Schema：`packages/design-contract/schema/v2/design-document.schema.json`。
- 只持久化一份自包含的树形 `DesignDocument` JSON，并保证相同 JSON 在无外部可变配置时具有稳定语义。
- 参考 semi-d2c 的 TreeNode 字段和转换管线，支持 HTML 元素、文本、图片与组件节点。
- 由 Schema 单向生成 TypeScript 契约类型，并让 Go/API 使用同一 Schema 的派生校验结果。
- 将 Graph、操作应用、依赖、预览和代码明确限制为可重建投影或派生产物。
- 为现有 v1 Graph/Tree/Profile 数据提供显式、确定且失败关闭的迁移。

**Non-Goals:**

- 不复制 semi-d2c 的插件 API、Figma 运行时、CodeSandbox 或框架专用生成器。
- 不在本变更中实现多人协作、事件溯源、撤销历史或生成代码反向同步。
- 不允许任意 CSS 属性、任意节点扩展字段、函数值或组件 props 中隐藏的子节点。
- 不承诺所有历史 v1 数据都能无损迁移；无法确定语义的数据必须返回结构化错误。

## Decisions

### 使用自包含的 v2 树形文档作为唯一持久化状态

规范文档固定包含：

```json
{
  "$schema": "https://ai-design-platform.dev/schema/v2/design-document.schema.json",
  "version": "2.0.0",
  "id": "login-page",
  "name": "登录页",
  "designSystem": {
    "id": "team-default",
    "version": "1.0.0",
    "digest": "sha256:...",
    "tokens": {},
    "components": {}
  },
  "assets": {},
  "root": {
    "id": "root",
    "kind": "element",
    "name": "登录页",
    "tag": "div",
    "style": {},
    "props": {},
    "children": []
  }
}
```

`designSystem` 保存生成和渲染所需的已解析不可变快照，`id + version + digest` 仅用于来源追踪和完整性校验。运行时不得再通过同一引用加载可变 Profile 来补充或覆盖文档语义。

选择 Tree 而非持久化 Graph，是因为它与 semi-d2c 的转换管线、AI 结构化输出和人类检查方式一致，并天然表达唯一父子所有权和顺序。Graph 仍可作为编辑器内存索引提高查找和操作效率，但必须能从 Tree 重建且不独立保存。

备选方案是继续持久化 Graph，并把 Tree 作为输入。该方案保留了两个完整文档形态及往返一致性负担，不符合本次唯一事实源目标。

### 采用严格且完全可序列化的 TreeNode 子集

所有节点必须具有全局唯一非空 `id`、`kind`、`name`、`tag`、`style`、`props` 和 `children`。`kind` 取值为 `element`、`text`、`image` 或 `component`：

- `text` 必须包含 `text`；
- `image` 必须包含指向文档级 `assets` 的 `assetId`，可包含 `alt`；
- `component` 可包含 `packageName` 和 `defaultModule`；
- 内容组合只能通过 `children` 表达，`props` 内不得嵌套 DesignNode；
- `style` 使用 semi-d2c 一致的 camelCase Web CSS 名称，并由 Schema 显式枚举首期允许的属性；数值尺寸统一表示逻辑像素；
- `props` 仅允许 JSON 的 null、boolean、number、string、array 和普通 object，不允许非有限数字或特殊运行时值。

Schema 对文档和节点均设置 `additionalProperties: false`。全局 ID 唯一、Asset 引用、组件包信息和设计系统摘要一致性等无法仅由 JSON Schema 完整表达的规则，作为同一契约的语义约束实现于生成的校验器和共享 fixture 中，不得扩展文档格式。

semi-d2c 的 `dependencies` 可由 `tag + packageName + defaultModule` 收集，`className` 可由样式生成，`toTemplate` 是函数，`__semi_d2c_node__` 是运行时标记，因此均不持久化。原始设计工具节点类型若需审计，只能放入 Schema 明确定义的可选 `source` 对象，不能使用开放扩展字段。

### Schema 是唯一契约定义，语言类型与校验器均为派生物

v2 只公开 `design-document.schema.json` 作为当前 DSL 契约。TypeScript 类型必须通过类型级 Schema 推导或确定性生成获得；Go/API 必须加载同一 Schema 执行结构校验，任何生成文件均须标注禁止手工编辑。标准库与现有依赖不具备这两项能力，因此只允许增加直接用于类型派生和 Schema 校验的最小依赖，并由现有检查入口验证派生结果，不新增独立运行或测试命令。

固定 fixture 同时执行 Schema 校验、TypeScript 读取/派生和 Go 接收集成测试。手写代码只负责 JSON Schema 无法表达的语义不变量和领域操作，不能重新声明字段必填性、枚举或对象形状。

备选方案是让 TypeScript 类型成为事实源再生成 Schema。该方案会把 Go、AI 结构化输出和持久化格式绑定到 TypeScript 工具链，因此不采用。

### 所有运行时模型都是从规范 Tree 派生的可丢弃投影

编辑器加载文档时可建立 `{nodes, parentById, childOrder}` Graph 索引。操作命令在隔离副本上应用，成功后必须重新序列化并验证完整 v2 Tree，再原子替换规范文档；操作日志和 Graph 不作为恢复来源。

渲染器、React/Vue 生成器和依赖收集器只读取已验证文档。它们不得把 className、组件默认 props、目标框架 binding、解析后的 URL 或布局测量写回文档。相同输入和相同生成器版本必须产生确定性派生结果。

### v1 仅作为带格式判别的迁移输入

迁移入口先根据结构和版本判别 v1 Graph 或 v1 Tree，不允许仅依赖当前同为 `1.0.0` 的字符串猜测格式。迁移过程解析固定 Profile，生成自包含 `designSystem` 快照，将 Asset、节点、顺序和支持的样式映射到 v2 Tree，最后执行完整 v2 校验。

迁移必须返回原始格式、原始版本、目标版本和警告。遇到缺失 Profile、摘要不匹配、多个父节点、循环、未知节点、无法映射的样式/组件绑定或非 JSON 值时整次失败，不写入部分结果。成功后只持久化 v2 文档；原 v1 payload 由现有备份或审计边界保留，不作为在线读取来源。

## Risks / Trade-offs

- [树结构移动节点时需要更新嵌套对象，随机访问成本高] → 编辑会话建立可丢弃 Graph 索引，并在提交时回写、验证完整 Tree。
- [内嵌设计系统快照增大文档体积] → 快照仅包含生成和渲染实际需要的解析契约；后续可做内容寻址存储优化，但读取语义仍以文档固定摘要对应的不可变内容为准。
- [resolved CSS 比原有布局意图更接近渲染目标] → v2 明确定位为 D2C 中间文档并限制首期 Web CSS 子集；跨目标抽象不是本变更目标。
- [Schema 无法表达全局 ID 唯一等约束] → 使用由同一契约驱动的语义校验器和跨语言共享 fixture，禁止语义校验器另行定义字段形状。
- [现有未归档 OpenSpec 仍描述旧模型] → 本变更实施前标记冲突变更为被取代；完成后按 OpenSpec 流程分别归档，不能让旧任务继续修改 v2 契约。
- [部分 v1 文档无法确定性迁移] → 失败关闭并返回稳定路径和错误码，不使用默认值静默改变设计。

## Migration Plan

1. 新增 v2 单一 Schema、合法/非法 fixture 和只读 v1→v2 迁移 fixture，不切换运行时写入。
2. 从 v2 Schema 生成 TypeScript 类型及 Go 校验派生物，建立生成差异检查和跨语言契约测试。
3. 实现 v2 Tree 校验、Graph 投影、操作提交回写和现有渲染模型派生，保持 UI 对派生接口的调用边界。
4. 实现 v1 Graph/Tree + Profile 到 v2 的迁移器，并用固定 fixture 验证成功与失败路径。
5. 将 API 写入和持久化切换为仅接受 v2；旧数据在读取边界迁移成功后原子写回 v2。
6. 删除或停止公开旧的并列 DSL Schema、手写类型所有权和旧校验入口，更新 `DSL_DESIGN.md` 及冲突 OpenSpec 状态。

回滚时恢复 v1 读取路径和迁移前数据，不尝试把已创建的 v2 文档有损降级为 v1。切换前必须保留迁移输入及版本标记，使回滚不会覆盖原始文档。

## Open Questions

无。首期明确采用 Web D2C 中间文档定位；未来若需要跨 Web/原生目标，应通过新的主版本重新评估样式模型。
