## MODIFIED Requirements

### Requirement: Root Agent 项目生成
系统 SHALL 在项目 generation 的前台 SSE 请求内，以当前目标用户消息作为需求启动 Root Agent，并使用仅服务端可见的固定 GenerationContract。Root SHALL 按 `StandardizedPRD → UI Design InitialUIDocument → Auto Layout final DesignDocument` 的两个 Agent 依赖推进；Auto Layout MUST 在内部完成确定性编译、Flex 布局规划与应用及最终门禁，系统不得新增 Specification、独立 Compiler、Layout Engine 或 Final Gate 阶段。系统 MUST 将停止、断开和超时取消传播给 Root Agent，且不得启动后台运行。

两个专业 Agent MAY 复用非 Agent 的执行 Harness 进行有限生成与校验 Loop。该 Harness 不得出现在任务 catalog 中，不得改变阶段产物，只能将短错误摘要传给同一 Agent 的下一次尝试。

#### Scenario: 用户消息启动 Root
- **WHEN** 项目所有者提交有效用户消息
- **THEN** 系统保存用户消息与 generation 尝试、发送 generation 事件并启动 Root Agent

#### Scenario: Agent 成功完成
- **WHEN** UI Design 和 Auto Layout 两个 Agent 均通过自身门禁，且 Auto Layout 返回的最终 DesignDocument 通过后端契约与 v2 render model 校验
- **THEN** 系统发送唯一 completed 事件及最终文档，并完成 generation 尝试

#### Scenario: 中间产物无效
- **WHEN** 任一 Agent 输出不符合声明 Schema 或越过职责边界
- **THEN** Root 不把该输出写入有效状态，并按有限重试规则重试或以稳定错误结束，不得由后续 Agent 猜测修复任意结构

### Requirement: Auto Layout 响应式文档契约
最终 DesignDocument v2 Schema SHALL 接受由 Auto Layout Agent 内部合法 LayoutPlan 和布局模块写入的响应式 layout、layoutItem、flexWrap、sizing 和可选 computedLayout 字段；所有枚举与尺寸模式 MUST 受 GenerationContract 限制。Auto Layout Agent MUST 同步提供当前画布可消费的基础 style 投影，并在返回前完成最终文档校验。

#### Scenario: Auto Layout 写入响应式能力
- **WHEN** Auto Layout 计划在合法断点为已有节点提供方向、换行和尺寸覆盖
- **THEN** Auto Layout Agent 内部布局模块写入对应响应式字段，最终文档通过 DesignDocument v2 Schema 和自身渲染契约校验

#### Scenario: 模型尝试写入坐标
- **WHEN** Auto Layout 模型输出包含 computedLayout、x、y、width 或 height 几何结果而非 LayoutPlan 允许的尺寸意图
- **THEN** LayoutPlan Schema 拒绝输出且最终文档保持不变
