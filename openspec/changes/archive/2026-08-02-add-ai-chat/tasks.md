## 1. 后端 AI 配置

- [x] 1.1 在 `apps/api/internal/config` 增加强类型 `AIConfig`、`API_AI_*` 环境变量绑定、development 下根 `.env.local` 的 `DS_BASE_URL`/`DS_API_KEY` 缺省加载与进程环境优先规则
- [x] 1.2 增加 BaseURL、APIKey、Model、AI 请求超时及 HTTP 写超时关系校验，并同步安全的默认值与 `config/config.example.yaml`
- [x] 1.3 扩展配置测试，覆盖本地缺省来源、环境覆盖、缺失凭据、生产环境不读取本地文件和超时组合无效场景

## 2. Go 对话领域与 HTTP 接口

- [x] 2.1 在 `apps/api/internal/chat` 定义应用消息、请求/响应 DTO、稳定领域错误与消息数量、角色、内容、末条角色的提前校验
- [x] 2.2 使用 `net/http` 实现可注入的 Chat Completions 客户端，完成 URL 规范化、服务端认证、模型与非流式请求转换、响应提取、超时取消和敏感错误收敛
- [x] 2.3 实现 Gin handler 的有限请求体、JSON 解析、`400 invalid_request`、`502 ai_unavailable`、`504 ai_timeout` 与成功响应映射
- [x] 2.4 在启动流程中组装 chat client 与 handler，并在 Router 注册 `POST /api/chat`，保持健康检查行为不变
- [x] 2.5 使用单元测试和 `httptest` 覆盖合法单轮/多轮、全部输入边界、上游请求转换、非 2xx、畸形或空响应、超时、客户端取消及响应不泄露上游详情

## 3. Web 对话编排

- [x] 3.1 为 `apps/web` 添加 Zustand 运行时依赖，不将其加入 `packages/ui` 或其他 workspace 包
- [x] 3.2 在 `apps/web/next.config.js` 增加由服务端 `API_BASE_URL` 驱动的 `/backend/:path*` 同源 rewrite，并提供非敏感本地默认地址
- [x] 3.3 在 workspace 路由附近实现带明确类型的对话请求函数，校验后端成功与错误响应且不依赖共享 UI 内部路径
- [x] 3.4 使用 `zustand/vanilla` 工厂实现消息、状态、错误、失败历史、发送、重试、重置和取消动作，并通过路由局部 Provider 为每次工作台挂载创建独立 store
- [x] 3.5 使用小粒度 selector 连接工作台容器，实现单一在途请求、成功追加、失败保留及复用历史重试，不启用持久化中间件
- [x] 3.6 将 URL 中的非空 prompt 交给幂等的 store 初始化动作且只自动提交一次，并同步处理空 prompt、组件卸载取消和开发模式重复 effect 场景

## 4. 共享工作台对话界面

- [x] 4.1 为 `packages/ui` 添加 `react-virtuoso` 运行时依赖，不将虚拟列表依赖放入 `apps/web` 或其他 workspace 包
- [x] 4.2 将 `packages/ui` 的 `Workspace` 改为通过公开 Props 接收带稳定 id 的消息、状态、错误、发送与重试回调，并同步更新 Zustand 消息创建逻辑与 `apps/web` 唯一调用方
- [x] 4.3 使用 `Virtuoso` 将占位对话栏替换为动态高度的 user/assistant 虚拟消息列表，通过消息 id 提供稳定 item key，且不在共享包中执行接口请求或读取环境变量
- [x] 4.4 将等待状态、稳定错误提示、重试操作与 live region 放在虚拟视口之外，并实现位于底部时自动跟随、浏览历史时保持位置及回到底部操作
- [x] 4.5 增加受控多行输入与发送按钮，落实空白校验、等待禁用、Enter 发送、Shift+Enter 换行和发送后清空草稿
- [x] 4.6 更新 workspace CSS Module，保证虚拟列表尺寸、输入区固定、对话栏显隐与响应式布局兼容，并保留语义化列表、可访问名称和焦点状态

## 5. 验证与契约核对

- [x] 5.1 对新增和修改的 Go 文件执行 `gofmt`，运行 `go test ./...` 与 `go vet ./...`，确认后端单元测试和静态检查通过
- [x] 5.2 运行 `@repo/ui` 与 `web` 的 lint、类型检查和构建入口，确认公共 Props、Zustand store、`react-virtuoso`、局部 Provider、Next.js rewrite 与客户端代码通过现有工具链
- [x] 5.3 核对受控上游的 HTTP 自动化覆盖，并将现有工具链无法自动覆盖的长列表滚动、历史位置、键盘、读屏与窄屏布局记录为需要人工确认的风险
- [x] 5.4 检查最终 diff、公开 HTTP 契约和示例配置，确认未提交密钥、未记录消息正文、除 Zustand 与 `react-virtuoso` 外未新增运行时依赖、未修改数据库结构且未覆盖用户现有无关改动
