# design-document-canvas-delivery Specification

## Purpose

定义最终设计文档到工作台画布的交付与渲染。

## Requirements

### Requirement: 最终设计文档画布交付
系统 SHALL 在 Agent 成功终态将最终 DesignDocument 作为 JSON 交付工作台，Web SHALL 使用 v2 设计文档渲染器显示在画布区域。

#### Scenario: 成功渲染画布

- **WHEN** Web 收到 completed 事件中的有效 DesignDocument
- **THEN** 工作台以该文档替换画布等待状态
