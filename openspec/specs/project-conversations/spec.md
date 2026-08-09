# project-conversations Specification

## Purpose

TBD - created by archiving change add-single-user-authentication. Update Purpose after archive.

## Requirements

### Requirement: 项目归属与首次发送创建

系统 SHALL 将每个项目归属于一个用户，且一个项目 SHALL 对应一条 AI 对话。系统 MUST 在已登录用户首次发送非空消息时，原子创建项目、用户消息和生成尝试；仅访问或离开空白工作台 MUST NOT 创建项目。

#### Scenario: 首次发送创建项目

- **WHEN** 已登录用户向 `POST /api/projects` 提交有效的首条用户消息
- **THEN** 系统创建归属于该用户的项目、基于首条消息生成的标题、用户消息和运行中的生成尝试

#### Scenario: 离开空白工作台

- **WHEN** 已登录用户打开 `/workspace` 后未发送消息便离开
- **THEN** 系统不创建项目、消息或生成尝试记录

#### Scenario: 首次发送完成路由归属

- **WHEN** 首次发送返回项目标识
- **THEN** Web 将当前地址替换为 `/workspace/{projectId}`，后续读取和生成均使用该项目标识

### Requirement: 项目读取与完整历史

系统 SHALL 只向项目所有者返回项目，并 SHALL 返回项目中按稳定时间顺序排列的全部完整用户消息和助手消息。系统 MUST NOT 将 SSE 临时文本、失败或中断尝试的未完成文本作为消息返回。

#### Scenario: 打开已有项目

- **WHEN** 项目所有者请求 `GET /api/projects/{projectId}`
- **THEN** 系统返回项目资料和从首条至最新一条的完整消息历史

#### Scenario: 刷新生成完成的项目

- **WHEN** 项目生成已完整完成且用户刷新 `/workspace/{projectId}`
- **THEN** Web 从项目接口恢复已持久化的用户消息和助手消息

#### Scenario: 刷新生成中断的项目

- **WHEN** 项目上一生成尝试已中断且用户刷新项目页面
- **THEN** Web 恢复已保存的用户消息，但不恢复任何未完成助手文本

#### Scenario: 读取其他用户项目

- **WHEN** 当前用户请求不属于自己的项目标识
- **THEN** 系统返回 HTTP 404 与 `not_found`，且不泄露项目或消息资料

### Requirement: 最近项目列表

系统 SHALL 通过 `GET /api/projects` 返回当前用户最近更新的最多 20 个项目，并按更新时间倒序和稳定次序排列。

#### Scenario: 读取最近项目

- **WHEN** 已登录用户请求最近项目列表
- **THEN** 系统只返回该用户的最多 20 个项目且最新更新项目在前

#### Scenario: 用户没有项目

- **WHEN** 已登录用户尚未发送过首条消息
- **THEN** 系统返回空项目列表

### Requirement: 用户消息先于生成持久化

创建项目或开始后续 generation 时，系统 MUST 在调用上游 AI 前提交用户消息与运行中的生成尝试。若前置持久化失败，系统 MUST NOT 调用上游或建立成功的 SSE 流。

#### Scenario: 后续消息开始生成

- **WHEN** 项目所有者向 `POST /api/projects/{projectId}/generations` 提交有效用户消息
- **THEN** 系统先保存用户消息和生成尝试，再调用上游并返回 SSE

#### Scenario: 持久化失败

- **WHEN** 用户消息或生成尝试无法提交到数据库
- **THEN** 系统返回稳定错误且不调用上游 AI

### Requirement: 完整助手消息提交

系统 SHALL 仅在上游完整成功结束后保存单条助手消息，并 SHALL 将助手消息与对应生成尝试原子标记为完成。失败、停止、连接断开或上游中断 MUST NOT 保存半截助手回复。

#### Scenario: 生成完整完成

- **WHEN** 上游生成非空助手回复并正常结束
- **THEN** 系统原子保存完整助手消息、关联生成尝试并将其标记为完成

#### Scenario: 生成中途失败

- **WHEN** 上游在已产生部分文本后失败
- **THEN** 系统将生成尝试标记为失败且不保存任何助手消息

#### Scenario: 用户停止生成

- **WHEN** 用户停止正在运行的生成
- **THEN** 系统取消上游调用、将生成尝试标记为中断且不保存已流式展示的临时文本

### Requirement: 项目内生成串行化

