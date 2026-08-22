## Purpose

为设计文档提供受约束、可验证且可迁移的多模态代码生成能力。

## Requirements

### Requirement: 独立的多模态 Codegen Agent

系统 SHALL 提供独立 Codegen Agent，联合 final DesignDocument v2 与自动捕获的画布图片规划、生成和修复源码。Codegen Agent SHALL 作为 Root Supervisor 的可选任务注册；Root 仅在存在 final document 和画布上下文、且模型选择代码生成时调度它。Codegen Agent MUST NOT 修改 generation 状态、输入文档、画布图片或既有 `PRD → UI Design → Auto Layout` 结果。

#### Scenario: JSON 与自动捕获的画布图片共同进入模型

- **WHEN** 调用方提交合法 final DesignDocument 和 viewport 画布上下文
- **THEN** 服务端通过受控 CanvasCapture 适配器自动读取对应画布图片，并将 JSON 与图片共同交给视觉模型

#### Scenario: 画布捕获器不可用

- **WHEN** 当前运行没有配置可用的 CanvasCapture 适配器
- **THEN** 系统返回 `codegen_canvas_capture_unavailable`，不调用模型且不生成候选文件
- **THEN** Codegen Agent 的多模态模型请求同时包含结构化设计上下文和图片内容，而不是仅按 JSON 执行确定性转换

#### Scenario: Codegen 失败不污染设计结果

- **WHEN** 规划、生成、静态检查或视觉检查失败
- **THEN** 系统保留原 DesignDocument 和画布快照，不启动上游 Agent 重试且不修改 generation 终态

### Requirement: 冻结且严格的输入上下文

Codegen Agent SHALL 在规划前验证 DesignDocument v2 Schema、引用完整性、Profile、唯一 ID 和树语义，并验证图片格式、字节数、像素、viewport ID 与尺寸。每次运行 MUST 固定文档和图片的内容摘要，后续步骤不得读取漂移后的输入。Agent MUST NOT 修 JSON、补字段、迁移版本或用图片覆盖明确契约事实。

#### Scenario: 非法文档或图片被提前拒绝

- **WHEN** 文档不合法，或图片缺失、格式不支持、超限、viewport 不存在或尺寸不匹配
- **THEN** Codegen Agent 返回稳定 `codegen_input_invalid` 且不调用模型、不创建候选文件

#### Scenario: 图片与文档显著不对应

- **WHEN** 多模态分析确认画布图片与声明 viewport 或文档内容显著不一致
- **THEN** Agent 返回 `codegen_input_mismatch`，不猜测并修改其中任一输入

#### Scenario: 运行期间输入发生变化

- **WHEN** 后续工具步骤观察到输入摘要与运行开始时不同
- **THEN** Agent 终止本次运行并返回稳定输入漂移错误，不混合两个版本继续生成

### Requirement: 先规划后生成

Codegen Agent SHALL 在写入候选文件前生成通过内部 Schema 校验的 CodePlan。CodePlan MUST 覆盖组件层次、语义元素、布局与响应式策略、Ant Design 使用、样式分工、资产和风险。无合法 CodePlan 时 Agent MUST NOT 生成源码。

#### Scenario: 合法计划驱动代码生成

- **WHEN** Agent 已联合分析 DesignDocument 与画布图片
- **THEN** Agent 先保存结构化 CodePlan，再依据该计划生成首版 TSX/CSS 候选

#### Scenario: 计划多次无效

- **WHEN** 模型在允许的计划尝试次数内仍未返回符合 Schema 的 CodePlan
- **THEN** Agent 返回 `codegen_plan_invalid`，且不调用候选写入和验证工具

#### Scenario: 公开结果不泄露思维链

- **WHEN** Codegen 成功或失败
- **THEN** 对外仅返回简短计划摘要和阶段信息，不返回隐藏推理或完整内部 CodePlan 历史

### Requirement: 受控候选工作区与工具

系统 SHALL 为每次运行创建独享隔离临时工作区，并仅向 Agent 暴露具备严格输入 Schema 的候选读写、固定静态检查、预览渲染和完成工具。Agent MUST NOT 获得通用 shell、任意文件系统、网络或依赖安装能力。运行完成、取消或失败后 SHALL 清理工作区。

