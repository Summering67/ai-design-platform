## Context

当前首页把用户描述放入 `/workspace?prompt=...`，`apps/web/app/workspace/page.tsx` 读取该参数后只将字符串传给共享 `Workspace`。共享工作台内部自行构造一条用户消息和永久加载占位态，没有输入框、消息模型或应用回调；`apps/web` 当前也没有状态库。Go API 已具备配置、日志、数据库和 Gin 生命周期，但路由只有健康检查。

这次变更跨越共享 UI、Next.js 应用状态、Go HTTP 边界和外部 AI 服务。上游凭据当前位于仓库根目录未提交的 `.env.local`，不能进入客户端 bundle、请求响应或日志。仓库现有 API 写超时为 10 秒，也不足以可靠覆盖一次模型请求，需要与 AI 调用超时一起协调。

## Goals / Non-Goals

**Goals:**

- 从首页 prompt 启动首轮请求，并在工作台内完成内存态多轮对话。
- 由 Go API 统一校验输入、持有凭据、调用兼容 Chat Completions 的上游，并屏蔽上游响应差异。
- 让共享工作台只负责可复用交互和展示，通过清晰的 Props/回调与应用能力连接。
- 为超时、错误映射、并发提交、密钥保护和可访问性建立明确行为。
- 后端不新增运行时依赖，优先使用已有 Viper、Gin 与 Go 标准库；前端引入 Zustand 管理对话状态，并由 `react-virtuoso` 支撑长消息列表的虚拟滚动。

**Non-Goals:**

- 不持久化会话或消息，不实现最近聊天、收藏、新建聊天等侧栏业务。
- 不实现登录、用户隔离、计费、限流或内容审核系统。
- 不实现流式输出、工具调用、推理过程展示、文件或代码生成。
- 不改变 PostgreSQL schema，也不把 AI 凭据放到 `packages/ui` 或浏览器环境。

## Decisions

### 1. 采用“受控共享 UI + Web 应用编排 + Go 领域代理”三层边界

`packages/ui` 导出稳定的 `ChatMessage`、`ChatStatus` 与 `WorkspaceProps`，接收消息、草稿提交回调和重试回调；`ChatMessage` 包含只用于前端列表身份的稳定 `id`，共享 UI 只管理输入框草稿、导航显示等纯界面状态。`apps/web` 的 workspace 路由附近使用 Zustand store 拥有消息列表、当前请求、错误、失败历史和首次 prompt 初始化逻辑，并负责创建消息 id；提交后端时只发送 role 与 content。`apps/api/internal/chat` 拥有 DTO、输入规则、上游客户端与 HTTP handler，`internal/server` 只完成依赖注入和路由注册。

Zustand store 使用 `zustand/vanilla` 工厂创建，并由 workspace 路由内的客户端 Provider 为每次工作台挂载持有独立实例；组件通过小粒度 selector 订阅所需状态。请求函数作为依赖传入 store，AbortController 保留在 store 工厂闭包中，不暴露为公共状态；Provider 卸载时调用取消动作。不开启 persist middleware，刷新后仍按无持久化语义重新初始化。

这样可保持共享包不依赖 Next.js、Zustand 或具体 API，避免服务端模块级单例在请求间共享会话，也避免把 Gin context 传入业务或上游客户端。备选方案是让 `Workspace` 自己 `fetch`，或在模块顶层创建全局 Zustand hook；前者会让共享 UI 耦合业务契约，后者存在 SSR 请求间状态污染风险，因此均不采用。

### 2. 浏览器使用同源路径，由 Next.js rewrite 转发到 Go API

客户端请求相对路径 `/backend/api/chat`。`apps/web/next.config.js` 使用仅服务端可见的 `API_BASE_URL` 将 `/backend/:path*` rewrite 到 Go API，本地提供非敏感的 `http://localhost:8080` 默认值。这样无需在 Go API 中扩大 CORS 范围，也不需要创建只有一层转发逻辑的 Route Handler。

备选方案是暴露 `NEXT_PUBLIC_API_BASE_URL` 并让浏览器跨域访问 Go API；这需要额外的允许来源配置和 CORS 中间件，部署面更大，因此不采用。

### 3. 定义稳定、非流式的应用对话契约

`POST /api/chat` 接收：

