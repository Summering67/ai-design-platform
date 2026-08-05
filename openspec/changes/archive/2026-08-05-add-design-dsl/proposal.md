## Why

当前平台只能生成并展示对话内容，缺少一份能由 AI 生成、被编辑器安全修改、并稳定派生为预览和业务代码的设计数据契约。需要先建立框架无关且跨语言一致的 DSL，才能让后续设计画布、AI 生成和代码导出基于同一事实来源演进。

## What Changes

- 新增版本化 JSON Schema 契约，覆盖可持久化的 `DesignDocument` Graph、面向 AI 的 `DesignTreeDocument` 和增量 `DesignOperation`。
- 新增 TypeScript DSL 内核，实现 Tree/Graph 转换、Graph 不变量校验、原子操作应用和错误结果。
- 新增 Go DSL 适配层，校验和迁移传入文档，并只接受规范化后的 Graph 用于持久化边界。
- 新增跨端固定 fixture 与往返契约测试，确保 TypeScript 与 Go 对 v1 文档的兼容性。
- 新增基于 Graph 的 DOM/CSS 预览输入与 React、Tailwind CSS、Ant Design 代码生成接口；首期支持基础节点及 Button、Input、Card、Form、Menu 组件实例。
- 明确首期不支持 Canvas/SVG、协作、历史、撤销重做和生成代码反向同步。

## Capabilities

### New Capabilities

- `design-dsl-contract`: 定义 v1 设计文档、树视图和操作的跨语言 JSON Schema、版本兼容及固定样例。
- `design-dsl-core`: 提供 TypeScript 与 Go 对 DSL 的校验、规范化、反规范化、操作原子性和持久化边界。
- `design-document-derivation`: 从规范化设计图派生 DOM/CSS 预览输入和 React、Tailwind CSS、Ant Design 代码。

### Modified Capabilities

无。

## Impact

- 新增 `packages/design-contract` 与 `packages/design-dsl` 工作区包，以及各自的公开导出、TypeScript 配置和测试。
- 新增 `apps/api/internal/design` 领域模块，用于 API 接收、版本检查、迁移和持久化前校验；不改变现有认证和项目对话契约。
- 后续设计编辑器与 AI 生成流程将以 DSL 操作协议作为唯一写入口，不能直接修改 DOM、JSX 或节点对象表。
- 预期复用现有 TypeScript、Go、React、Tailwind CSS 与 Ant Design 技术栈；若仓库尚未具备 Ant Design，需要在实施阶段确认并仅为代码生成目标增加所需依赖。
> 该变更的 DSL 事实源设计已被 `consolidate-design-dsl-source` 取代。实施时以 DesignDocument 2.0 树形 JSON 为准，本文仅保留历史背景。
