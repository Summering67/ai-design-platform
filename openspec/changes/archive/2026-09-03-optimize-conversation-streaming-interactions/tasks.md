## 1. 流式状态基础

- [x] 1.1 在 `apps/web/app/workspace` 增加函数式帧缓冲模块，为 reasoning 事件与 assistant 文本提供有序 enqueue、提交、丢弃和卸载清理能力。
- [x] 1.2 【单元测试】覆盖同帧合并、跨帧顺序、空增量、显式提交、终态丢弃、重复清理和卸载后不再更新。
- [x] 1.3 将 `workspace-chat.tsx` 的 reasoning 定时器和逐 chunk assistant `setState` 接入帧缓冲，保证完成事件先应用 reasoning 前序增量，正式助手消息替换全部临时文本。
- [x] 1.4 【集成测试】覆盖发送、回答、重试、完成、失败、中断、主动停止和卸载时两条临时通道的发布与清理顺序。

## 2. Workspace 显式流式接口

- [x] 2.1 调整 `Workspace` Props，分离持久化 `messages` 与显式 `streamingMessage`，移除通过特殊消息 ID `streaming` 推断临时状态的逻辑。
- [x] 2.2 使用持久化消息 ID、临时消息 ID 和 reasoning ID 组成稳定的 Virtuoso 数据与 key，同步 `WorkspaceChat` 调用方及所有组件 fixture。
- [x] 2.3 【组件集成测试】验证 reasoning 与临时助手正文的排列、持久化消息不被改写、稳定 key 以及空流式内容不创建条目。

## 3. Reasoning 披露交互

- [x] 3.1 将 reasoning 展示实现为默认折叠的受控披露行，运行中取最新非空行摘要，完成或截断后取首个非空行摘要，并在 chunk 更新时保持用户展开状态。
- [x] 3.2 隐藏 Agent 名称、任务 ID、内部阶段键和尝试次数，保留通用运行/完成标题、完整原文及截断提示。
- [x] 3.3 完成披露行的整行点击、Enter/空格键切换、`aria-expanded`、焦点保持和简短运行状态播报，避免每个 chunk 重复播报完整正文。
- [x] 3.4 调整 CSS Module 中的状态点、低对比度扫光、摘要截断、正文缩进和展开箭头，并在 `prefers-reduced-motion` 下禁用非必要动画。
- [x] 3.5 【组件集成测试】覆盖默认折叠、鼠标与键盘展开、运行中最新行、完成后首行、流式重渲染状态保持、截断提示、内部身份隐藏和焦点保持。

## 4. 滚动与长对话

- [x] 4.1 复用 `react-virtuoso` 的底部状态与 `followOutput`，确认 reasoning 展开和帧级增量仅在用户接近底部时跟随，离开底部后保留阅读位置及“最新消息”操作。
- [x] 4.2 【组件集成测试】使用 Virtuoso 测试替身覆盖底部跟随、历史阅读期间不跟随、回到底部操作、reasoning 动态高度和大量稳定 ID 条目。

## 5. 测试工具与验证

- [x] 5.1 确认 workspace 仍缺少 TSX DOM 测试工具后，仅向 `packages/ui` 增加 `vitest` 与 `jsdom` 开发依赖，并复用 React DOM 测试接口，不新增生产依赖、浏览器测试或测试命令脚本。
- [x] 5.2 【单元测试】运行 reasoning 聚合与帧缓冲测试，确认原始字符、任务尝试隔离、完成、截断和清理行为。
- [x] 5.3 【集成测试】运行 Workspace 对话组件测试，确认披露、键盘、焦点、流式排列和滚动策略。
- [x] 5.4 运行受影响文件格式化、`@repo/ui` 与 Web 的 lint、类型检查及 Web 构建；只记录与本变更无关的既有失败，不扩大修复范围。
- [x] 5.5 检查最终依赖与 diff，确认未修改 SSE/HTTP/数据库契约，未持久化 reasoning，未引入未使用代码或 `@deepseek-ai/dsh-*` 依赖。
