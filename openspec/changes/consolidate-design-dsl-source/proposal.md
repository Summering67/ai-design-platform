## Why

当前设计 DSL 同时由 JSON Schema、TypeScript 类型、Go 校验、Graph/Tree 契约和 Profile 契约手工描述，已经出现必填字段与所有权漂移。需要参考 semi-d2c 的 TreeNode 转换模型，把可持久化设计收敛为一份可序列化、可跨语言验证且能稳定派生预览与代码的树形 JSON。

## What Changes

- **BREAKING**：将 `DesignDocument` 2.0 树形 JSON 确定为设计数据的唯一事实来源，并仅由 `packages/design-contract/schema/v2/design-document.schema.json` 一份当前 Schema 定义；现有 v1 契约只作为只读迁移输入。
- **BREAKING**：不再将规范化 Graph、`DesignTreeDocument`、`DesignSystemProfile`、`DesignGenerationContract` 或 `DesignOperation[]` 作为可持久化 DSL 的并列事实来源。
- 参考 semi-d2c `TreeNode` 保留稳定的 `id`、`name`、`tag`、`packageName`、`defaultModule`、`style`、`props`、`text` 和 `children`，新增严格的 `kind` 判别字段及文档级 Asset 引用。
- 排除函数、任意扩展字段、运行时标记、生成后的 `className` 和可推导依赖；所有节点属性必须是合法 JSON 值。
- 将编辑器 Graph、父子索引、依赖/imports、DOM 预览、React/Vue 代码和其他目标模型定义为从规范 JSON 单向派生的投影或产物。
- 把生成时所用的已解析设计系统快照嵌入规范文档，避免外部可变 Profile 与文档共同决定同一份设计的语义。
- 提供现有 v1 Graph/Tree/Profile 数据到新规范文档的显式迁移边界，并拒绝无法无损或确定性迁移的数据。
- TypeScript 类型必须由规范 Schema 生成；Go 和其他语言边界直接使用同一 Schema 校验，不再手工维护另一份字段契约。

## Capabilities

### New Capabilities

- `canonical-design-document`: 定义参考 semi-d2c TreeNode 的唯一树形 DesignDocument JSON、字段约束、内嵌设计系统快照、Asset 引用、版本及跨语言契约规则。
- `design-document-projections`: 定义 Graph 索引、操作应用、依赖收集、预览与代码生成只能从规范文档派生，且不得反向成为事实来源。
- `design-document-migration`: 定义现有 Graph、Tree 和 Profile 分离模型向唯一规范 JSON 的确定性迁移、失败语义和兼容边界。

### Modified Capabilities

无。当前主规格尚未包含设计 DSL；本变更将在实施时取代未归档 `add-design-dsl` 与 `complete-preview-data-model` 中冲突的 DSL 事实源约定。

## Impact

- 影响 `packages/design-contract` 的 Schema、fixture、迁移说明和公开导出。
- 影响 `packages/design-dsl` 的类型来源、Tree/Graph 转换、操作应用、Profile 校验和派生模型。
- 影响 `apps/api/internal/design` 的文档接收、Schema 校验、迁移与持久化边界。
- 影响 `packages/ui` 的设计渲染输入适配，但不要求组件直接读取持久化 JSON。
- 影响现有 DSL fixture、单元测试、集成测试、`DSL_DESIGN.md` 以及两个未归档 OpenSpec 变更的契约描述。
- 标准库与现有依赖无法直接从 JSON Schema 派生 TypeScript 类型或在 Go 中执行完整 JSON Schema 校验；实施时仅允许新增这两项能力实际需要的最小依赖，不引入其他基础设施。
