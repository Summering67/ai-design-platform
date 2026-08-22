# apps/server 开发规范

## 技术栈

- FastAPI + Starlette，Uvicorn 仅作为独立进程入口。
- Pydantic Settings + PyYAML：配置只在 `config.py` 解析，业务模块不得直接读取环境变量或 YAML。
- 配置来源为默认值、YAML、`apps/server/.env`、根目录开发兼容变量、进程环境 `API_*`；数据库 DSN 使用 SQLAlchemy/psycopg URL 格式，Go 配置不在 Python 层复用。
- SQLAlchemy 2 AsyncEngine/AsyncSession + psycopg 3 async driver。
- Python 标准 `logging` + 集中 JSON formatter/Filter。
- HTTPX、jsonschema、uv、Ruff、mypy、pytest。

## 数据库

- SQLAlchemy Model 与 Pydantic DTO 分离；每个请求使用独立 `AsyncSession`。
- 事务由领域服务显式控制；不得跨并发任务共享 Session，不依赖隐式 lazy loading。
- 数据库或 SQLAlchemy 异常必须在边界转换为稳定领域错误，不暴露 SQL、DSN 或堆栈。

## HTTP 与生命周期

- 路由按领域放入 `APIRouter`，应用工厂负责注册。
- 认证通过 `Depends` 注入当前用户；业务逻辑不得依赖 FastAPI Request/Response。
- `lifespan` 管理 AsyncEngine、Session factory 和 HTTPX client，并存入 `app.state`。
- Pydantic 请求模型使用 `extra="forbid"`；validation/领域异常统一转换为现有 API 错误结构。
- SSE 使用 `StreamingResponse`，客户端断开必须取消上游并终结 generation。

## UI 生成 Agent 职责边界

项目生成流水线固定为：

```text
PRD
  → UI Design Agent
  → InitialUIDocument
  → Auto Layout Agent
  → final DesignDocument
```

禁止增加 Specification、独立 Compiler、Layout Engine 或 Final Gate Agent/任务。确定性编译器、Flex 布局引擎和 Harness 只能作为两个 Agent 的内部普通模块。

### UI Design Agent

UI Design Agent 负责：

- 图层节点、稳定 ID、父子层级和节点顺序。
- 组件选择、内容、业务 props、交互意图和资源引用。
- 颜色、字体、边框、阴影、圆角等非布局视觉样式。
- 必要的容器语义和布局意图，但不得提前生成最终排版参数。

UI Design Agent 禁止决定或生成：

- `direction`、`wrap`、`justifyContent`、`alignItems`、`alignSelf`。
- `gap`、`rowGap`、`columnGap`、布局 `padding` 和响应式断点。
- `fixed`、`fill`、`hug`、`flexGrow`、`flexShrink`、`flexBasis`。
- 最终 `layout`、`layoutItem`、`responsive`、布局 style 投影或 `computedLayout` 坐标。

InitialUIDocument Schema 不得强制 UI Design Agent 填写上述最终布局字段。若需要传递布局偏好，必须使用专门的布局意图字段，并保持其为非几何、非最终排版语义。

### Auto Layout Agent

Auto Layout Agent 负责：

- 在内部将合法 InitialUIDocument 确定性编译为 DesignDocument。
- 根据既有图层结构、布局要求和布局意图生成、校验并应用 LayoutPlan。
- 接收固定 viewport 与独立 measurement 输入，由内部纯函数 Flex 模块为每个 viewport 生成完整 `resolvedLayouts` Geometry 快照。
- 生成 Flex 的方向、换行、对齐、间距、内边距、尺寸策略和响应式规则。
- 将布局事实写入 `layout`、`layoutItem`、`responsive`，将 Geometry 写入 `resolvedLayouts`；Renderer 只消费 Geometry。
- 返回通过完整契约及渲染门禁的 final DesignDocument。

Auto Layout Agent 禁止创建、删除、移动、重排或重新挂载节点，禁止修改稳定 ID、组件、内容、业务 props 和非布局视觉样式；模型不得生成 `computedLayout`、`resolvedLayouts` 或其他几何坐标。

### Harness

Harness 只负责模型调用、候选校验、短错误摘要和有限重试。Harness 不是 Agent，不得修改 UI 图层结构、重写 DesignDocument、生成 LayoutPlan 或计算坐标，也不得把完整错误响应或失败候选再次传给模型。

### Multimodal Codegen Agent

Codegen Agent 是 final DesignDocument 之后按需调用的独立能力，并作为 Root Supervisor 的可选能力注册，不得改变 `PRD → UI Design → Auto Layout` 的依赖顺序。Root 必须根据用户原始目标、能力描述、已完成产物、调用历史和当前可执行能力决定是否调用；禁止用固定任务兜底强制调用 Codegen。它同时接收只读 DesignDocument 和 viewport 画布图片，先生成 CodePlan，再在隔离临时工作区生成 React/Tailwind CSS/Ant Design 的 TSX/CSS 候选。

Codegen Agent 可以通过受控工具检查和修复自己生成的 TSX/CSS，并在预览环境中进行视觉审查；它不得修改 DesignDocument、画布快照、generation 状态、用户仓库或上游 Agent 输出。工具层只允许固定检查、候选文件读写和预览渲染，不允许模型执行任意 shell、访问任意路径、安装依赖或访问网络。

## 检查

使用 `uv` 及已提交 `uv.lock` 管理依赖。相关测试、静态检查、类型检查和构建结果必须实际记录在迁移队列中。
