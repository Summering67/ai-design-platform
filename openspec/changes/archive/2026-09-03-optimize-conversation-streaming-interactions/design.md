## Context

工作台当前通过 `chat-api.ts` 读取项目级 SSE，在 `workspace-chat.tsx` 中分别维护持久化消息、临时 assistant 文本和按 `runId + taskId + attempt` 聚合的 reasoning。reasoning 已有 16ms 批量提交，assistant 文本仍按每个 delta 更新；共享 `Workspace` 又通过特殊消息 ID `streaming` 判断临时消息并将 reasoning 插入虚拟列表。这使传输、投影和展示之间存在隐式约定，且用户展开状态容易被运行状态或重渲染覆盖。

参考实现 `deepseek-harness` 的有效经验包括：独立 reasoning 披露行、运行中使用最新行摘要、完成后使用首行摘要、帧级视觉更新、稳定条目身份和明确的滚动所有权。但其 Cordis 插件、Conversation Node、持久化 chunk 与 reasoning 回放架构不适用于本项目；本项目契约明确禁止 reasoning 进入消息历史、数据库或日志。

## Goals / Non-Goals

**Goals:**

- 在当前 generation 内实时、轻量地展示 reasoning，并保持其与正式助手消息的语义区分。
- 让用户的展开状态、键盘焦点和历史阅读位置不被高频 chunk 更新打断。
- 统一 reasoning 与 assistant 文本的有界刷新策略，保持原始字符顺序。
- 通过显式 Props 消除 `streaming` 特殊消息 ID 这一隐式接口。
- 在不新增生产依赖的前提下完成改造，并以单元和组件集成测试覆盖行为。

**Non-Goals:**

- 不改变服务端模型请求、SSE 事件结构、HTTP 路由或 generation 终态。
- 不持久化、恢复、搜索或回放 reasoning 与未完成 assistant 文本。
- 不展示 Agent 名称、任务 ID、内部阶段键、尝试次数或执行轨迹声明。
- 不引入 Cordis、`@deepseek-ai/dsh-*`、新的状态库、Markdown 渲染器或折叠组件库。
- 不替换 `react-virtuoso`，也不复制参考项目为历史分页设计的自定义滚动锚点系统。

## Decisions

### 1. 保持三层 seam，收紧 Workspace 接口

`chat-api.ts` 只负责把 SSE 帧解析为事件；`workspace-chat.tsx` 与纯投影函数负责 generation 生命周期和增量聚合；`Workspace` 只负责展示和局部交互。`Workspace` 将继续接收持久化 `messages` 与结构化 `reasoning`，并新增显式的临时 assistant 输入，例如 `streamingMessage: { id: string; content: string } | null`，不再向 `messages` 注入 `{ id: "streaming" }`。

选择显式临时输入是因为特殊 ID 把展示规则泄漏给调用方，也存在真实消息 ID 冲突和测试误判风险。未选择把所有内容统一为参考项目的 Assistant Block，因为本项目 reasoning 来自多个 Agent 任务，且生命周期和持久化规则与正式助手消息不同。

### 2. 使用共享的函数式帧缓冲实现两条流式通道

在 Web 路由附近提供一个小型函数式缓冲模块，内部使用队列、`requestAnimationFrame` 和取消句柄，对外只暴露 enqueue、flush/discard 与 dispose 所需的最小接口。reasoning 通道在同一批次内按接收顺序调用 `applyReasoningEvent`；assistant 通道按顺序连接文本。一个动画帧最多触发一次对应 React 状态提交。

终态处理遵循明确顺序：reasoning 完成事件与此前 delta 进入同一有序队列；服务端 `completed` 提供持久化助手消息时，先取消尚未发布的临时 assistant 更新，再以服务端消息为准；失败、停止、追问和卸载统一丢弃临时队列。未选择为每条 chunk 继续直接 `setState`，因为它会把传输频率直接变成渲染频率；也未选择定时器常量，因为动画帧更贴近可见更新且在后台标签页自然降频。

### 3. reasoning 披露状态归展示模块所有