#### Scenario: Agent 原子写入双文件候选

- **WHEN** Agent 调用候选写入工具并提供同 basename 的 TSX/CSS
- **THEN** 工具在验证文件名、扩展名、数量和内容大小后原子替换当前候选

#### Scenario: 路径逃逸或任意命令被拒绝

- **WHEN** 模型尝试使用绝对路径、`..`、额外文件、shell 命令、网络地址或安装依赖
- **THEN** 工具层在执行前拒绝请求并返回稳定安全诊断

#### Scenario: 取消释放运行资源

- **WHEN** 调用方取消正在进行的 Codegen
- **THEN** 系统停止模型和工具任务、清理临时工作区并返回 `codegen_cancelled`

### Requirement: 固定且可迁移的双文件产物

一次成功 Codegen SHALL 原子返回恰好两个 UTF-8 文本文件：一个 `.tsx` React 函数组件和一个同 basename 的 `.css` 文件。TSX MUST 相对导入该 CSS、默认导出合法 PascalCase 组件，并且 MUST NOT 引用仓库内部模块、预览壳、DesignDocument 运行时解释器或未允许的包。

#### Scenario: 生成 React、Tailwind CSS 与 Ant Design 代码

- **WHEN** 设计包含可用语义 HTML、常规布局和 Ant Design 组件
- **THEN** Agent 生成使用 React、静态 Tailwind class、按需 Ant Design import 与作用域 CSS 的两个文件

#### Scenario: 真实项目迁移边界

- **WHEN** 调用方把两个文件复制到已配置 React、Tailwind CSS 和 `antd` 的目标项目
- **THEN** 文件不需要本仓库私有依赖或服务端运行时即可参与目标项目编译

#### Scenario: 非法名称或半成品被拒绝

- **WHEN** 文件名含路径穿越/扩展名注入，或候选缺少任一文件
- **THEN** 结果校验失败且不返回成功产物

### Requirement: 契约事实与视觉证据的优先级

Agent SHALL 保留 DesignDocument 明确声明的文本、节点顺序、组件、资产、布局和响应式事实，并使用图片理解视觉层次、组合、留白和最终观感。Agent MUST NOT 因视觉猜测删除或改写明确契约内容，也不得把所有 `resolvedLayouts` 直接转换成整页 absolute 定位。

#### Scenario: 图片帮助选择代码表达

- **WHEN** JSON 可由多种等价 React/CSS 结构表达而图片呈现明确的视觉分组和层级
- **THEN** Agent 使用图片证据选择更符合设计稿且可维护的组件和样式表达

#### Scenario: 视觉推断与明确事实冲突

- **WHEN** 图片观感与 DesignDocument 的明确文本、组件或资产引用冲突但未达到整体输入不匹配
- **THEN** Agent 保留 DesignDocument 事实，并在验证摘要中记录视觉不确定性

#### Scenario: 布局保持可迁移

- **WHEN** 文档包含 `layout/layoutItem/responsive` 和 viewport 几何快照
- **THEN** Agent 生成可维护的 Flex/Grid/响应式代码，不把整页退化为逐节点 absolute 坐标复刻

### Requirement: 安全且受约束的源码语义

Agent SHALL 只生成展示当前设计所需的源码，MUST NOT 把 JSON 字符串解释为可执行代码、生成动态执行、远程脚本、凭空构造的 API 调用或未声明业务状态。CSS SHALL 使用组件根作用域约束局部样式和 Ant Design 覆盖。

#### Scenario: 无交互契约时生成展示型组件

- **WHEN** DesignDocument 未声明可执行交互意图
- **THEN** Agent 不虚构事件回调、请求、全局状态或导航逻辑

#### Scenario: 字符串代码不被执行

- **WHEN** props 或文本包含看起来像 JavaScript 的字符串
- **THEN** 生成代码把它作为数据安全表达，不转换为函数体、表达式或动态执行入口

#### Scenario: Ant Design 样式保持局部

- **WHEN** 候选需要覆盖 Ant Design 内部样式
- **THEN** CSS selector 包含组件根作用域，不生成影响宿主项目其他组件的无界全局规则

