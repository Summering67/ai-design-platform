## Why

当前工作台虽然能够接收 reasoning 与助手文本增量，但思考过程、生成状态和最终回答分别更新，展开状态与滚动行为缺少一致规则，高频 chunk 还会造成不必要的 React 更新。需要将对话流整理为稳定、可访问且不会打断用户阅读的流式交互，同时继续遵守 reasoning 不持久化、不进入消息历史的安全边界。

## What Changes

- 将运行中的 reasoning 显示为默认折叠的轻量“正在思考”披露行，折叠态展示最新非空行，用户可通过整行点击或键盘展开完整原文。
- reasoning 完成后保留用户的展开选择，折叠摘要切换为首个非空行；截断时明确说明内容已达到展示上限。
- 不向用户展示 Agent 名称、任务 ID、内部阶段键或尝试次数，reasoning 始终与正式助手消息保持视觉和语义分离。
- 统一 reasoning 与助手正文增量的帧级缓冲提交，保持字符顺序与原始内容不变，减少高频渲染。
- 明确虚拟列表的滚动所有权：用户位于底部时跟随新内容，浏览历史时保持阅读位置并提供回到底部操作。
- 补充折叠、键盘、流式重渲染、截断、焦点和滚动策略的单元或组件集成测试。
- 不引入 `deepseek-harness` 的 Cordis、插件、会话持久化或 reasoning 回放架构，不新增生产依赖。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `ai-chat`: 调整 Web reasoning 的展示时机、披露交互、流式缓冲、滚动跟随和可访问性要求。
- `agent-run-observability`: 将 reasoning 完成事件的含义从“首次允许展示”调整为“结束运行态并固定摘要”，同时保留临时传输与禁止持久化要求。

## Impact

- 前端编排：`apps/web/app/workspace/workspace-chat.tsx`、`reasoning.ts` 及相关测试。
- 共享展示：`packages/ui/src/blocks/workspace/index.tsx`、`workspace.module.css` 及组件测试。
- 契约：为 `ai-chat` 和 `agent-run-observability` 创建 delta specs；不改变 SSE 事件结构、HTTP 路由、数据库结构或 DesignDocument。
- 依赖：复用 React、`lucide-react` 与 `react-virtuoso`；生产依赖保持不变。若现有测试工具无法覆盖交互，仅评估加入最小前端测试开发依赖。
