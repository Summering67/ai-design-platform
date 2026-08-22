## Context

现有主链路产出 final DesignDocument v2，Web 画布根据该文档渲染设计。DesignDocument 提供节点树、组件、资产、样式、布局与响应式事实；画布图片提供模型难以仅从 JSON 恢复的整体视觉信息，例如视觉层级、密度、对齐感、分组、留白和组件观感。

本能力不是 DesignDocument 的确定性编译器。它是 final DesignDocument 之后按需调用的多模态 Codegen Agent：模型理解结构和图片、制定 CodePlan、生成代码，并通过受控工具检查和修复自己的候选文件。确定性代码只负责门禁、工具执行和结果约束。

Penpot MCP 的实现证明了这一交互模式的可行性：模型既读取结构化 shape tree，也通过 `export_shape` 观察设计；代码经显式工具发送到受控执行上下文，任务具有 ID 关联、超时、响应大小限制和结构化结果。这里复用其“结构 + 视觉 + 受控工具 + 有界反馈”的原则，但不复用 Penpot 代码，也不给模型设计文件写权限或通用 shell。

仓库规范保留 `PRD → UI Design → Auto Layout` 的主顺序；Codegen 作为 Root Supervisor 的可选能力注册，不会改变前三个阶段的依赖关系。Root 只有在上下文提供画布信息且模型判断用户需要源码时才调度它。

## Goals / Non-Goals

**Goals:**

- 联合使用 final DesignDocument v2 和至少一张对应画布图片理解页面。
- 先规划再生成一个 React 函数组件 TSX 和一个同名 CSS 文件，使用 React、Tailwind CSS 与 Ant Design。
- 让 Agent 在隔离临时工作区内检查并有限次数修复自己的生成代码。
- 比较候选预览与原设计图，修复显著的结构、布局和视觉偏差。
- 产物不引用仓库私有模块或运行时 DesignDocument 解释器，可复制到满足依赖前提的真实项目。
- 对输入、工具、尝试次数、时间、诊断和输出大小建立明确边界，失败时不污染设计结果和用户项目。

**Non-Goals:**

- 不修改 UI Design Agent 或 Auto Layout Agent 的职责和输出；Root 只新增 Codegen 能力描述与自主选择入口。
- 不修复、补全、迁移或重写 DesignDocument，也不从截图反向覆盖契约事实。
- 不生成完整 Vite/Next.js 项目、`package.json`、Tailwind 配置、路由、API、状态管理或额外资源文件。
- 不承诺像素级复刻，不用视觉判断覆盖明确的文本、组件、资产和布局契约。
- 不允许模型访问任意文件路径、执行任意命令、安装依赖、访问网络或直接写入用户仓库。
- 不暴露模型思维链、完整原始诊断、失败源码、内部路径或预览环境细节。

## Decisions

### 1. Codegen 是独立的多模态 Agent

新增独立调用入口，接收：

```text
CodegenRequest
  ├─ document: final DesignDocument v2
  ├─ canvas: viewportIds + canvasId（可选）
  └─ options: componentName/fileBaseName（可选）
```

请求必须包含至少一个 viewport 的画布上下文。服务端通过受控 CanvasCapture 适配器自动读取当前画布并生成截图；调用方不再上传或拼接图片。每张截图绑定文档中存在的 viewport，尺寸必须与该 viewport 一致；同一 viewport 不得重复。运行开始时计算文档和截图的内容摘要，后续阶段只读取该冻结快照，防止一次运行混入变化后的设计。未配置捕获器时返回稳定的 `codegen_canvas_capture_unavailable` 错误。

Codegen 同时保留独立入口并注册为 Root Supervisor 的可选能力，不写数据库设计结果。Root 每轮获得用户原始目标、能力描述、已完成产物、调用历史和当前可执行能力；只有模型返回 `codegen` 且依赖满足时才执行。模型返回空任务且设计结果已完成时直接结束，不允许确定性兜底把 Codegen 强制补入。

### 2. 模型调用契约必须支持视觉输入

现有仅结构化文本的 ModelPort 不能满足本能力。新增专用于 Codegen 的多模态端口，支持由文本、结构化 JSON 和图片组成的请求，并要求配置的模型具备视觉能力。端口返回结构化 Agent action，而不是自由格式聊天文本。

模型上下文包括：

