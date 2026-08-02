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
系统 SHALL 提供 `POST /api/chat`，接收按时间顺序排列的 `user` 与 `assistant` 消息，并在成功时返回单条规范化的 assistant 消息。系统 SHALL 限制请求体、消息数量和单条内容长度，且 SHALL 在消息为空、角色不支持、内容为空或最后一条不是 user 时拒绝请求。

#### Scenario: 合法单轮请求
- **WHEN** 客户端提交一条非空 user 消息且上游成功回复
- **THEN** 系统返回 HTTP 200 和只包含稳定 role、content 字段的 assistant 消息

#### Scenario: 合法多轮请求
- **WHEN** 客户端提交由 user 与 assistant 组成且最后一条为 user 的有效历史
- **THEN** 系统按原顺序把完整历史交给上游，并返回本轮 assistant 消息

#### Scenario: 非法消息请求
- **WHEN** 请求缺少消息、包含不支持的角色、包含空内容或最后一条不是 user
- **THEN** 系统在调用上游前返回 HTTP 400 与 `invalid_request` 错误

#### Scenario: 请求超过边界
- **WHEN** 请求体、消息数量或单条内容超过规定上限
- **THEN** 系统在调用上游前返回 HTTP 400 与 `invalid_request` 错误

### Requirement: 有界的上游 Chat Completions 调用
系统 SHALL 使用服务端配置在请求上下文和独立 AI 超时内调用兼容 Chat Completions 的上游，并 SHALL 将应用消息、配置模型和非流式选项转换为最小上游请求。系统 MUST NOT 向客户端透传上游原始错误体、内部网络错误或凭据。

#### Scenario: 上游成功返回
- **WHEN** 上游在超时内返回包含有效 assistant 文本的成功响应
- **THEN** 系统提取首个有效 assistant 文本并转换为应用对话响应

#### Scenario: 上游拒绝或响应无效
- **WHEN** 上游返回非成功状态、畸形 JSON、空 choices 或空 assistant 内容
- **THEN** 系统返回 HTTP 502 与稳定的 `ai_unavailable` 错误，且响应不包含上游原始错误

#### Scenario: 上游调用超时
- **WHEN** 上游未在 AI 请求超时内完成响应
- **THEN** 系统取消调用并返回 HTTP 504 与稳定的 `ai_timeout` 错误

#### Scenario: 客户端取消请求
- **WHEN** 客户端在上游调用期间取消请求
- **THEN** 系统通过请求 context 取消上游调用并停止后续处理

### Requirement: Web 多轮对话编排
Web 应用 SHALL 在内存中维护当前消息历史，SHALL 将每轮完整历史提交到同源后端路径，并 SHALL 在成功时追加 assistant 消息。系统 SHALL 同一时间只允许一个在途请求；失败时 SHALL 保留已发送历史并提供不重复追加 user 消息的重试能力。

#### Scenario: 首页 prompt 启动首轮对话
- **WHEN** 用户从首页携带非空 prompt 进入工作台
- **THEN** Web 应用只自动提交一次该 prompt，立即展示 user 消息，并在成功后展示 assistant 回复

#### Scenario: 用户继续对话
- **WHEN** 已有消息的用户提交新的非空内容
- **THEN** Web 应用追加新的 user 消息，将完整历史发送到后端，并在成功后追加 assistant 回复

#### Scenario: 请求正在进行
- **WHEN** 当前对话请求尚未完成
- **THEN** Web 应用展示等待状态并阻止再次提交

#### Scenario: 请求失败后重试
- **WHEN** 当前轮请求失败且用户触发重试
- **THEN** Web 应用保留已有消息并重新发送同一份历史，不新增重复的 user 消息

### Requirement: 受控且可访问的工作台对话界面
共享 `Workspace` SHALL 通过 Props 与回调接收带稳定 id 的消息、对话状态、错误、发送动作和重试动作，MUST NOT 读取应用环境变量或自行请求接口。对话栏 SHALL 使用 `react-virtuoso` 虚拟化展示 user 与 assistant 消息，并 SHALL 展示等待态、错误态以及支持键盘操作的多行输入区。

#### Scenario: 空会话
- **WHEN** 消息列表为空且没有请求进行
- **THEN** 对话栏展示开始对话的空状态和可用输入区

#### Scenario: 键盘发送消息
- **WHEN** 输入内容非空且用户按 Enter
- **THEN** 对话栏调用发送回调并清空本地草稿

#### Scenario: 输入多行内容
- **WHEN** 用户按 Shift+Enter
- **THEN** 输入区插入换行且不调用发送回调

#### Scenario: 空白或等待期间提交
- **WHEN** 草稿只包含空白字符或对话状态为等待中
- **THEN** 发送动作不可用且不会调用发送回调

#### Scenario: 对话状态变化
- **WHEN** 新消息、等待状态或错误状态出现
- **THEN** 对话栏以虚拟列表和独立可感知状态区域呈现变化，同时保留当前键盘焦点

#### Scenario: 位于底部时收到新消息
- **WHEN** 用户位于消息列表底部或接近底部且新消息出现
- **THEN** 虚拟列表跟随到最新消息

#### Scenario: 浏览历史时收到新消息
- **WHEN** 用户已向上滚动浏览历史且新消息出现
- **THEN** 虚拟列表保持当前阅读位置并提供回到底部的操作

#### Scenario: 长对话虚拟渲染
- **WHEN** 消息历史包含大量不同高度的消息
- **THEN** 对话栏只挂载当前视口及必要缓冲区内的消息，并使用稳定消息 id 保持条目身份

#### Scenario: 对话栏显隐
- **WHEN** 用户隐藏后重新显示对话栏或切换到窄屏布局
- **THEN** 虚拟列表重新适配可用尺寸并保持有效滚动状态
