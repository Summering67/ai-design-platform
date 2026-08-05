## ADDED Requirements

### Requirement: 唯一的当前设计文档契约
系统 SHALL 仅将符合 `packages/design-contract/schema/v2/design-document.schema.json` 的 `DesignDocument` 2.0 JSON 作为当前可持久化设计事实源。系统 MUST NOT 将 Graph、Tree 镜像、Profile、GenerationContract、操作日志、渲染模型或生成代码作为可独立恢复同一设计的并列事实源。

#### Scenario: 接受唯一规范文档
- **WHEN** 输入完整满足 v2 Schema 和全部语义不变量
- **THEN** 系统将该树形 JSON 作为唯一可持久化设计状态，并仅从它建立其他运行时模型

#### Scenario: 拒绝并列持久化模型
- **WHEN** 写入请求尝试以 Graph、Profile 引用或渲染模型替代完整 v2 文档
- **THEN** 系统返回稳定契约错误，且不改变已持久化文档

### Requirement: 自包含且版本固定的文档根
`DesignDocument` MUST 包含固定值 `version: "2.0.0"`、稳定非空 `id`、非空 `name`、内嵌 `designSystem`、文档级 `assets` 和唯一 `root`。`designSystem` MUST 包含来源 `id`、版本、内容摘要以及解析后的 Token 和组件契约快照；运行时 MUST NOT 使用外部可变配置覆盖快照语义。

#### Scenario: 离线解析相同设计语义
- **WHEN** 两个消费者仅获得同一份合法 v2 JSON 和相同版本的派生实现
- **THEN** 两者无需加载外部 Profile 即可解析相同的节点、样式、组件契约和 Asset 语义

#### Scenario: 设计系统摘要不一致
- **WHEN** 内嵌设计系统内容与声明摘要不匹配
- **THEN** 语义校验失败并定位到 `designSystem.digest`，文档不得进入持久化或派生阶段

### Requirement: 严格可序列化的设计节点
每个节点 MUST 包含文档内全局唯一的非空 `id`、`kind`、`name`、`tag`、`style`、`props` 和 `children`。`kind` MUST 为 `element`、`text`、`image` 或 `component`；对象 MUST 拒绝 Schema 未声明字段，所有属性值 MUST 是合法 JSON 值，节点组合 MUST 仅通过 `children` 表达。

#### Scenario: 接受 semi-d2c 风格节点
- **WHEN** 节点使用合法的 tag、camelCase style、JSON props 和有序 children，且满足对应 kind 的字段要求
- **THEN** Schema 与语义校验均通过并保留 children 顺序

#### Scenario: 拒绝运行时值与开放扩展
- **WHEN** 节点包含函数语义、非有限数值、`toTemplate`、`__semi_d2c_node__`、生成后的 `className` 或任意未声明字段
- **THEN** 系统以可定位错误拒绝整个文档

#### Scenario: 拒绝 props 中隐藏节点
- **WHEN** 组件把 DesignNode 作为 props 的嵌套对象表达内容组合，而不是使用 children
- **THEN** 语义校验失败且指出对应 props 路径

### Requirement: 节点判别字段约束
`text` 节点 MUST 包含字符串 `text`；`image` 节点 MUST 包含 `assetId` 并引用存在的文档级 Asset；`component` 节点 MUST 使用内嵌设计系统快照允许的 tag、包和 props；其他 kind MUST NOT 携带与自身无关的专用字段。

#### Scenario: 合法文本图片和组件
- **WHEN** 文本具有 text、图片引用有效 Asset、组件满足快照中的包与 props 契约
- **THEN** 文档校验通过并可进入派生阶段

#### Scenario: 拒绝悬空 Asset
- **WHEN** image 节点的 assetId 在文档 assets 中不存在
- **THEN** 语义校验返回包含节点 ID 和 assetId 路径的稳定错误

#### Scenario: 拒绝未注册组件
- **WHEN** component 节点的 tag、packageName 或 props 不符合内嵌组件契约
- **THEN** 系统拒绝文档且不得由渲染器用默认组件补救

### Requirement: 受限的 Web 样式契约
`style` MUST 只允许 v2 Schema 显式列出的 camelCase Web CSS 属性和对应值域；数值尺寸 MUST 表示逻辑像素。系统 MUST NOT 接受 CSS 文本块、选择器、任意自定义属性或依赖浏览器测量才能成为事实的布局结果。

#### Scenario: 接受结构化样式
- **WHEN** 节点使用受支持的 display、position、盒模型、文本、Flex、可见性、变换、阴影或过滤属性及合法值
- **THEN** 样式按 JSON 原值保存并可由派生器确定性转换

#### Scenario: 拒绝 CSS 文本
- **WHEN** style 包含 CSS 声明字符串、选择器或未列入 Schema 的属性
- **THEN** Schema 校验失败并返回具体 style 属性路径

### Requirement: Schema 派生跨语言契约
TypeScript 公共 DSL 类型及 Go/API 字段校验 MUST 从 v2 Schema 确定性派生，派生文件 MUST 标明禁止手工编辑。手写语义校验可以补充全局 ID、引用和摘要等不变量，但 MUST NOT重新定义对象形状、字段必填性或枚举。

#### Scenario: 生成结果无漂移
- **WHEN** 在未修改 v2 Schema 的情况下重新生成语言契约
- **THEN** 生成结果与仓库中的派生文件完全一致

#### Scenario: 跨语言读取同一 fixture
- **WHEN** TypeScript 和 Go/API 读取同一份合法及非法 v2 fixture
- **THEN** 两端对结构合法性给出一致结论，并对语义错误使用相同稳定错误码和 JSON 路径
