## ADDED Requirements

### Requirement: 版本化的跨语言 DSL 契约
系统 SHALL 在 `packages/design-contract/schema/v1/` 提供 `DesignDocument` Graph、`DesignTreeDocument` 和 `DesignOperation` 的 JSON Schema，并将 JSON Schema 作为 Go、TypeScript、AI 输入和持久化格式的唯一跨语言契约。Schema MUST 使用 `version` 表示 SemVer 格式版本，且 MUST NOT 表达 DOM、JSX、Tailwind 类名、CSS 字符串、Canvas 指令、`ResolvedLayout` 或 `EditorState`。

#### Scenario: 接受 v1 合法 Tree 输入
- **WHEN** 输入包含合法的 `1.0.0` Tree、页面、节点、结构化样式、布局意图、资源、令牌与组件引用
- **THEN** Tree Schema 校验通过，并可交给规范化器处理

#### Scenario: 拒绝不兼容版本或渲染副产物
- **WHEN** 输入的主版本高于当前支持版本，或包含 CSS 字符串、DOM 测量值或编辑器临时状态
- **THEN** 系统以可定位的契约错误拒绝该输入，且不产生可持久化文档

### Requirement: 固定跨端契约样例
系统 SHALL 在 `packages/design-contract/fixtures/v1/` 保存至少一份合法 Tree 和其预期 Graph，并要求 TypeScript 和 Go 对相同 fixture 执行契约测试。

#### Scenario: 两端读取同一 fixture
- **WHEN** TypeScript 内核和 Go 适配层加载同一 v1 Tree 与 Graph fixture
- **THEN** 两端均能验证其格式，并得到与 fixture 一致的规范化图结构

### Requirement: 兼容性与迁移边界
系统 SHALL 拒绝高于支持版本或主版本不兼容的文档；对于支持迁移的较低次版本，系统 SHALL 迁移到当前版本并返回警告。持久化边界 SHALL 保存原始版本和当前规范化 Graph，以支持审计与可重试迁移。

#### Scenario: 导入可迁移低次版本
- **WHEN** API 接收一个支持迁移的较低次版本文档
- **THEN** 系统迁移并校验其当前 Graph，返回版本迁移警告，并保留原始版本信息