系统 SHALL 同时只允许一个项目存在一个运行中的生成尝试。不同客户端消息标识在项目已有运行中生成时 MUST 被拒绝且不得写入消息；重复提交相同客户端消息标识 MUST NOT 重复创建消息、生成尝试或上游调用。

#### Scenario: 多浏览器并发发送

- **WHEN** 同一项目已有运行中的生成且另一浏览器提交不同客户端消息标识
- **THEN** 系统返回 HTTP 409 与 `generation_in_progress`，且不保存第二条用户消息

#### Scenario: 重复提交相同消息

- **WHEN** 客户端以同一项目和相同客户端消息标识重复提交发送请求
- **THEN** 系统返回既有消息和生成状态，且不创建重复记录或自动重新调用上游

#### Scenario: 异常生成租约过期

- **WHEN** 项目仅有一条租约已过期但仍标记为运行中的生成尝试，且用户发起新生成
- **THEN** 系统先将过期尝试标记为中断，再尝试创建新的生成尝试

### Requirement: 停止与显式重新生成

系统 SHALL 允许项目所有者通过 `POST /api/projects/{projectId}/generations/{generationId}/stop` 停止当前运行中的 generation，并通过 `POST /api/projects/{projectId}/messages/{messageId}/generations` 对尚无被采纳助手消息的用户消息显式重新生成。重新生成 SHALL 复用原用户消息并创建新的生成尝试，且 MUST NOT 自动触发。

#### Scenario: 显式停止运行中生成

- **WHEN** 项目所有者请求停止当前运行中的 generation
- **THEN** 系统触发当前上游取消并将该尝试终结为中断

#### Scenario: 重复停止已结束生成

- **WHEN** 项目所有者请求停止已完成、失败或中断的 generation
- **THEN** 系统按既有终态幂等返回且不改变消息历史

#### Scenario: 显式重新生成失败消息

- **WHEN** 用户对失败或中断且尚无助手消息的用户消息发起重新生成
- **THEN** 系统创建新的生成尝试、复用原用户消息并以 SSE 返回新生成

#### Scenario: 拒绝重新生成已完成消息

- **WHEN** 用户对已经关联被采纳助手消息的用户消息请求重新生成
- **THEN** 系统返回 HTTP 409 与稳定错误码，且不创建新尝试

### Requirement: 无后台队列与自动重试

系统 SHALL 在发起 generation 的前台 HTTP 请求内执行上游生成，MUST NOT 将其提交到后台队列，MUST NOT 在失败、断开或中断后自动重试，也 MUST NOT 在客户端断开后继续生成。

#### Scenario: SSE 客户端断开

- **WHEN** 客户端在 generation 完成前断开 SSE 请求且未建立其他前台生成请求
- **THEN** 系统取消上游调用并终结当前尝试，不在后台继续生成或重试

#### Scenario: 上游失败

- **WHEN** 上游 generation 返回失败
- **THEN** 系统记录失败终态并等待用户显式重新生成

### Requirement: 阻断输入与生成恢复

系统 SHALL 支持 generation 状态 `awaiting_input`。所有 Agent 的结构化 `input_required` 请求 SHALL 持久化并暂停当前 generation；项目所有者通过专用回答接口提交每个问题的非空答案后，系统 SHALL 将同一 generation 恢复为 `running`，从 Requirement 阶段重新执行，并将与来源阶段匹配的已回答输入传递给 Agent。每个 Agent 阶段最多允许三轮阻断追问。

问题选项 SHALL 随问题单持久化。未开放“其他”回答的问题只接受其选项 label；开放“其他”回答的问题可接受用户提供的非空自定义内容。

#### Scenario: 用户回答后恢复生成

- **WHEN** 项目所有者提交 pending input request 的完整答案
- **THEN** 系统原子保存答案、恢复 generation 并通过 SSE 返回后续 Agent 事件和最终结果

#### Scenario: 不完整或重复回答

- **WHEN** 回答缺少问题、包含未知问题 ID、重复问题 ID 或重复 response ID
- **THEN** 系统拒绝回答且不得启动第二次 Agent 执行

### Requirement: Agent 成功说明消息

系统 SHALL 在 Root Agent 成功产生最终设计文档后创建简短助手消息以完成既有项目对话轮次；该消息 MUST NOT 包含或替代 DesignDocument。

#### Scenario: 成功后保留对话轮次

- **WHEN** Agent 运行成功并返回最终文档
- **THEN** 系统保存一条助手完成说明并将生成尝试标记为完成
