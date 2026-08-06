## ADDED Requirements

### Requirement: 受生成契约约束的初始 UI 文档
UI 设计智能体 SHALL 接收已通过校验的 StandardizedPRD 和固定版本的 DesignGenerationContract，并输出符合 v2 `DesignDocument` Schema 的初始 UI 文档。文档 SHALL 使用 `version: "2.0.0"`，表达根图层、稳定节点 ID、嵌套结构、组件引用、内容、基础样式、布局意图、交互状态和响应式意图。

#### Scenario: 从 PRD 生成多页面结构
- **WHEN** 标准 PRD 定义登录页、项目列表页及二者间流程
- **THEN** 初始文档包含对应根图层、可追溯的主要区域和导航关系，并通过 v2 DesignDocument Schema 校验

#### Scenario: 保持固定 Profile 引用
- **WHEN** UI 设计智能体产生初始文档
- **THEN** 文档引用与输入 DesignGenerationContract 完全一致的 Profile ID、版本和摘要

### Requirement: 只使用允许的设计能力
UI 设计智能体 MUST 只使用 DesignGenerationContract 允许的节点类型、Token、组件、variant、slot、override、图标、资源策略和布局能力，不得声明目标框架绑定、CSS 字符串、任意事件处理器或未注册组件。

#### Scenario: 请求未注册组件
- **WHEN** PRD 提到日期选择，但生成契约未提供日期组件
- **THEN** 智能体使用契约允许的可表达组合或返回能力不足问题，不得虚构组件引用

#### Scenario: 禁止目标框架属性
- **WHEN** 模型尝试输出 Ant Design 属性、React 组件名或 Tailwind class
- **THEN** 输出门禁拒绝这些字段，不让目标框架实现进入 v2 DesignDocument

### Requirement: PRD 到 UI 的覆盖可追溯
初始 UI 文档 SHALL 覆盖标准 PRD 中所有非阻断页面、关键用户流程、必要状态和明确内容约束。无法表达的需求 MUST 进入结构化生成问题列表，不得静默遗漏。

#### Scenario: 覆盖加载与错误状态
- **WHEN** PRD 要求列表具有加载、空、成功和错误状态
- **THEN** 初始 UI 文档表达这些状态或返回无法表达的结构化问题

### Requirement: 初始文档确定性门禁
模型输出后，系统 MUST 执行 v2 DesignDocument Schema、Profile 引用、节点 ID、父子层级、资源引用和生成契约能力校验。失败结果不得进入规范校验子图，且只允许一次带最小错误上下文的修复重试。

#### Scenario: 节点 ID 重复
- **WHEN** 模型输出两个具有相同稳定 ID 的图层
- **THEN** 初始文档门禁拒绝输出并定位重复节点，不将其交给规范校验智能体
