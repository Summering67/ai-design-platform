## ADDED Requirements

### Requirement: Root 模型驱动调度
系统 SHALL 使用一个 Root Supervisor LangGraph 根据当前运行状态、已完成输出、校验报告和剩余目标，动态选择已注册的专业子图、决定调用顺序、是否重复调用以及何时进入最终门禁。Root MUST 只负责能力发现、输入输出校验、任务派发、状态推进、有限重试、错误收敛和结果汇总，不得承担专业生成逻辑。模型可以改变阶段顺序，但不得绕过声明的数据依赖、Schema 校验、Profile 校验或最终门禁。

#### Scenario: 模型选择执行路径
- **WHEN** 调用方提交合法产品需求和固定版本的 DesignGenerationContract
- **THEN** Root 根据当前状态选择一个或多个可用专业子图执行，允许在需求解析、UI 设计、规范校验和 Auto Layout 之间循环或调整顺序，并在满足最终门禁前持续推进

#### Scenario: 数据依赖阻止调用
- **WHEN** Root 选择的专业子图缺少其声明的结构化输入
- **THEN** Root 不派发该子图，改为选择其他可执行子图或返回等待状态，不得向子图传递缺失、伪造或未校验的数据

#### Scenario: 仅允许注册能力
- **WHEN** Root 或专业 Agent 请求调用未注册的 Agent 能力
- **THEN** Agent Runtime 拒绝该请求并返回稳定的能力不可用错误，不创建未声明的运行时 Agent

#### Scenario: 并行执行独立任务
- **WHEN** UI 设计和其他已声明子图的输入依赖均已满足，且全局执行额度允许并行
- **THEN** Root 可以并行派发这些子图，并在全部必要结果到达后重新评估下一步，而不是假设固定的先后顺序

#### Scenario: 最终门禁不可绕过
- **WHEN** Root 认为当前 v2 DesignDocument 已经满足用户目标
- **THEN** Root MUST 先调用最终门禁；只有 v2 最终门禁通过后才能产生 `result`，否则根据报告继续派发修正 Agent 或进入失败终态

### Requirement: 稳定任务身份与父子归属
系统 SHALL 为 Root 运行、每个动态派发任务和每次 Agent 尝试分配稳定身份。任务 MUST 记录所属 run ID、注册能力名、模型选择的任务名、尝试序号、Root 或父任务身份以及当前状态；同一任务重试 MUST 创建新的尝试身份，但不得覆盖前一次尝试记录。调用方和运行事件 MUST 使用这些身份关联状态，不得依赖模型生成的显示名称或内部 LangGraph 节点对象地址。

#### Scenario: 动态任务首次派发
- **WHEN** Root 根据当前状态首次派发 UI 设计能力
- **THEN** 系统创建归属于当前 run 的 UI 设计任务身份和尝试序号 1，并在该任务的开始、进度和完成事件中保持一致

#### Scenario: 动态任务重试保留谱系
- **WHEN** UI 设计任务因可重试结构化输出错误执行第二次尝试
- **THEN** 第二次尝试具有新的尝试身份和序号 2，同时继续归属于同一 run、同一注册能力和同一父任务

### Requirement: 专业 Agent 生命周期状态机
系统 SHALL 以运行事件确定性派生每个专业 Agent 尝试的生命周期，状态至少包含 `pending`、`running`、`completed`、`failed` 和 `cancelled`。每次尝试 MUST 从 `pending` 至多进入一次 `running`，并恰好进入一个终态；终态之后到达的重复完成、进度或错误事件 MUST 被忽略且不得触发新的模型调度。

#### Scenario: 完成事件推进 Root
- **WHEN** 当前专业 Agent 尝试从 `running` 进入 `completed` 且结构化输出通过 Schema
- **THEN** Root 原子记录该尝试终态与有效输出，然后根据最新状态重新评估并选择可执行任务

#### Scenario: 忽略迟到事件
- **WHEN** 已取消的专业 Agent 尝试随后返回进度或完成事件
- **THEN** 系统忽略该事件，不修改 Graph State、不产生结果事件且不启动后续阶段

### Requirement: 版本化运行状态与阶段交接
系统 SHALL 为每次运行维护唯一 run ID、活动任务及其状态、已完成任务摘要、固定 Profile 引用、标准 PRD、各任务产生的 UI 文档、校验报告、重试计数和错误终态。所有子图交接值 MUST 在写入 Graph State 前通过对应版本化 JSON Schema，且 MUST 是可序列化数据，不得包含模型客户端、请求对象或数据库连接。

#### Scenario: 拒绝无效任务输出
- **WHEN** 子图返回缺少必填字段、包含未知字段或不符合声明版本的结果
- **THEN** Root 将该结果标记为结构化输出错误，不把它写入有效任务状态