每个 reasoning 条目以稳定 ID 作为 React key。披露行使用局部受控状态并默认折叠；运行中折叠摘要取最后一个非空行，完成或截断后取第一个非空行。流式文本变化只更新摘要和正文，不重置 `expanded`。完整标题行是点击和键盘操作目标，提供 `aria-expanded`；运行状态通过简短状态文本或等价语义表达，不让辅助技术在每个 chunk 重复朗读整段原文。

未选择由 `status === reasoning` 强制展开，因为这会覆盖用户选择，并让长文本持续改变列表高度。阶段与任务字段只用于聚合和稳定身份，不进入可见文案。

### 4. 复用 Virtuoso 的滚动 seam

继续使用 `react-virtuoso` 的稳定 key、`atBottomStateChange` 与 `followOutput`。只有用户位于底部或接近底部时允许新内容跟随；用户离开底部后不主动写入滚动位置，只显示“最新消息”操作。reasoning 展开引起的动态高度也通过 Virtuoso 处理。

未选择复制参考项目的 DOM hit-test、ResizeObserver 和分页锚点算法，因为当前工作台没有历史向前分页或嵌套 Conversation Node；复制会绕过现有虚拟列表的深模块接口并产生两套滚动所有权。

### 5. 视觉状态保持克制且遵守减少动态效果

运行中的披露行使用单一低对比度扫光或状态点作为标志，完成后停止动画，截断状态显示独立提示。CSS 使用现有冷灰与靛蓝视觉语言，并在 `prefers-reduced-motion: reduce` 下禁用非必要动画。reasoning 正文保持纯文本与换行，不在流式路径引入 Markdown 解析。

### 6. 为交互测试补充最小开发依赖

纯聚合与帧缓冲继续使用 Node 单元测试。折叠、键盘、焦点和流式重渲染需要 DOM 环境；当前 workspace 未声明可执行 TSX 组件测试的工具，因此实现时 SHALL 先确认现有工具链，若仍不可用，仅增加 `vitest` 与 `jsdom` 开发依赖，直接使用 React DOM 测试接口，不增加生产依赖或浏览器测试。

## Risks / Trade-offs

- [实时展示 reasoning 会暴露更多模型原始输出] → 继续限制为已认证当前 generation、禁止持久化与日志，并使用“模型思考”而非执行审计措辞。
- [默认折叠降低完整过程的即时可见性] → 折叠态持续展示最新摘要和运行状态，完整内容保持一次操作可达。
- [动画帧批量提交会增加最多一帧的视觉延迟] → 该延迟换取显著更少的渲染次数，并且不改变接收顺序或终态结果。
- [虚拟列表回收条目可能丢失局部展开状态] → 当前 generation 的 reasoning 位于会话尾部且数量有界；若组件集成测试证明存在可见问题，再将展开映射提升到 `ChatPanel`，不预先增加共享状态。
- [原生或自定义披露控件在不同 DOM 测试环境行为存在差异] → 通过显式受控状态与键盘事件测试锁定接口，不依赖浏览器默认切换细节。
- [辅助技术对高频 live region 的处理不同] → 只播报短运行状态变化，不把持续增长的全文设为原子 live region；无法由 jsdom 覆盖的读屏器差异记录为剩余风险。

## Migration Plan

1. 先加入纯帧缓冲及单元测试，再将 reasoning 与 assistant 临时文本接入，保证终态清理顺序。
2. 收紧 `Workspace` Props，移除特殊 `streaming` 消息 ID，并同步唯一调用方与组件 fixture。
3. 替换 reasoning 披露交互和样式，补充组件集成测试。
4. 运行相关格式化、lint、类型检查、单元测试、组件集成测试和 Web 构建；不把浏览器自动化作为验收方式。
5. 若出现回归，可回退显式临时 Props、帧缓冲和披露行实现；没有数据库迁移、服务端部署顺序或持久数据回滚要求。

## Open Questions

无。默认采用参考实现的折叠策略，同时保留本项目“reasoning 临时且不持久化”的既有安全边界。
