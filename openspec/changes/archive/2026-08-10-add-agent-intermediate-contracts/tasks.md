## 1. 中间契约与共享类型

- [x] 1.1 在 `packages/design-contract/schema/v2` 新增严格的 `initial-ui-document.schema.json`，包含图层 kind/tag、稳定 ID、资产、组件、Token、基础 style 与 layout/layoutItem 约束
- [x] 1.2 新增严格的 `layout-plan.schema.json`，使 layout、layoutItem、responsive 与 DesignDocument 对应定义同源并禁止内容、结构、style 与 computedLayout 字段
- [x] 1.3 为两个新增 Schema 增加有效和无效 fixtures，保留现有 UIValidationReport 兼容 Schema 并标记 deprecated，更新 `packages/design-contract` 的生成类型与公开导出
- [x] 1.4 [单元测试] 增加两个新增 Schema 的正反例、条件字段、additionalProperties、布局枚举一致性和未知字段拒绝测试

## 2. UI Design 初始 UI JSON 阶段

- [x] 2.1 重写 UI Design prompt，明确输出包含图层结构、组件、内容、基础样式和布局规则的初始 UI JSON，并列出不得生成的 designSystem、computedLayout 和框架字段
- [x] 2.2 将 UI Design 模型结构化输出切换为 `initial-ui-document.schema.json`，并在返回后执行引用、唯一 ID、叶子节点、深度和节点数量语义校验
- [x] 2.3 将 UI Design 子图返回值和 Root State 交接字段由无约束 `initial_document` 改为 `initial_ui_document`，同步调整任务 catalog 和依赖判断
- [x] 2.4 [单元测试] 覆盖合法初始 UI JSON、重复 ID、非法组件/Token/资产引用、非法叶子 children、未知字段和禁止最终字段拒绝

## 3. Auto Layout 内部确定性编译

- [x] 3.1 将纯函数 `compile_initial_ui_document` 迁入 Auto Layout Agent，从固定 GenerationContract 注入 v2 版本、Profile、Token/组件快照与资产，并递归映射 kind/tag、style、layout 和 layoutItem
- [x] 3.2 实现稳定 ID、业务节点、文案和结构保持校验，确保编译器不会静默删除初始 UI JSON 语义或发明契约能力
- [ ] 3.3 将 DesignDocument Schema、Profile、GenerationContract、引用、层级、节点上限和布局校验改为收集全部可定位问题
- [ ] 3.4 定义 Auto Layout 内部 `ValidationResult`，支持 keyword、expected、脱敏截断 actual 和完整问题状态；deprecated UIValidationReport 仅保留成功兼容投影
- [ ] 3.5 [单元测试] 覆盖相同输入编译等价、Profile 固定、kind/tag 映射、缺失 contract 能力和多错误路径报告

## 4. 两 Agent 流水线迁移

- [x] 4.1 从 Root Supervisor 的任务顺序、catalog、ready 判断、状态交接和事件中移除 Specification Agent
- [x] 4.2 将 Auto Layout 输入改为 InitialUIDocument，并在调用布局模型前完成确定性编译和 DesignDocument 全量校验
- [x] 4.3 移除 Specification prompt、graph、nodes 及运行引用；不得保留模型重写完整 DesignDocument 的兼容路径
- [x] 4.4 [单元测试] 覆盖两 Agent 顺序、Auto Layout 内部编译、编译失败不调用布局模型，以及最终文档成功交付

## 5. Auto Layout 计划与确定性应用

- [x] 5.1 重写 Auto Layout prompt，明确只为已有节点输出声明式 LayoutPlan，不得修改结构、业务语义、视觉样式或生成 computedLayout
- [x] 5.2 将 Auto Layout Agent 内部规划切换为 `LayoutPlan` Schema，并增加 nodeId、GenerationContract 能力、断点、非负数值和互斥约束校验
- [x] 5.3 将布局应用模块收回 Auto Layout Agent，在 Agent 内部写入 layout、layoutItem、responsive，并移除 `props.data-sizing` 和错误的 gap/style 映射
- [x] 5.4 实现布局字段到当前 v2 渲染器可消费 style 的确定性投影，只覆盖布局 Agent 拥有的样式字段并保留其余视觉样式
- [ ] 5.5 仅对无需外部测量即可推导的节点生成 computedLayout，对字体、图片或组件尺寸不确定的节点保持省略，并由 Auto Layout Agent 返回完整 DesignDocument
- [ ] 5.6 [单元测试] 覆盖 Flex/尺寸/响应式投影、未知节点、禁止能力、负数、幂等应用、语义保持和 computedLayout 省略条件

