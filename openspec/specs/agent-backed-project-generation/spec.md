# agent-backed-project-generation Specification

## Purpose

定义由 Root Agent 驱动的项目级设计生成。

## Requirements

### Requirement: Root Agent 项目生成
系统 SHALL 在项目 generation 的前台 SSE 请求内，以当前目标用户消息作为需求启动 Root Agent，并使用仅服务端可见的固定 GenerationContract。系统 MUST 将停止、断开和超时取消传播给 Root Agent，且不得启动后台运行。

#### Scenario: 用户消息启动 Root

- **WHEN** 项目所有者提交有效用户消息
- **THEN** 系统保存用户消息与 generation 尝试、发送 generation 事件并启动 Root Agent

#### Scenario: Agent 成功完成

- **WHEN** Root Agent 产生有效最终 DesignDocument
- **THEN** 系统发送唯一 completed 事件及最终文档，并完成 generation 尝试
