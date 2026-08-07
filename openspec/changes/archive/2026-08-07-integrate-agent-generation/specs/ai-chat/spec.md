## MODIFIED Requirements

### Requirement: 稳定的对话 HTTP 契约
系统 SHALL 移除匿名 `POST /api/chat`，并提供受认证的项目级 generation 接口。`POST /api/projects` SHALL 创建项目并处理首条用户消息，`POST /api/projects/{projectId}/generations` SHALL 处理指定项目的新用户消息，二者均 SHALL 以 SSE 返回 generation 元数据、Agent 运行事件和唯一终态。系统 SHALL 限制请求体、客户端消息标识和单条用户内容，且 SHALL 在内容为空、超过 32,000 个字符或包含未知字段时拒绝请求。

#### Scenario: 首次项目生成
- **WHEN** 已登录用户向 `POST /api/projects` 提交有效客户端消息标识和首条用户消息
- **THEN** 系统创建项目与用户消息，并以 SSE 返回项目和 generation 标识、Agent 阶段事件及包含最终设计文档的最终结果

#### Scenario: 已有项目继续对话
- **WHEN** 项目所有者向 `POST /api/projects/{projectId}/generations` 提交有效用户消息且项目无运行中生成
- **THEN** 系统保存用户消息并以 SSE 返回该 generation 的 Agent 运行事件与最终结果

#### Scenario: 非法消息请求
- **WHEN** 请求内容为空、超过长度限制、客户端消息标识无效或包含未知字段
- **THEN** 系统在创建项目、保存消息或调用上游前返回 HTTP 400 与 `invalid_request`

#### Scenario: 匿名 generation 请求
- **WHEN** 未登录客户端请求项目或 generation 接口
- **THEN** 系统返回 HTTP 401 与 `unauthorized`，且不调用上游

#### Scenario: 匿名旧接口已移除
- **WHEN** 客户端请求旧的 `POST /api/chat`
- **THEN** 系统不匹配该路由，且不会提供匿名对话能力
