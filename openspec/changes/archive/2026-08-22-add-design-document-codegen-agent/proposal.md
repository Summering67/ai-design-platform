## Why

平台当前只能交付 final DesignDocument v2 和画布视觉结果，不能把二者进一步转成可迁入真实 React 项目的源码。仅按 JSON 字段做确定性映射无法利用设计稿中的视觉层次、留白、组合方式和组件表达，也不能在生成代码出现类型、格式或视觉偏差时自行分析并修复。因此需要新增一个真正使用视觉模型、具有规划和受控工具循环的 Codegen Agent。

## What Changes

- 新增独立于现有设计生成主链路的多模态 Codegen Agent，同时接收通过校验的 final DesignDocument v2 和与 viewport 对应的画布图片。
- Agent 先联合理解 JSON 语义与设计稿视觉信息，形成内部 CodePlan，再生成一个 React `.tsx` 文件和一个同名 `.css` 文件；目标技术栈固定为 React、Tailwind CSS 和 Ant Design。
- Agent 通过受控工具在隔离临时工作区写入候选文件，运行格式化、TypeScript、ESLint 等预定义检查，并根据有限诊断自动修复自己的代码；不执行模型给出的任意命令，也不写入用户项目。
- 建立受控的视觉自检：预览环境渲染候选组件并返回预览图，由视觉模型与输入设计稿比较并生成结构化问题，再进入同一个有上限的修复循环；预览能力是该 Agent 的运行前提。
- 固定成功输出仍为两个可迁移 UTF-8 文本文件，并附带不含思维链的计划摘要和验证摘要；CodePlan、候选版本、原始诊断和预览图仅作为内部运行状态。
- 明确输入与修复边界：Agent 可以修改自己生成的 TSX/CSS，但不得修改 DesignDocument、画布图片、上游 generation 状态，也不得调用 UI Design 或 Auto Layout Agent 返工。
- 保留确定性模块作为 Agent 工具与安全边界，用于输入校验、安全命名、文件读写、诊断裁剪、输出契约校验和资源限制，而不是把它们作为核心代码生成器。
- 不改变现有 `PRD → UI Design → Auto Layout → final DesignDocument` 的依赖顺序；将 Codegen 注册为 Root 可选能力，由 Root 模型结合用户目标、已完成产物、画布上下文和能力描述决定是否调用，不作为强制第四阶段。

## Capabilities

### New Capabilities

- `design-document-code-generation`：定义多模态 Codegen Agent 的输入、规划、源码生成、隔离检查、视觉自检、自动修复、双文件输出和失败语义。

### Modified Capabilities

无。

## Impact

- `apps/server`：新增 Codegen Agent、视觉模型调用能力、受控工具执行器、有限状态循环、稳定错误与单元/集成测试；Root 获得基于上下文自主选择该能力的入口。
- `packages/design-contract`：新增 Codegen 请求、画布图片描述、双文件结果和验证摘要契约及 TypeScript 导出。
- API/调用方：新增按 final DesignDocument 和画布上下文自动捕获图片后生成代码的能力；不修改现有 project generation 成功响应。
- 运行环境：服务端需要可用的视觉模型和预装的隔离检查/预览环境；目标项目需已配置 React、Tailwind CSS 与 `antd`。
- 生成范围：第一版只返回单个 React 组件对应的 TSX/CSS，不创建项目脚手架、依赖清单、路由、后端接口或业务状态逻辑。
