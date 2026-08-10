# design-document-canvas-delivery Specification

## Purpose

定义最终设计文档到工作台画布的交付、门禁与渲染。

## Requirements

### Requirement: 最终设计文档画布交付
系统 SHALL 在 Auto Layout Agent 成功终态将最终 DesignDocument 作为 JSON 交付工作台。Auto Layout Agent MUST 在返回前执行与 Web v2 设计文档渲染器一致的 render model 校验，并确认基础 viewport 所需的布局已经投影为渲染器可消费的合法 style；Web SHALL 使用 v2 设计文档渲染器显示在画布区域。仅通过后端 Schema 但无法派生 render model 的文档不得作为成功结果交付。

v2 设计文档渲染器 SHALL 为默认 GenerationContract 注册的 72 项 Ant Design 基础能力提供渲染映射。`Grid` SHALL 投影为 `Row` 容器，`Message` 与 `Notification` 等命令式能力 MUST 投影为无副作用的静态 `Alert`，`Icon` 与 `Util` SHALL 使用语义容器预览；未知组件仍 MUST 保持可识别的降级标记，不得在画布渲染期间执行外部副作用。

#### Scenario: 成功渲染画布
- **WHEN** Web 收到 completed 事件中的有效 DesignDocument，且该文档已通过 render model 与布局样式门禁
- **THEN** 工作台以该文档替换画布等待状态并递归渲染页面结构、内容和基础布局

#### Scenario: 拒绝不可渲染文档
- **WHEN** 候选最终文档包含渲染器不接受的组件引用、嵌套节点或布局结果
- **THEN** Auto Layout Agent 在 completed 事件前失败，工作台不会收到该文档作为成功结果
