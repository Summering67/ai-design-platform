## 1. 多模态 Codegen 契约

- [x] 1.1 在 `packages/design-contract/schema/v2` 新增严格的 Codegen 请求 Schema，约束 final DesignDocument、至少一张 viewport 画布图片、安全命名、图片格式/尺寸/大小和未知字段。
- [x] 1.2 新增 CodePlan、双文件产物、计划摘要、验证摘要和稳定错误的内部/公开类型，并同步 `packages/design-contract` 公开导出。
- [x] 1.3 新增合法与非法 fixtures，覆盖文档/图片绑定、同 viewport 重复、名称注入、双文件原子性和响应脱敏。
- [x] 1.4 （单元测试）验证 Codegen 请求/结果 Schema、内容摘要、图片限制和恰好两个 TSX/CSS 文件的契约。

## 2. 多模态模型与 Agent 状态

- [x] 2.1 扩展模型适配边界以支持文本、结构化 JSON 和图片 content parts，并在模型不具备视觉能力时返回稳定错误。
- [x] 2.2 实现 CodePlan Schema、规划提示和生成/修复提示，明确 JSON 事实优先、React/Tailwind CSS/Ant Design 目标、双文件范围和禁止暴露思维链。
- [x] 2.3 实现独立 Codegen 状态图：输入门禁、规划、生成、静态检查、预览、视觉审查、修复、完成/失败；作为 Root 的可选任务，不改变既有前三阶段顺序。
- [x] 2.4 保存显式运行状态，包括冻结输入摘要、计划、候选 manifest、尝试次数、裁剪诊断、预览引用和变更摘要，并在终止时清理临时状态。
- [x] 2.5 （单元测试）使用 fake multimodal model 验证图片确实进入规划和视觉审查请求、无计划不得生成、阶段事件不含思维链且 Root 顺序不变。

## 3. 隔离工作区与受控工具

- [x] 3.1 实现每次运行独享的临时工作区及安全 basename 解析，运行完成、失败或取消后可靠清理。
- [x] 3.2 实现 `write_candidate`/`read_candidate` 工具，只允许原子读写同 basename 的 TSX/CSS，并限制文件数、路径和内容大小。
- [x] 3.3 实现固定 verifier adapter，使用预定义格式化、TypeScript 和 ESLint 配置检查候选，不接受模型提供的命令、依赖或路径。
- [x] 3.4 实现 preview renderer adapter 契约，在指定 viewport 将候选转换为预览图片，并限制耗时、像素、响应大小和可访问资源。
- [x] 3.5 实现机器诊断与视觉诊断的去重、脱敏、裁剪和稳定分类，禁止返回绝对路径、堆栈、完整源码或输入副本。
- [x] 3.6 （单元测试）覆盖路径逃逸、额外文件、任意命令、网络/安装依赖尝试、输出超限、工具超时、取消和工作区清理。

## 4. 生成、检查与自动修复闭环

- [x] 4.1 实现首版候选生成，确保默认导出 React 函数组件、相对 CSS import、静态 Tailwind class、按需 Ant Design import、作用域 CSS 和无仓库私有依赖。
- [x] 4.2 实现静态检查失败后的有限修复循环，每轮只修改候选 TSX/CSS，并在修改后重新运行全部强制检查。
- [x] 4.3 实现静态通过后的视觉审查，将原画布图与预览图交给视觉模型并校验结构化问题、置信度与契约冲突。
- [x] 4.4 实现视觉问题的有限修复循环；修复后依次重跑静态检查、预览和视觉审查，直至通过或达到上限。
- [x] 4.5 实现模型调用、工具调用、修复轮数、输入/输出、单步与总耗时限制，并映射 `input_invalid`、`input_mismatch`、`plan_invalid`、`generation_failed`、`verification_failed`、`visual_mismatch`、`timeout`、`cancelled` 和 `limit_exceeded`。
- [x] 4.6 （单元测试）覆盖首次成功、类型错误后修复、lint 错误后修复、视觉偏差后修复、建议与契约冲突、静态/视觉耗尽和输入全程不变。

## 5. 独立 API 与集成验证

- [x] 5.1 按现有认证和错误响应约定新增独立 Codegen API，接收文档与画布图片并输出阶段事件或最终双文件结果，不写 generation 状态和 `.agent-outputs`。
- [x] 5.2 更新 `apps/server/AGENTS.md` 的职责说明，明确 Codegen 是 final DesignDocument 后的独立多模态能力，内部可修复自己的源码但不进入设计生成主链路。
- [x] 5.3 （集成测试）使用 fake model、fake verifier 和 fake preview renderer 覆盖成功、静态修复、视觉修复、超时、取消、脱敏错误及清理流程。
- [x] 5.4 （集成测试）将代表性最终双文件放入最小 React、Tailwind CSS、Ant Design 类型环境执行 TypeScript 编译，覆盖 HTML、资产、嵌套组件和响应式布局。
- [x] 5.5 （集成测试）验证 preview renderer adapter 的 viewport、输入产物和图片结果契约；不使用浏览器自动化作为 OpenSpec 验收方式。

## 7. 自动读取画布

- [x] 7.1 新增 CanvasCapture 适配器协议，由服务端根据文档和 viewport 上下文自动捕获画布图片。
- [x] 7.2 Codegen API 在调用 Agent 前执行画布捕获、viewport 校验、超时和数量限制，不再要求调用方上传图片。
- [x] 7.3 覆盖捕获成功、viewport 无效、捕获超时和捕获器不可用的测试与稳定错误码。

## 8. Root 模型自主路由

- [x] 8.1 为 Root 能力目录增加清晰的 Agent 描述，并向模型提供用户原始目标、已完成产物、调用历史和当前可执行能力。
- [x] 8.2 移除模型空选或选中未就绪能力时的确定性任务兜底；已有设计结果时以空任务表示无需继续调用 Agent。
- [x] 8.3 将 Codegen Runner 接入项目生成链路，并仅在 Root 模型选择 `codegen` 后自动读取画布和运行 Codegen Agent。
- [x] 8.4 覆盖 Root 选择 Codegen 与明确不选择 Codegen 两种路径，验证未选择时不会被强制调用。

## 6. 相关检查

- [x] 6.1 运行 `packages/design-contract` 适用的格式化、lint、类型检查和相关测试，并只处理本变更引入的问题。
- [x] 6.2 运行 `apps/server` 适用的 Ruff、mypy、相关 pytest 与构建，并记录实际结果及未执行检查的风险。