```json
{
  "messages": [
    { "role": "user", "content": "创建一个作品集网站" },
    { "role": "assistant", "content": "你偏好什么风格？" }
  ]
}
```

角色只允许 `user` 和 `assistant`，消息必须非空、按时间排序，最后一条必须是 `user`。Handler 使用有限请求体，并限制最多 50 条消息及单条内容最多 32000 个字符；不合法请求在任何上游调用前返回 `400`。成功响应只暴露稳定字段：

```json
{
  "message": { "role": "assistant", "content": "..." }
}
```

错误使用 `{"error":{"code":"...","message":"..."}}`：输入错误映射为 `400 invalid_request`，上游拒绝、非预期响应或网络失败映射为 `502 ai_unavailable`，调用超时映射为 `504 ai_timeout`。响应与日志均不透传上游原始错误体。

首版使用一次性 JSON 响应。相比 SSE，非流式契约更容易在当前尚无对话基础设施的仓库中建立边界、重试和测试；流式体验可作为后续独立变更。

### 4. 后端每轮接收完整历史，服务端不持久化

Web 在每次提交时发送截至当前用户消息的完整 `user`/`assistant` 历史，Go API 原样转换为上游消息。上游返回的首个有效 assistant 文本被规范化为应用响应，Web 再追加到本地列表。刷新页面会丢失内存态历史；若 URL 仍有 prompt，则它会重新开始首轮对话。

这能在没有会话表、用户身份和迁移的情况下提供真正的多轮上下文。备选方案是立即在 PostgreSQL 保存 conversation ID 与消息；缺少认证时无法正确界定所有权，因此延期。

### 5. 用强类型 AI 配置统一当前本地变量与部署变量

`internal/config` 新增 `AIConfig`：BaseURL、APIKey、Model 与 RequestTimeout。部署使用符合现有规范的 `API_AI_BASE_URL`、`API_AI_API_KEY`、`API_AI_MODEL`、`API_AI_REQUEST_TIMEOUT`；为兼容用户现有本地配置，开发环境可通过 Viper 的独立 dotenv reader 从仓库根 `.env.local` 读取 `DS_BASE_URL` 与 `DS_API_KEY` 作为缺省来源，真实进程环境变量始终优先。生产环境不自动读取仓库文件。

Model 使用非敏感默认值 `deepseek-v4-flash`，仍可由配置覆盖；BaseURL 与 APIKey 没有默认值，缺失时阻止启动。上游地址由规范化后的 BaseURL 追加 `/chat/completions`，客户端用服务端凭据认证。AI 请求超时默认 60 秒，同时将示例和默认的 HTTP 写超时调整为大于 AI 超时，并在配置校验中阻止不一致的组合。

备选方案是让前端直接使用 `DS_API_KEY`；任何公开前缀或浏览器请求都会暴露密钥，因此禁止。

### 6. 上游客户端使用标准库并保持可替换接缝

`internal/chat` 使用注入的 `*http.Client` 与配置构造上游 client，不引入厂商 SDK。Service/Handler 侧只依赖最小的 `Complete(ctx, messages)` 接口，以便通过本地 `httptest.Server` 覆盖请求转换、认证、超时、非 2xx、畸形 JSON 与空回复。日志只包含稳定错误类别、状态和耗时，不记录消息、完整 URL 查询或凭据。

厂商 SDK 能减少 DTO 代码，但会引入额外依赖并把应用契约绑定到特定版本；当前只需兼容标准 Chat Completions 子集，标准库更合适。

### 7. Zustand store 显式建模提交、等待、成功与失败

Store 状态包含 `messages`、`status`、`error` 与重试所需的失败历史，动作包含初始化 prompt、发送、重试、重置和取消。异步动作在读取状态后先提前判断空内容或已有在途请求；提交时立即追加 user 消息并清除错误，成功时追加 assistant 消息，失败时保留已发送消息与失败历史。重试复用同一份历史，不重复追加 user 消息。等待期间输入区和发送动作禁用，避免历史分叉。

首次非空 prompt 通过幂等的 `initializePrompt` 动作自动提交一次，由 store 记录已初始化值，避免 React 开发模式重复 effect 产生重复请求。UI 容器只使用 selector 读取 `messages`、`status`、`error` 和稳定动作，再转换为共享 `Workspace` 的受控 Props。

