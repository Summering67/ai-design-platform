## Why

当前模型请求把阶段指令与动态上下文混合组装，尤其是多模态 Codegen 请求会在大型 DesignDocument 和图片之前放置阶段指令，导致跨阶段请求较早出现前缀差异，降低 Prompt Cache 可复用 Token 数。需要统一稳定前缀与动态后缀的组装规则，在不改变 Agent 业务语义的前提下提高缓存命中。

## What Changes

- 为结构化文本请求建立确定性的消息分段：稳定角色说明与响应 Schema 位于前缀，动态业务上下文随后，阶段指令与重试反馈位于末尾。
- 为多模态请求建立确定性的内容分段：稳定 Codegen 规则和共享文档上下文优先，阶段特有上下文、图片及最终指令随后。
- 对 Prompt 消息顺序和重试场景增加单元测试，防止后续修改破坏可缓存前缀。
- 不修改 ModelPort 的公开调用方式、HTTP 接口或业务产物 Schema。

## Capabilities

### New Capabilities

- `prompt-cache-friendly-model-requests`: 规定模型请求必须保留确定性的稳定前缀，并将阶段指令与校验反馈追加到动态内容末尾。

### Modified Capabilities

无。

## Impact

- 影响 `apps/server` 中模型消息构造、Harness 重试载荷和多模态 Codegen 内容组装。
- 增加服务端 Agent 单元测试；不新增依赖或配置。
- 模型输出协议、公开接口和持久化数据结构保持不变。
