## Why

当前工作台的对话栏只有静态占位状态，用户从首页提交描述后无法获得 AI 回复或继续追问。需要打通 `apps/web`、共享工作台 UI 与 `apps/api`，在不向浏览器暴露上游密钥的前提下提供可用的多轮 AI 对话。

## What Changes

- 在 Go API 中新增 AI 对话领域能力与 `POST /api/chat` 接口，由后端校验消息、调用上游兼容 Chat Completions 的服务，并返回稳定的应用响应。
- 将已有 `DS_BASE_URL`、`DS_API_KEY` 纳入后端强类型配置与启动校验；密钥只在服务端使用，不写入响应或日志。
- 在 `apps/web` 引入 Zustand 管理对话消息、请求状态、错误与重试动作，把首页传入的首条 prompt 自动作为首轮消息发送，并支持用户继续发送多轮消息。
- 将 `packages/ui/src/blocks/workspace/index.tsx` 的占位对话栏改为受控的通用对话界面，通过 Props 与回调接收消息、加载状态、错误状态和发送动作，并使用 `react-virtuoso` 虚拟化渲染消息列表，不直接访问接口或环境变量。
- 为后端配置、上游调用和 HTTP 契约补充自动化测试，并对前端对话状态和共享 UI 交互执行类型、静态与构建验证；现有工具链无法自动覆盖的视觉和交互行为列为人工确认风险。
- 本次不持久化聊天记录，不加入用户认证、会话列表管理、文件生成或数据库结构变更。

## Capabilities

### New Capabilities

- `ai-chat`: 覆盖安全的服务端 AI 代理、稳定的对话 HTTP 契约、多轮消息处理，以及工作台中的发送、加载、回复与错误交互。

### Modified Capabilities

无。

## Impact

- 影响 `apps/api/internal/config`、`apps/api/internal/server` 及新增的 AI 对话领域模块，并扩展 API 示例配置。
- 影响 `apps/web/app/workspace` 附近的应用级对话状态与 API 调用代码，并为 `apps/web` 新增 Zustand 运行时依赖。
- 影响 `packages/ui/src/blocks/workspace` 的公共 Props、对话栏结构和样式，并为 `packages/ui` 新增 `react-virtuoso` 运行时依赖；现有 `Workspace` 调用方需要同步适配。
- 新增公开 HTTP 接口 `POST /api/chat`，但不修改数据库结构。
- 上游调用优先使用 Go 标准库 `net/http`，后端不新增运行时依赖；前端新增当前需求实际使用的 Zustand 与 `react-virtuoso`。