- 固定系统约束与目标技术栈；
- 完整 DesignDocument 或在输入上限内的无损结构化表示；
- viewport 元数据和对应画布图片；
- 当前 CodePlan、候选文件以及最近一次经过裁剪的工具诊断；
- 可调用工具的严格 Schema。

不得记录或对外返回隐藏推理。可观测事件只包含 `planning`、`generating`、`checking`、`reviewing`、`repairing`、`completed`、`failed` 等阶段、尝试次数、耗时和稳定错误码。

### 3. CodePlan 是内部的结构化工作产物

Agent 首次动作必须生成通过 Schema 校验的 CodePlan，至少包含：

- 页面与 viewport 范围；
- 组件和语义 HTML 的映射；
- 布局、响应式和样式策略；
- Ant Design 使用计划及 import；
- 资产使用方式；
- 预期的组件层次和风险。

CodePlan 用来约束后续生成和修复，但不是第三个输出文件。公开结果仅包含简短 `planSummary`，不包含逐步推理。计划无效时可在模型调用上限内重试，不能绕过计划直接写文件。

### 4. Agent 通过最小工具集操作候选产物

Codegen runtime 只向 Agent 暴露预定义工具：

- `write_candidate`：原子写入安全 basename 对应的 `.tsx` 和 `.css`；
- `read_candidate`：读取当前两个候选文件；
- `run_static_checks`：运行固定版本、固定参数的格式化检查、TypeScript 和 ESLint；
- `render_preview`：在固定的 React/Tailwind/Ant Design 预览壳中渲染指定 viewport 并返回图片；
- `finish`：提交当前候选作为结果。

工具由服务端实现，不接收 shell 字符串、任意路径、依赖名称或网络地址。候选文件只存在于每次运行独享的临时工作区；工具验证 basename、扩展名、文件数量、内容大小和路径解析结果。运行结束或取消后清理工作区。

与 Penpot 的代码执行工具不同，本 Agent 不需要通用 JavaScript 执行能力。更窄的工具面能满足代码生成和自检，同时避免模型生成的命令越过边界。

### 5. 生成目标固定为两个可迁移文件

一次成功结果原子返回：

- `<FileBaseName>.tsx`，默认导出 PascalCase React 函数组件；
- `<FileBaseName>.css`，由 TSX 通过 `./<FileBaseName>.css` 导入。

TSX 可从 `react` 和 `antd` 导入目标项目公开 API，可使用静态 Tailwind class；不得引用本仓库模块、临时预览壳或 DesignDocument runtime。CSS 必须由组件根 class 作用域限制，避免无边界全局规则。

Agent 可以根据设计语义选择 Ant Design 组件和 CSS/Tailwind 表达方式，不要求相同输入字节稳定。确定性结果校验仍会拒绝额外文件、非法命名、路径穿越、仓库内部 import、远程脚本、动态执行和超限内容。

DesignDocument 不包含可执行回调。Agent 不得把字符串解释为代码，也不得虚构 API 调用或业务状态；只有输入契约明确表达的交互意图才能生成局部、无外部副作用的 UI 行为。第一版没有交互契约时输出展示型组件。

### 6. JSON 是语义事实，图片是视觉证据

冲突时采用以下优先级：

1. DesignDocument 的文本、节点顺序、组件、资产引用和布局/响应式字段是必须保留的事实；
2. 画布图片用于理解组合、视觉权重和最终观感，并帮助发现 JSON 到代码表达中的偏差；
3. `resolvedLayouts` 可作为目标 viewport 的几何证据，但不得简单把整页退化为 absolute 定位；
4. 若图片与文档显著不对应，Agent 返回 `codegen_input_mismatch`，不猜测哪一个需要修改。

Tailwind 与 CSS 不使用固定的属性映射编译器。提示约束 Agent 优先用静态 Tailwind utilities 表达常规布局，用作用域 CSS 表达精确视觉值、响应式规则和必要的 Ant Design 局部覆盖，并避免同一属性冲突。

### 7. 检查和修复采用有界状态循环

运行状态如下：

```text
输入门禁 → 规划 → 生成候选 → 静态检查 ──通过──→ 视觉自检 → 完成
                         │                         │
                         └──失败→ 修复 ───────────┘
                                      视觉问题 ─→ 修复
```

