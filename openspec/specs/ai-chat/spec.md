# AI Chat Specification

## Purpose

定义 AI 对话能力的服务端配置、HTTP 契约、上游调用、Web 状态编排和工作台交互要求，确保密钥只保留在服务端，并为多轮对话提供稳定、安全且可访问的端到端行为。

## Requirements

### Requirement: 服务端 AI 配置与密钥保护

系统 SHALL 将上游 BaseURL、APIKey、Model 和请求超时加载为后端强类型配置，SHALL 在 BaseURL 或 APIKey 缺失时阻止 API 服务启动，并 MUST NOT 将 APIKey 暴露给浏览器、HTTP 响应或日志。部署环境 SHALL 使用 `API_` 前缀配置；开发环境 SHALL 能兼容仓库根 `.env.local` 中已有的 `DS_BASE_URL` 与 `DS_API_KEY`，且进程环境变量优先。

#### Scenario: 使用现有本地 AI 配置

- **WHEN** 服务运行于 development，进程环境未提供 AI 地址和密钥，且仓库根 `.env.local` 包含 `DS_BASE_URL` 与 `DS_API_KEY`
- **THEN** 系统加载这两个值作为后端 AI 配置，并且不会将它们发送给浏览器

#### Scenario: 部署环境覆盖本地配置

- **WHEN** 进程环境提供 `API_AI_BASE_URL` 或 `API_AI_API_KEY`，同时本地文件存在对应值
- **THEN** 系统使用进程环境中的值

#### Scenario: 必需 AI 配置缺失

- **WHEN** BaseURL 或 APIKey 在所有允许的配置来源中均为空
- **THEN** 系统返回配置错误且不启动 HTTP 服务

#### Scenario: 超时配置不一致

- **WHEN** HTTP 写超时不大于 AI 请求超时
- **THEN** 系统返回配置错误且不启动 HTTP 服务

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

#### Scenario: generation 等待用户输入

- **WHEN** Agent 发出阻断性的 `input_required`
- **THEN** SSE 返回唯一的 `input_required` 事件并结束当前流，客户端展示逐题回答表单而不是继续发送普通消息

### Requirement: 有界的上游 Chat Completions 调用

系统 SHALL 使用服务端配置，在前台请求上下文和独立 AI 超时内调用兼容 Chat Completions 的上游流式接口。系统 SHALL 从数据库完整历史中选择目标用户消息之前最近最多 24 个完整对话轮次，按原顺序追加当前目标用户消息后发送给上游；达到总内容上限时 SHALL 只移除最旧的整个轮次。系统 MUST NOT 拆分轮次、截断消息、使用失败或中断的临时文本、生成摘要，或向客户端透传上游原始错误、内部网络错误和凭据。

#### Scenario: 上游接收最近完整轮次

- **WHEN** 项目包含超过 24 个完整对话轮次并开始新的 generation
- **THEN** 上游只接收最近 24 个完整轮次和当前目标用户消息，且消息以 user 开始并以当前 user 结束

#### Scenario: 总内容达到上限

- **WHEN** 最近完整轮次与当前目标用户消息的总内容超过服务端上限
- **THEN** 系统从最旧完整轮次开始整轮移除，始终保留当前目标用户消息且不截断任何消息

#### Scenario: 历史包含失败或中断尝试

- **WHEN** 项目历史包含未产生助手消息的失败或中断生成尝试
- **THEN** 系统不把其临时文本或不完整轮次发送给上游，也不生成摘要替代它们

#### Scenario: 上游流式成功返回

- **WHEN** 上游在超时内持续返回有效 assistant 文本并正常结束
- **THEN** 系统向客户端转发文本增量，并在完整结束后保存单条规范化助手消息

#### Scenario: 上游拒绝或响应无效

- **WHEN** 上游返回非成功状态、畸形流或空 assistant 内容
- **THEN** 系统标记生成失败并返回稳定错误事件，且不保存助手消息或暴露上游原始错误

#### Scenario: 上游调用超时

- **WHEN** 上游未在 AI 请求超时内完成流式响应
- **THEN** 系统取消调用、标记生成失败并返回 `ai_timeout` 终态，且不保存助手消息

#### Scenario: 客户端取消请求

- **WHEN** 客户端在上游流式调用期间停止、断开或刷新页面
- **THEN** 系统取消上游调用、标记生成中断并停止后续文本增量

### Requirement: Web 多轮对话编排

Web 应用 SHALL 从项目接口加载完整消息历史，并使用项目级 SSE 接收正在生成的临时 assistant 文本与真实模型 reasoning 增量。Web SHALL 按 run、任务和尝试次数聚合 reasoning，MUST NOT 将其转换为助手消息或持久化历史。Web SHALL 在新消息请求中携带稳定客户端消息标识，同一项目同一时间只允许一个在途生成；失败或中断后 SHALL 保留已保存的用户消息，并只在用户显式操作时基于同一用户消息重新生成。

#### Scenario: 首页 prompt 启动首轮对话

