## 1. DeepSeek reasoning 流适配

- [x] 1.1 将 Agent 模型适配器接入 lifespan 管理的共享 HTTPX client，显式启用 `thinking` 和 Chat Completions 流，并保持现有超时、鉴权与稳定错误映射。
- [x] 1.2 实现模型模块内部的 SSE 纯解析逻辑，分离 `delta.reasoning_content`、`delta.content`、终止帧与畸形帧，最终 content 继续执行 JSON 对象解析。
- [x] 1.3 扩展 ModelPort 的结构化调用和 Root 任务选择调用，使其通过显式异步 sink 原样发送非空 reasoning 增量，且不在全局模型实例保存 generation 状态。
- [x] 1.4 【单元测试】覆盖 thinking 请求参数、reasoning/content 分流、无 reasoning、原始顺序、畸形流、上游错误和取消传播。

## 2. Agent 事件与输出边界

- [x] 2.1 在 Root 选择和每个子 Agent 尝试中绑定 run、stage、taskId 与 attempt，将 reasoning 映射为 `status=reasoning` 的既有 progress 事件。
- [x] 2.2 按单个任务尝试执行既有 Agent 输出字节上限，达到上限后只发送一次 `reasoning_truncated`，同时继续消费并校验最终结构化 content。
- [x] 2.3 确保 reasoning 不进入阶段 output、助手消息、数据库、错误 payload 或日志，并在停止、断开和超时时立即停止发送。
- [x] 2.4 【集成测试】覆盖项目 SSE 中 reasoning 事件的身份与顺序、阶段完成分离、截断、无 reasoning、终态和客户端取消行为。

## 3. Web reasoning 状态编排

- [x] 3.1 为 Web 定义结构化 reasoning 条目与纯聚合逻辑，使用 runId、taskId 和 attempt 作为身份，按原始顺序追加 delta 并处理完成与截断状态。
- [x] 3.2 调整工作台 SSE 消费逻辑，使 reasoning 不再通过通用 Agent 文本消息展示，并在新 generation、重试、失败、中断、停止和卸载时按规格清理临时状态。
- [x] 3.3 对高频 reasoning chunk 进行有界批量提交，保持字符内容和接收顺序不变，避免每个小 chunk 触发一次完整消息列表更新。
- [x] 3.4 【单元测试】覆盖 reasoning 聚合、不同任务和重试隔离、顺序保持、截断、终态保留及各类清理路径。

## 4. 工作台可访问展示

- [x] 4.1 扩展共享 Workspace Props，接收按 Agent 任务组织的 reasoning 数据，并在与持久化消息分离的生成区域渲染。
- [x] 4.2 实现可键盘操作的可折叠“模型思考过程”区域：活跃阶段展开、完成阶段折叠且可重新打开，并呈现截断状态与辅助技术可感知的增量更新。
- [x] 4.3 确保 reasoning 展示不改变消息虚拟列表身份、当前键盘焦点、助手消息内容或最终 DesignDocument 渲染。
- [x] 4.4 【组件测试】覆盖真实增量展示、折叠交互、阶段分组、截断提示、焦点保持和 reasoning 与消息的视觉语义分离。

## 5. 契约与验证

- [x] 5.1 同步受影响的 Agent 事件 fixture、类型和契约测试，确认复用 progress enum 且 payload 行为符合增量 spec。
- [x] 5.2 【集成测试】运行 Server 相关测试，验证最终结构化生成、重试、超时和 generation 唯一终态没有回归。
- [ ] 5.3 运行 Server Ruff、mypy 与构建检查，记录实际结果且不修复无关存量问题。
- [ ] 5.4 运行 Web 与共享 UI 的 lint、类型检查和构建，记录实际结果且不修复无关存量问题。
