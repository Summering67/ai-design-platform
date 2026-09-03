## MODIFIED Requirements

### Requirement: Web 多轮对话编排
Web 应用 SHALL 从项目接口加载完整消息历史，并使用项目级 SSE 接收 Agent 运行事件与真实模型 reasoning 增量。Web SHALL 按 run、任务和尝试次数聚合 reasoning，MUST NOT 将其转换为助手消息或持久化历史。Web SHALL 将 reasoning 与临时助手正文增量按动画帧或等价的有界刷新周期批量提交，保持字符内容和接收顺序不变。Web SHALL 在新消息请求中携带稳定客户端消息标识，同一项目同一时间只允许一个在途生成；失败或中断后 SHALL 保留已保存的用户消息，并只在用户显式操作时基于同一用户消息重新生成。

#### Scenario: 首页 prompt 启动首轮对话

- **WHEN** 用户从公开首页提交非空 prompt，完成必要登录并进入新工作台
- **THEN** Web 从当前标签页恢复该 prompt、只提交一次首轮消息，并在取得项目标识后进入 `/workspace/{projectId}`

#### Scenario: 用户继续对话

- **WHEN** 用户在已加载项目中提交非空内容
- **THEN** Web 立即展示已提交的用户消息、消费 SSE Agent 事件，并在完成后以服务端持久化消息和最终设计文档为准

#### Scenario: 聚合 reasoning 增量

- **WHEN** Web 连续收到属于同一 run、任务和尝试次数的 reasoning 进度事件
- **THEN** Web 按接收顺序原样缓冲增量、以有界频率发布临时状态，并且不会插入固定思考内容或改变文本

#### Scenario: 生成中展示 reasoning

- **WHEN** Web 收到当前 generation 的首个非空 reasoning 增量
- **THEN** Web 立即创建对应的临时运行条目供工作台展示，不等待阶段完成事件

#### Scenario: 阶段成功后固定 reasoning

- **WHEN** Web 收到同一任务的 `completed` 或 `reasoning_completed` 事件
- **THEN** Web 在先应用此前已接收增量后将对应条目标记为完成，并保留到页面离开或下一次 generation 开始

#### Scenario: 请求正在进行

- **WHEN** 当前项目 generation 尚未进入终态
- **THEN** Web 阻止再次提交或重新生成，并提供停止当前 generation 的操作

#### Scenario: 主动停止生成

- **WHEN** 用户在 generation 期间触发停止
- **THEN** Web 请求停止服务端 generation、关闭本地 SSE、取消待提交的临时更新、丢弃 reasoning 与 assistant 临时文本，并保留用户消息供显式重新生成

#### Scenario: 生成失败后显式重新生成

- **WHEN** 当前用户消息的 generation 失败或中断且用户触发重新生成
- **THEN** Web 请求该用户消息的新 generation，且不新增重复用户消息

#### Scenario: 会话失效

- **WHEN** 工作台请求返回 HTTP 401
- **THEN** Web 跳转登录页并保留当前项目地址和当前标签页草稿，登录后恢复它们

### Requirement: 受控且可访问的工作台对话界面
共享 `Workspace` SHALL 通过 Props 与回调接收带稳定 ID 的持久化消息、显式的临时流式文本、generation 状态、运行中或已完成的 reasoning、结构化追问、错误、发送、停止和重新生成动作，MUST NOT 通过特殊消息 ID 推断流式状态，MUST NOT 读取应用环境变量或自行请求接口。对话栏 SHALL 使用 `react-virtuoso` 虚拟化展示用户、助手消息及临时 reasoning，并 SHALL 在与正式消息视觉和语义分离的披露行中展示 reasoning。披露行 SHALL 默认折叠，运行中显示最新非空行摘要，完成后显示首个非空行摘要，用户展开选择在流式重渲染期间保持稳定。生成态、错误态、结构化追问按钮及支持键盘操作的多行输入区 SHALL 位于独立可感知区域。UI MUST NOT 展示 Agent 名称、任务标识、内部阶段键或尝试次数；只有合法 `input_required` 中的问题和选项可以作为用户需要回答的内容。

#### Scenario: 隐藏 Agent 调用信息

- **WHEN** reasoning 数据包含 Agent 阶段、任务标识和尝试次数
- **THEN** 对话栏仅使用通用“正在思考”或“思考过程”标题展示内容，不展示内部身份信息

#### Scenario: 运行中 reasoning 折叠摘要

- **WHEN** reasoning 条目处于运行状态且包含一个或多个非空文本行
- **THEN** 披露行默认折叠、显示最新非空行摘要和可感知运行状态，并允许用户展开完整原文

#### Scenario: reasoning 完成后固定摘要

- **WHEN** 已展示的 reasoning 条目从运行状态变为完成状态
- **THEN** 披露行改用首个非空行作为摘要，并保持用户此前选择的展开或折叠状态

#### Scenario: reasoning 内容被截断

- **WHEN** reasoning 条目状态为 `truncated`
- **THEN** 披露行保留已收到原文并明确提示内容已达到展示上限

#### Scenario: 键盘操作 reasoning

- **WHEN** 键盘焦点位于 reasoning 披露行且用户按 Enter 或空格键
- **THEN** 对话栏切换该条目的展开状态且焦点保持在原控件

#### Scenario: 正式追问替换未完成 reasoning

- **WHEN** Web 在缓冲 reasoning 后收到合法 `input_required`
- **THEN** Web 丢弃当前未完成 reasoning，只展示结构化问题及编号选项按钮

#### Scenario: 展示结构化追问按钮

- **WHEN** Web 收到合法 `input_required`
- **THEN** 对话栏按问题展示编号选项按钮，等待用户完成回答后再恢复 generation

#### Scenario: 追问内容超过可用高度

- **WHEN** 结构化追问的问题和选项无法在对话栏剩余高度内完整展示
- **THEN** 问题列表可独立上下滚动，提交按钮保持可见，并在所有问题均已回答后允许用户提交

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

#### Scenario: 运行事件变化

- **WHEN** 新 Agent 事件、流式增量、持久化消息、generation 状态或错误出现
- **THEN** 对话栏在独立可感知状态区域呈现变化，同时保留当前键盘焦点且不重复朗读完整 reasoning

#### Scenario: 位于底部时收到新内容

- **WHEN** 用户位于消息列表底部或接近底部且新消息或文本增量出现
- **THEN** 虚拟列表跟随到最新内容

#### Scenario: 浏览历史时收到新内容

- **WHEN** 用户已向上滚动浏览历史且新消息或文本增量出现
- **THEN** 虚拟列表保持当前阅读位置并提供回到底部的操作

#### Scenario: 长对话虚拟渲染

- **WHEN** 消息历史包含大量不同高度的消息
- **THEN** 对话栏只挂载当前视口及必要缓冲区内的消息，并使用稳定消息或 reasoning ID 保持条目身份

#### Scenario: 对话栏显隐

- **WHEN** 用户隐藏后重新显示对话栏或切换到窄屏布局
- **THEN** 虚拟列表重新适配可用尺寸并保持有效滚动状态
