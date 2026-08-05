## ADDED Requirements

### Requirement: 版本化团队设计系统 Profile

系统 SHALL 提供独立于单份设计文档的版本化 `DesignSystemProfile`，至少描述语义 Token 与 typography 定义、允许的组件及其 variant axes、合法 variant 组合、命名内容 slot 与 overrides schema、布局能力、图标目录和资源策略。Profile SHALL 具有稳定的 ID、版本和内容摘要；同一 ID 与版本一经发布 MUST 不可变，并可被 AI 生成边界、所有 DSL 写入边界和渲染边界共同解析。

#### Scenario: 读取团队设计系统

- **WHEN** AI 生成器为某个团队开始生成设计 DSL
- **THEN** 生成器获得该团队指定版本的 Profile 摘要和结构化约束，而不是使用未约束的通用组件列表

#### Scenario: 保存设计系统引用

- **WHEN** DesignTreeDocument 被规范化为 DesignDocument
- **THEN** 文档仅保存所采用的 DesignSystemProfile ID、版本与内容摘要，不复制 Profile 中的 Token、组件定义或目标绑定，后续校验和渲染可确定原始团队约束

#### Scenario: 拒绝发生漂移的 Profile

- **WHEN** 文档引用的 Profile ID 与版本可解析，但其内容摘要与文档保存值不一致，或该历史版本无法解析
- **THEN** 系统返回稳定的 Profile 解析错误，不使用团队当前版本、默认 Profile 或同名 Profile 替代

### Requirement: Profile 与文档及适配器的所有权边界

`DesignSystemProfile` SHALL 是团队语义 Token、typography、组件契约、variant、overrides、布局能力、图标目录和资源策略的唯一事实来源。`DesignDocument` SHALL 仅保存 Profile 引用、设计节点、语义引用和通过资源策略校验的具体 Asset 实例；目标框架导出、Ant Design binding、CSS 映射、图标包实现和 CDN 地址转换 MUST 属于 `DesignRenderAdapter`，不得进入 Profile 或 DesignDocument 核心契约。文档级 Token 或组件覆盖 MUST 仅在 Profile 明确声明对应 override schema 时允许。

#### Scenario: 拒绝文档重定义团队语义

- **WHEN** DesignTreeDocument 自行定义同名 Token、typography、组件契约或目标组件 binding，且 Profile 未声明对应覆盖能力
- **THEN** Profile 校验返回结构化错误，不让文档值覆盖团队事实来源

#### Scenario: 更换目标绑定

- **WHEN** 同一份通过 Profile 校验的 DesignDocument 从 Ant Design 适配器切换到另一个目标适配器
- **THEN** 组件的目标 import、CSS 和图标实现可变化，但 DesignDocument 与 Profile 中不出现目标框架专用 binding

### Requirement: AI 生成前约束

系统 SHALL 在 AI 生成 `DesignTreeDocument` 前，从已解析且固定内容摘要的 Profile 确定性派生版本化 `DesignGenerationContract`，将允许的节点类型与字段、Token 引用、组件、variant、命名 slot、overrides、图标、资源策略和布局能力作为结构化生成约束提供给模型。生成约束 SHALL 携带 Profile ID、版本与内容摘要，MUST NOT 由渲染器临时推断，也不得仅依赖自然语言摘要表达可校验规则。

#### Scenario: 生成受限组件

- **WHEN** Profile 只允许 Button、Input 和 Card
- **THEN** AI 生成约束只暴露这些组件及其允许的属性，生成结果不得声明 Profile 未注册的组件引用

#### Scenario: 生成受限布局

- **WHEN** Profile 禁止 absolute 布局或某种尺寸策略
- **THEN** AI 生成约束禁止这些布局字段，不能依赖渲染阶段再拒绝

#### Scenario: 固定一次生成使用的约束

- **WHEN** 团队在 AI 生成进行期间发布新的 Profile 版本
- **THEN** 当前生成请求和生成后校验继续使用请求开始时固定的 Profile 内容摘要，新版本只影响后续明确选择它的请求

### Requirement: 生成后按同一 Profile 校验

系统 MUST 在接收 AI 输出后、Tree → Graph 规范化前，使用生成时相同的 Profile 校验 `DesignTreeDocument`。Profile 校验失败 MUST 返回带 DSL 路径、Profile 版本和稳定错误码的结构化错误，且不得持久化无效文档。

#### Scenario: 拒绝未知 Token

- **WHEN** AI 输出引用 Profile 未定义的语义 Token
- **THEN** 服务端返回结构化 Profile 校验错误，不执行规范化或持久化

#### Scenario: 拒绝非法组件属性

- **WHEN** AI 输出已注册组件但使用不被 Profile props schema 允许的 variant 或 override
- **THEN** 服务端返回可定位错误，不把该 DSL 交给渲染器补救

### Requirement: 所有 DSL 写入口使用同一 Profile 校验

系统 MUST 对首次 Tree、`DesignOperation[]`、导入、迁移和 Profile 重绑定等所有可改变 DesignDocument 的入口执行统一顺序：跨语言 Schema 校验、Profile 引用解析、Profile 语义校验、原子规范化或操作应用、Graph 校验、持久化。任一步失败 MUST 保持原文档不变。Profile 校验 MUST 覆盖新增或修改的 Token 引用、typography、组件、variant、slot、override、图标、资源和布局能力。

#### Scenario: Operation 不能绕过 Profile

- **WHEN** 已持久化文档收到设置未知 Token、启用被禁布局或替换为未注册组件的 DesignOperation 批次
- **THEN** 整批操作返回带 operation 索引和 DSL 路径的稳定 Profile 错误，原 DesignDocument 不变

#### Scenario: Profile 重绑定必须显式迁移

- **WHEN** 调用方希望把文档改为另一个 Profile 或另一个 Profile 版本
- **THEN** 系统将其作为显式迁移执行完整 Profile 校验，禁止仅修改 profileRef 后直接渲染

### Requirement: Profile 与渲染适配解耦

系统 SHALL 将 Profile 作为设计语义与生成约束来源，将 `DesignRenderAdapter` 作为目标渲染实现。替换 Ant Design、图标库、资源 CDN 或 CSS 执行方式 MUST NOT 改变 Profile 对组件、Token 和布局能力的约束。适配器 SHALL 声明目标标识和受支持能力；渲染边界 MUST 在执行前验证适配器与文档 Profile 的兼容性。

#### Scenario: 同一 Profile 更换渲染目标

- **WHEN** 同一份通过 Profile 校验的 DesignDocument 使用不同的 DesignRenderAdapter
- **THEN** 输出目标可以不同，但节点语义、稳定 ID、顺序、组件引用和允许的 Token 保持一致

#### Scenario: 适配器不得放宽约束

- **WHEN** 渲染适配器未实现某个 Profile 允许的组件或 Token
- **THEN** 返回结构化适配错误或受控占位，不得把未支持能力重新解释为其他语义

#### Scenario: 拒绝不兼容的默认适配器

- **WHEN** 调用方未提供适配器，且系统默认适配器未声明支持文档引用的 Profile 或其必需能力
- **THEN** 返回 `adapter_incompatible` 结构化错误，不以默认 Ant Design、普通 DOM 或其他团队 Profile 继续渲染