静态检查是成功的强制门禁。每轮返回结构化、去重和裁剪后的诊断，包括工具名、稳定规则码、文件、行列和短消息；不把完整进程输出、绝对路径或依赖内部堆栈喂回模型。

视觉自检是强制步骤：服务端渲染与输入图片相同 viewport 的候选图，视觉模型返回按 `structure/layout/style/content` 分类的问题、严重级别和置信度。仅高置信度且与 DesignDocument 不冲突的问题触发修复。预览基础设施不可用属于稳定运行失败，不能伪装为通过。

Agent 每次修复只能改自己的 TSX/CSS，修改后必须重新跑完整静态检查；视觉修复后也必须重新生成预览。运行配置限制模型调用次数、修复轮数、单工具超时、总超时和输出字节数。达到上限仍不通过时返回稳定失败，不返回未经验证的“成功”文件。

### 8. 错误语义、取消与资源限制

稳定错误至少区分：

- `codegen_input_invalid`：DesignDocument、图片或命名不合法；
- `codegen_input_mismatch`：图片与文档/viewport 显著不对应；
- `codegen_model_unavailable`：模型不支持视觉或调用失败；
- `codegen_plan_invalid`：计划多次不符合 Schema；
- `codegen_generation_failed`：无法形成合法双文件候选；
- `codegen_verification_failed`：静态检查达到修复上限仍失败；
- `codegen_visual_mismatch`：视觉问题达到修复上限仍未收敛；
- `codegen_timeout` / `codegen_cancelled` / `codegen_limit_exceeded`。

入口限制文档与图片总大小、图片像素、节点数、深度、模型调用次数、工具调用次数、候选大小和总耗时。取消必须停止模型/工具任务并清理临时工作区。公开错误只含 code、短 message、阶段、尝试次数和可选安全定位，不含原始输入、候选源码、截图、绝对路径、堆栈或凭证。

### 9. 验证策略不依赖浏览器验收

OpenSpec 验收使用单元测试和集成测试，不安排浏览器自动化或人工浏览器验证：

- 单元测试验证请求/结果 Schema、状态转换、工具参数门禁、诊断裁剪、重试/取消和错误映射；
- 集成测试使用 fake multimodal model 与 fake preview renderer 验证计划、生成、静态修复和视觉修复闭环；
- TypeScript fixture 环境验证代表性最终 TSX/CSS 可编译；
- 预览工具本身通过输入输出契约及 renderer adapter 集成测试验证，不把真实浏览器操作列为 OpenSpec 验收任务。

## Risks / Trade-offs

- [风险] 模型输出非确定且可能漂移 → 使用结构化 CodePlan、工具 Schema、固定目标环境、强制静态门禁和有限修复；不承诺字节稳定。
- [风险] 图片与 JSON 产生冲突 → 明确 JSON 事实优先并在显著不对应时失败，不允许 Agent 反改输入。
- [风险] 视觉自评可能误报 → 只让高置信度、与契约一致的问题触发修复，并限制轮数；公开验证摘要保留未解决风险。
- [风险] 预览环境与真实项目版本不同 → 固定并公开 React/Tailwind/Ant Design 目标版本范围，产物不导入预览壳私有模块。
- [风险] 模型生成危险代码或命令 → Agent 无通用 shell/文件系统/网络工具；结果校验拒绝动态执行、远程脚本和越界 import。
- [风险] 两个文件无法携带本地二进制资产 → 仅使用 DesignDocument 中目标项目可访问的安全资产引用；资产复制不在第一版范围。
- [风险] 修复循环成本和延迟不可控 → 限制模型与工具次数、候选大小、图片像素和总时间，超限返回稳定错误。

## Migration Plan

1. 发布 Codegen 请求/结果、画布图片和验证摘要契约，不改变现有 generation API。
2. 扩展模型适配层的多模态能力，并实现隔离工作区及受控工具。
3. 实现 CodePlan、Agent 状态机、静态检查与视觉自检/修复循环。
4. 增加独立认证 API 与事件输出，并把 Codegen 作为 Root 可选能力接入；保持前三个设计阶段的依赖顺序。
5. 回滚时移除独立 API、Codegen runtime 与共享契约；DesignDocument v2 和既有 generation 数据无需迁移。

## Open Questions

无阻塞问题。第一版固定要求至少一张画布图片，并将预览环境作为部署前提执行视觉闭环；多页面拆分、自定义组件包、真实业务交互和资产打包留作后续变更。
