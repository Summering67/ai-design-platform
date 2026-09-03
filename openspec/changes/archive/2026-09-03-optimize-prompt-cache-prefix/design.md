## Context

模型适配器当前把角色说明和响应 Schema 放入 system 消息，把完整业务载荷序列化为单个 user 消息。Harness 重试会把 `validationFeedback` 混回业务载荷；多模态 Codegen 又把共享规则、阶段指令和大型文档拼成一个文本块，阶段指令先于文档，生成与修复还使用不同 purpose。上述顺序使本可复用的大型上下文之后无法继续共享缓存前缀。

本变更只调整请求组装，不依赖特定供应商的显式缓存字段；缓存是否生效仍由兼容 Chat Completions 的模型服务决定。

## Goals / Non-Goals

**Goals:**

- 让相同 purpose 与 Schema 的结构化请求具有字节级确定的 system 前缀。
- 让 Harness 首次尝试与重试共享完整业务上下文，将短校验反馈和最终指令留在末尾。
- 让 Codegen 生成与修复共享规则、DesignDocument、viewport、图片和 CodePlan 前缀。
- 通过请求捕获型单元测试固定消息和内容块顺序。

**Non-Goals:**

- 不承诺具体缓存命中率或计费下降幅度。
- 不新增供应商专属 `cache_control`、缓存键或配置。
- 不修改 Agent 输出 Schema、HTTP 接口、持久化结构或重试次数。

## Decisions

### 1. 在模型适配器内部拆分上下文与尾部指令

保留 `ModelPort.structured(purpose, payload, schema)` interface。实现会从 payload 中提取 `instruction` 与 `validationFeedback`，其余字段按原顺序紧凑序列化为上下文消息；尾部消息以固定字段顺序先放反馈、最后放 instruction。这样调用方无需学习缓存规则，缓存优化集中在一个深 module 内。

替代方案是在每个 Agent 调用点手工拆消息，但会扩大 interface 并让排序规则散落在调用方，降低 locality。

### 2. 保持 system 消息稳定且包含响应契约

purpose、通用输出规则和紧凑 JSON Schema 继续组成 system 消息。对同一 Agent 阶段，它们是稳定且确定的；业务输入不得进入该前缀。Schema 使用现有紧凑序列化，避免无意义空白造成前缀变化。

替代方案是把 Schema 放到末尾；这能跨不同 Schema 共享更短的前缀，但会牺牲同阶段请求对大型 Schema 的缓存复用，并弱化响应契约的优先级。

### 3. 多模态内容使用独立、确定顺序的内容块

Codegen 请求按以下顺序构造：共享系统规则、共享 DesignDocument/viewport 文本、原始画布图片、按插入顺序拆分的阶段上下文字段、额外预览图片、最终阶段指令。生成与修复统一使用相同 purpose，使使用相同文件 Schema 的请求可以共享到 CodePlan 为止。

替代方案是继续拼接单个文本块，仅把 instruction 移到字符串末尾；它仍会把阶段上下文的任一差异扩散到后续所有内容，无法复用图片与共同 CodePlan。

### 4. 用结构测试验证缓存友好性

测试断言消息/内容块的相同前缀和尾部指令位置，不模拟供应商缓存统计。缓存命中还受模型、最小 Token 门槛和供应商实现影响，单元测试不应伪造这些外部结果。

## Risks / Trade-offs

- [风险] 拆成多个 user 内容块或消息后，部分兼容服务可能对消息边界有细微行为差异 → 保留原始文本内容和顺序语义，并通过现有 Agent 单元测试验证输出协议。
- [风险] 共享前缀不足供应商最小缓存 Token 门槛时收益有限 → 优先覆盖大型 Schema、DesignDocument 和图片等高 Token 内容，不对命中率作硬编码承诺。
- [风险] payload 中同名字段被当作控制字段提取 → 仅提取现有约定字段 `instruction`、`validationFeedback`，当前所有调用方均将它们用作模型控制信息。

## Migration Plan

直接部署请求组装变更，无数据迁移。若模型行为出现回归，可回滚相关模型与 Codegen 组装代码；公开 interface 和存量数据均无需恢复。

## Open Questions

无。