- **WHEN** 用户从公开首页提交非空 prompt，完成必要登录并进入新工作台
- **THEN** Web 从当前标签页恢复该 prompt、只提交一次首轮消息，并在取得项目标识后进入 `/workspace/{projectId}`

#### Scenario: 用户继续对话

- **WHEN** 用户在已加载项目中提交非空内容
- **THEN** Web 立即展示已提交的用户消息、消费 SSE 文本增量，并在完成后以服务端持久化消息为准

#### Scenario: 聚合 reasoning 增量

- **WHEN** Web 连续收到属于同一 run、任务和尝试次数的 reasoning 进度事件
- **THEN** Web 按接收顺序原样追加增量，并且不会插入固定思考文案或改变文本内容

#### Scenario: 请求正在进行

- **WHEN** 当前项目 generation 尚未进入终态
- **THEN** Web 阻止再次提交或重新生成，并提供停止当前 generation 的操作

#### Scenario: 主动停止生成

- **WHEN** 用户在 generation 期间触发停止
- **THEN** Web 请求停止服务端 generation、关闭本地 SSE、丢弃临时 assistant 文本，并保留用户消息供显式重新生成

#### Scenario: 生成失败后显式重新生成

- **WHEN** 当前用户消息的 generation 失败或中断且用户触发重新生成
- **THEN** Web 请求该用户消息的新 generation，且不新增重复用户消息

#### Scenario: 会话失效

- **WHEN** 工作台请求返回 HTTP 401
- **THEN** Web 跳转登录页并保留当前项目地址和当前标签页草稿，登录后恢复它们

### Requirement: 受控且可访问的工作台对话界面

共享 `Workspace` SHALL 通过 Props 与回调接收带稳定 ID 的持久化消息、临时流式文本、按 Agent 任务组织的 reasoning、generation 状态、错误、发送、停止和重新生成动作，MUST NOT 读取应用环境变量或自行请求接口。对话栏 SHALL 使用 `react-virtuoso` 虚拟化展示用户与助手消息，并 SHALL 在与消息分离的生成区域以可访问的可折叠控件展示真实模型 reasoning、生成态、错误态以及支持键盘操作的多行输入区。UI MUST 将 reasoning 标注为模型思考过程，不得将其表示为系统执行日志或事实结论。

#### Scenario: 实时展示 reasoning

- **WHEN** 当前任务收到新的真实 reasoning 增量
- **THEN** 对话栏在对应 Agent 的可折叠区域按原始顺序展示内容，保持当前键盘焦点，并让辅助技术感知内容更新

#### Scenario: 阶段 reasoning 完成

- **WHEN** 对应 Agent 阶段完成
- **THEN** reasoning 区域默认折叠但在当前 generation 页面生命周期内仍可由用户重新展开

#### Scenario: reasoning 被截断

- **WHEN** Web 收到该任务的 reasoning 截断状态
- **THEN** 对应区域以状态信息说明展示已达到上限，且不会伪造缺失内容

#### Scenario: 空项目工作台

- **WHEN** 尚未创建项目且没有 generation 进行
- **THEN** 对话栏展示开始对话的空状态和可用输入区，且不创建空项目

#### Scenario: 键盘发送消息

- **WHEN** 输入内容非空且用户按 Enter
- **THEN** 对话栏调用发送回调并清空本地草稿

#### Scenario: 输入多行内容

- **WHEN** 用户按 Shift+Enter
- **THEN** 输入区插入换行且不调用发送回调

#### Scenario: 空白或生成期间提交

- **WHEN** 草稿只包含空白字符或当前项目正在生成
- **THEN** 发送动作不可用且不会调用发送回调

#### Scenario: 生成期间停止

- **WHEN** 当前项目正在生成
- **THEN** 对话栏展示可访问的停止操作，并在触发时调用停止回调

#### Scenario: 失败或中断后重新生成

- **WHEN** 最新用户消息的生成失败或中断
- **THEN** 对话栏展示可访问的重新生成操作，并在触发时传入该用户消息的稳定 ID

#### Scenario: 流式文本变化

- **WHEN** 新文本增量、持久化消息、generation 状态或错误出现
- **THEN** 对话栏在独立可感知状态区域呈现变化，同时保留当前键盘焦点

#### Scenario: 位于底部时收到新内容

- **WHEN** 用户位于消息列表底部或接近底部且新消息或文本增量出现
- **THEN** 虚拟列表跟随到最新内容

#### Scenario: 浏览历史时收到新内容

- **WHEN** 用户已向上滚动浏览历史且新消息或文本增量出现
- **THEN** 虚拟列表保持当前阅读位置并提供回到底部的操作

#### Scenario: 长对话虚拟渲染

- **WHEN** 消息历史包含大量不同高度的消息
- **THEN** 对话栏只挂载当前视口及必要缓冲区内的消息，并使用稳定消息 ID 保持条目身份

#### Scenario: 对话栏显隐

- **WHEN** 用户隐藏后重新显示对话栏或切换到窄屏布局
- **THEN** 虚拟列表重新适配可用尺寸并保持有效滚动状态