共享 UI 在消息区底部提供多行输入框和发送按钮：空白内容不能发送，Enter 发送、Shift+Enter 换行；状态与错误通过可感知的 live region 呈现。虚拟消息列表根据用户是否停留在底部决定是否跟随新消息，不强制打断正在浏览历史的用户，也不改变键盘焦点。

### 8. 使用 react-virtuoso 虚拟化消息列表

`packages/ui` 直接声明并使用 `react-virtuoso`，因为虚拟列表属于共享 `Workspace` 的渲染职责，而不是 `apps/web` 的业务状态职责。对话栏使用 `Virtuoso` 的 `data` 与 `itemContent` 渲染不同高度的 user/assistant 消息，通过 `computeItemKey` 使用 `ChatMessage.id` 保持节点身份稳定；输入区、等待态和错误重试区放在虚拟滚动视口之外，避免列表回收影响输入焦点或 live region。

列表用底部状态控制自动跟随：用户位于或接近底部时，新消息到达后平滑跟随到底部；用户向上浏览历史时保持当前位置，并提供回到底部操作。空会话继续显示独立空状态，不挂载无数据的虚拟列表。通过 Virtuoso 的语义化 List/Item 组件覆盖保留消息列表结构和可访问名称。

备选方案是继续用 `map` 渲染全部消息；它实现简单，但消息正文可能很长，随着多轮对话增长会持续增加 DOM 节点和布局成本，因此按用户要求采用专门处理动态高度内容的虚拟列表。

## Risks / Trade-offs

- [非流式响应在较慢模型下反馈感较弱] → 持续展示明确的等待状态，并用 60 秒有界超时；流式输出另立变更。
- [完整历史会随轮次增长并增加费用与延迟] → 首版限制消息数量和请求体大小；达到上限时在发起上游调用前返回稳定错误。
- [本地 `.env.local` 的发现依赖仓库布局] → 仅在 development 使用受限的仓库根查找，生产必须使用进程环境；测试显式注入临时配置来源。
- [上游模型名与响应字段可能变化] → 模型可配置，客户端只依赖最小兼容字段，并将不符合契约的响应转换为稳定的 502。
- [HTTP write timeout 调大影响所有 API 请求] → 仍保持有限值，并校验其只比 AI timeout 略长；后续若业务扩展可对 AI 路由采用独立 server 策略。
- [刷新会重新发送 URL prompt，可能产生重复费用] → 这是无持久化 MVP 的已知限制；页面文案不承诺恢复历史，持久化留待认证后设计。
- [Zustand store 若使用模块级单例可能在 SSR 请求间共享状态] → 使用 vanilla store 工厂和路由局部 Provider，每次工作台挂载创建独立实例且不启用持久化中间件。
- [虚拟列表会回收离屏消息节点，页面查找和辅助技术连续读取可能受影响] → 保留语义化列表结构、稳定 item key 和独立 live region；当前缺少组件测试入口，键盘、读屏、长列表滚动和窄屏布局列为需要人工确认的风险。
- [动态高度消息或容器显隐可能造成滚动位置跳变] → 由 Virtuoso 测量内容高度，使用底部状态决定跟随行为，并验证对话栏隐藏、恢复和窄屏布局场景。

## Migration Plan

1. 先扩展并验证后端配置与 AI client，再注册 `/api/chat`；凭据继续保留在未提交的本地文件或部署环境中。
2. 为 `apps/web` 安装 Zustand，为 `packages/ui` 安装 `react-virtuoso`，增加 Next.js rewrite、路由局部 store Provider 和对话动作，再调整共享 `Workspace` 公共 Props与虚拟消息列表，并同步更新唯一调用方。
3. 运行 Go 测试、Go vet、相关 lint/type check/build，并通过受控上游的 HTTP 自动化测试验证首轮、多轮、失败重试和响应不包含密钥。
4. 部署时先配置 API 进程的 AI 环境变量与 Web 的 `API_BASE_URL`，再上线 Web。回滚可同时移除 rewrite、前端交互和 `/api/chat`，不涉及数据回滚。

## Open Questions

无。首版采用可配置模型、非流式响应与 Zustand 内存态历史；持久化、认证和流式输出均作为后续能力处理。
