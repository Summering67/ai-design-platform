## MODIFIED Requirements

### Requirement: Web 多轮对话编排

Web 应用 SHALL 从项目接口加载完整消息历史，并使用项目级 SSE 接收正在生成的临时 assistant 文本与真实模型 reasoning 增量。Web SHALL 按 run、任务和尝试次数聚合 reasoning，MUST NOT 将其转换为助手消息或持久化历史。Web SHALL 在新消息请求中携带稳定客户端消息标识，同一项目同一时间只允许一个在途生成；失败或中断后 SHALL 保留已保存的用户消息，并只在用户显式操作时基于同一用户消息重新生成。

#### Scenario: 首页 prompt 启动首轮对话

- **WHEN** 用户从公开首页提交非空 prompt，完成必要登录并进入新工作台
- **THEN** Web 从当前标签页恢复该 prompt、只提交一次首轮消息，并在取得项目标识后进入 `/workspace/{projectId}`

#### Scenario: 用户继续对话

- **WHEN** 用户在已加载项目中提交非空内容
- **THEN** Web 立即展示已提交的用户消息、消费 SSE 文本与 reasoning 增量，并在完成后以服务端持久化消息为准

#### Scenario: 聚合 reasoning 增量

- **WHEN** Web 连续收到属于同一 run、任务和尝试次数的 reasoning 进度事件
- **THEN** Web 按接收顺序原样追加增量，并且不会插入固定思考文案或改变文本内容

#### Scenario: 请求正在进行

- **WHEN** 当前项目 generation 尚未进入终态
- **THEN** Web 阻止再次提交或重新生成，并提供停止当前 generation 的操作

#### Scenario: 主动停止生成

- **WHEN** 用户在 generation 期间触发停止
- **THEN** Web 请求停止服务端 generation、关闭本地 SSE、丢弃临时 assistant 文本与 reasoning 状态，并保留用户消息供显式重新生成

#### Scenario: 生成失败后显式重新生成

- **WHEN** 当前用户消息的 generation 失败或中断且用户触发重新生成
- **THEN** Web 请求该用户消息的新 generation，清理上一尝试的临时 reasoning，且不新增重复用户消息

#### Scenario: 会话失效

- **WHEN** 工作台请求返回 HTTP 401
- **THEN** Web 跳转登录页并保留当前项目地址和当前标签页草稿，登录后恢复它们但不恢复 reasoning

### Requirement: 受控且可访问的工作台对话界面

共享 `Workspace` SHALL 通过 Props 与回调接收带稳定 ID 的持久化消息、临时流式文本、按 Agent 任务组织的 reasoning、generation 状态、错误、发送、停止和重新生成动作，MUST NOT 读取应用环境变量或自行请求接口。对话栏 SHALL 使用 `react-virtuoso` 虚拟化展示用户与助手消息，并 SHALL 在与消息分离的生成区域以可访问的可折叠控件展示真实模型 reasoning、生成态、错误态以及支持键盘操作的多行输入区。UI MUST 将 reasoning 标注为模型思考过程，不得将其表示为系统执行日志或事实结论。

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

#### Scenario: 实时展示 reasoning

- **WHEN** 当前任务收到新的真实 reasoning 增量
- **THEN** 对话栏在对应 Agent 的可折叠区域按原始顺序展示内容，保持当前键盘焦点，并让辅助技术感知内容更新

#### Scenario: 阶段 reasoning 完成

- **WHEN** 对应 Agent 阶段完成
- **THEN** reasoning 区域默认折叠但在当前 generation 页面生命周期内仍可由用户重新展开

#### Scenario: reasoning 被截断

- **WHEN** Web 收到该任务的 reasoning 截断状态
- **THEN** 对应区域以状态信息说明展示已达到上限，且不会伪造缺失内容

#### Scenario: 生成期间停止

- **WHEN** 当前项目正在生成
- **THEN** 对话栏展示可访问的停止操作，并在触发时调用停止回调

#### Scenario: 失败或中断后重新生成

- **WHEN** 最新用户消息的生成失败或中断
- **THEN** 对话栏展示可访问的重新生成操作，并在触发时传入该用户消息的稳定 ID

#### Scenario: 流式文本变化

- **WHEN** 新文本增量、reasoning 增量、持久化消息、generation 状态或错误出现
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