#### Scenario: 保持 Profile 固定
- **WHEN** 任一任务输出的 Profile ID、版本或摘要不同于运行开始时固定值
- **THEN** Root 立即失败关闭，且不使用当前 Profile、默认 Profile或同名版本替代

### Requirement: 最小上下文投影与阶段隔离
Root SHALL 按每个专业 Agent 声明的输入 Schema 从 Graph State 构造最小上下文投影，不得默认复制完整对话、其他 Agent 的模型消息、无关中间文档或内部错误。专业 Agent MUST 只通过声明的结构化输出向 Root 回传结果，不得直接修改其他任务状态。重试输入 SHALL 由原任务输入、上一次结构化校验报告和固定运行元数据组成，不得追加无界模型历史。

#### Scenario: UI 设计 Agent 只接收所需上下文
- **WHEN** Root 派发 UI 设计任务
- **THEN** UI 设计 Agent 只接收标准 PRD、固定 DesignGenerationContract 和运行关联身份，不接收需求解析 Agent 的原始模型消息或其他未声明状态

#### Scenario: 校验反馈驱动同任务重试
- **WHEN** 专业 Agent 输出未通过结构化 Schema 且允许重试
- **THEN** Root 使用原任务输入和有界校验反馈重新派发同一注册能力，不传递上一次原始模型响应，也不重复执行不受当前任务依赖的已完成任务

### Requirement: 有界重试与唯一终态
Root SHALL 仅对明确标记为可重试的模型结构化输出错误执行同任务重试，每个动态任务最多重试一次。运行 MUST 恰好产生 `result`、`failed` 或 `cancelled` 中的一个终态；确定性契约错误、Profile 漂移和资源上限错误不得重试。

#### Scenario: 可重试输出第二次成功
- **WHEN** 某动态任务首次模型输出无法通过 Schema 且错误被标记为可重试，第二次输出合法
- **THEN** Root 记录一次重试并根据最新状态重新选择可执行任务，不强制回到固定顺序

#### Scenario: 重试耗尽
- **WHEN** 某动态任务第二次输出仍不合法
- **THEN** Root 返回该任务对应的稳定失败码，并且不产生部分成功结果

### Requirement: 有界执行额度
Agent Runtime SHALL 对活跃 Root 运行、专业 Agent 执行和上游模型调用实施显式且可配置的并发上限，并在派发前原子预留执行额度。单次运行可以并行执行多个输入依赖已满足的专业 Agent，但不得超过运行级和全局额度；额度不足时 MUST 在启动专业 Agent 或调用模型前返回稳定的容量错误，不得无界排队、超额启动或通过重试绕过额度。执行进入任一终态后 MUST 释放其额度。

#### Scenario: 并发额度耗尽
- **WHEN** 新运行准备派发需求解析 Agent，但全局专业 Agent 执行额度已满
- **THEN** 系统不启动子图或模型调用，并返回可识别的容量错误

#### Scenario: 取消后释放额度
- **WHEN** 运行期间当前专业 Agent 被取消并进入 `cancelled` 终态
- **THEN** 系统释放该 Agent 占用的执行额度，且同一尝试的重复取消不会重复释放

### Requirement: 流式事件与取消传播
Agent Runtime SHALL 按版本化运行事件 Schema 流式发送 run、stage、progress 和唯一终态事件。每个专业 Agent 事件 MUST 携带 run ID、阶段身份和尝试身份，使 Root 能够关联、去重并确定性推进状态。调用方断开、显式取消或运行超时时，取消 MUST 从 Root 传播到当前专业 Agent 子图和上游模型调用；当前尝试确认终止或达到取消超时前，Root 不得启动后续阶段，终止后不得继续发送进度或结果事件。

#### Scenario: 调用方取消运行
- **WHEN** 调用方在任一动态子图执行期间取消运行
- **THEN** 当前运行中的模型请求和所有未完成子图均被取消，事件流以唯一 `cancelled` 终态结束

#### Scenario: 隐藏内部实现
- **WHEN** 子图或上游模型返回异常
- **THEN** 事件流只包含稳定阶段和错误码，不包含 prompt、模型原始响应、内部路径、堆栈或凭证

#### Scenario: 重复完成通知
- **WHEN** Root 收到相同 run ID、任务身份和尝试身份的重复完成事件
- **THEN** Root 只处理第一次有效完成事件，后续重复事件不重复写入状态、不重复触发新的模型调度

### Requirement: 单次运行状态不形成持久化事实源
第一阶段 Agent Runtime MUST 以无跨调用记忆的子图执行，不持久化项目对话、DesignDocument 或长期 Agent memory。相同 run ID 的重放行为由调用方控制，Agent Runtime 不得把内存 checkpoint 当作业务恢复依据。

#### Scenario: 独立运行不继承历史
- **WHEN** 两次运行使用不同 run ID 但提交相同需求
- **THEN** 第二次运行不读取第一次运行的 Graph State、模型消息或中间文档