## 6. 流水线门禁与渲染交付

- [x] 6.1 更新 Root Supervisor 的 completed 状态、任务输入输出和事件摘要，只使用 `initial_ui_document` 与 `final_document`，不新增 Specification 或 `final_gate` 任务
- [x] 6.2 在两个 Agent 返回前执行对应 Schema、GenerationContract、引用和渲染语义门禁，并确保内部编译未通过时不调用布局模型
- [x] 6.3 [集成测试] 更新 fake model 与完整 Agent 流水线测试，验证两个 Agent 依次推进并交付可派生 v2 render model 的最终文档
- [ ] 6.4 [集成测试] 覆盖初始 UI JSON、内部编译、LayoutPlan 或 Auto Layout 最终文档校验任一失败时不产生成功 result
- [ ] 6.5 [集成测试] 在 `packages/design-dsl` 与 `packages/ui` 覆盖最终 fixture 可通过 render model 并由 DesignDocumentRenderer 递归形成基础布局节点

## 7. 相关检查

- [ ] 7.1 运行并通过 `packages/design-contract` 的格式化、lint、类型检查和构建入口
- [ ] 7.2 运行并通过 `apps/server` 的 Ruff、mypy、Agent 单元测试与流水线集成测试
- [ ] 7.3 运行并通过 `packages/design-dsl` 和 `packages/ui` 的 lint、类型检查、单元测试与构建入口
- [x] 7.4 运行 OpenSpec 校验并确认 proposal、design、delta specs 与 tasks 均可解析且 apply-ready

## 8. Agent 执行 Harness 与有限 Loop

- [x] 8.1 新增两个专业 Agent 共用的结构化输出 Harness，执行有界的“调用—校验—短摘要—重试”循环，且不注册为 Agent 或任务阶段
- [x] 8.2 将 UI Design 和 Auto Layout 的模型调用接入 Harness，由各 Agent 提供自身校验函数，Harness 不修改候选产物或内部编译文档
- [x] 8.3 实现错误摘要白名单和长度上限，只传递 code、可用 JSON Pointer 路径及简短原因，禁止回传完整错误、候选、Schema 或输入副本
- [x] 8.4 [单元测试] 覆盖首次失败后成功、重试耗尽、短摘要长度、候选未被修改，以及 Harness 不出现在任务 catalog

## 9. UI Design 诊断与回放

- [x] 9.1 新增 Harness 结构化诊断 Trace，记录 stage、attempt、status、failure phase、耗时、输出大小、模型标识和 prompt/Schema/GenerationContract 指纹
- [x] 9.2 实现最多 20 个 Schema 问题的完整内部收集，包含 JSON Pointer、keyword、expected 与脱敏截断 actual，同时保持模型重试只接收短摘要
- [x] 9.3 增加 DEBUG 级脱敏候选快照和可聚合指标字段，禁止记录完整 PRD、GenerationContract、敏感字段或未截断候选
- [x] 9.4 [单元测试] 覆盖多错误路径、指纹稳定性、敏感字段脱敏、快照长度、首次失败后成功 Trace，以及离线 Schema 回放

## 10. 模型调用超时与稳定失败

- [x] 10.1 为 thinking/fallback 子调用增加不可由流活动延长的绝对时限，并记录脱敏子调用 Trace
- [x] 10.2 将模型失败拆分为超时、限流、认证、HTTP、非法流、空响应和非法 JSON稳定错误，移除 fallback 决定 retryable 的逻辑
- [x] 10.3 在 Root Runner 真正执行 Agent 总时限，并避免 Harness 耗尽后再触发 Supervisor 重复模型重试
- [x] 10.4 [单元测试] 覆盖持续流绝对超时、fallback 错误可重试、认证失败不可重试、子调用 Trace 和持续 activity 的 Agent 总超时