### Requirement: 强制静态检查与自动修复

Agent SHALL 在候选生成后运行固定版本、固定参数的格式化检查、TypeScript 和 ESLint。任一强制检查失败时，系统 SHALL 向模型提供经过结构化、去重、脱敏和裁剪的诊断，并允许 Agent 只修改自己的 TSX/CSS 后重新执行全部强制检查，直到通过或达到上限。

#### Scenario: 类型错误被 Agent 修复

- **WHEN** 首版 TSX 产生可修复的 TypeScript 或 Ant Design props 类型错误
- **THEN** Agent 接收文件/行列/规则码/短消息，修改候选并重新运行全部静态检查

#### Scenario: 诊断不泄露内部信息

- **WHEN** 检查进程输出包含绝对路径、堆栈或冗长依赖信息
- **THEN** 返回模型和调用方的诊断移除敏感内容并受数量与字节上限约束

#### Scenario: 静态修复未收敛

- **WHEN** 达到最大修复轮数后仍有强制检查失败
- **THEN** Agent 返回 `codegen_verification_failed`，不把最后候选标记为成功且不修改输入设计

### Requirement: 预览与多模态视觉自检

部署环境 SHALL 提供受控 preview renderer，将当前候选在输入 viewport 下渲染为图片。静态检查通过后，视觉模型 SHALL 比较候选预览与原画布图片，返回按结构、布局、样式和内容分类的结构化问题。仅高置信度且不违反 DesignDocument 事实的问题 SHALL 触发修复。

#### Scenario: 视觉偏差触发修复闭环

- **WHEN** 候选通过静态检查，但视觉审查发现高置信度的阻断级布局或样式偏差
- **THEN** Agent 修改 TSX/CSS、重新运行全部静态检查、重新渲染并再次视觉审查

#### Scenario: 视觉误报不得覆盖契约

- **WHEN** 视觉审查建议的修改会删除明确文本、替换组件或违背布局契约
- **THEN** Agent 拒绝该建议并保留 DesignDocument 事实

#### Scenario: 视觉修复未收敛

- **WHEN** 达到最大视觉修复轮数后仍存在阻断问题
- **THEN** Agent 返回 `codegen_visual_mismatch`，不把候选标记为成功

#### Scenario: 预览基础设施不可用

- **WHEN** preview renderer 超时或不可用
- **THEN** Agent 返回稳定运行失败，不伪造视觉检查通过结果

### Requirement: 有界运行、稳定错误与验证摘要

系统 SHALL 限制输入总字节、图片像素、节点数、深度、模型调用、工具调用、修复轮数、候选大小、单步超时和总耗时。成功结果 SHALL 包含阶段、尝试次数、已通过检查和未阻断风险的验证摘要；失败 SHALL 返回稳定错误码。公开响应 MUST NOT 包含完整输入、失败源码、截图、隐藏推理、堆栈、内部路径或凭证。

#### Scenario: 达到资源或时间上限

- **WHEN** 运行超过任一配置上限
- **THEN** Agent 尽快停止并返回 `codegen_limit_exceeded` 或 `codegen_timeout`，且不返回未经验证的成功文件

#### Scenario: 成功结果具有可核验摘要

- **WHEN** 静态检查和视觉自检均通过
- **THEN** 结果原子包含两个文件、简短计划摘要，以及检查名称、尝试次数和未阻断风险，不包含内部执行细节

#### Scenario: Root 模型自主决定是否调用 Codegen

- **WHEN** final DesignDocument 和画布上下文均已就绪，Root 再次评估用户原始目标、能力说明、已完成产物和调用历史
- **THEN** 仅当模型选择 `codegen` 时调用 Codegen Agent；模型返回空任务时直接交付设计结果，不通过确定性兜底强制调用 Codegen；Codegen 成功时在保留原 DesignDocument 结果的基础上追加代码产物

#### Scenario: Root 拒绝未就绪或未知能力

- **WHEN** 模型选择未知 Agent 或当前依赖尚未满足的能力
- **THEN** Root 返回稳定调度错误，不静默替换为固定任务，也不猜测用户意图
