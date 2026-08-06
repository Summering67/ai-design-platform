## 1. 生成契约依赖与共享 Schema

- [x] 1.1 核对现有 v2 `DesignDocument` Schema、DesignSystemProfile、DesignGenerationContract fixture 与 v2 契约加载边界，禁止在 Agent 模块内复制 v1 Tree 契约
- [x] 1.2 在 `packages/design-contract/schema/v2` 新增版本化 `standardized-prd.schema.json`，覆盖目标、用户、范围、页面、流程、内容、组件、交互状态、响应式、可访问性、约束、假设和未决问题
- [x] 1.3 在 `packages/design-contract/schema/v2` 新增版本化 `ui-validation-report.schema.json` 和 `agent-run-event.schema.json`，定义稳定错误码、JSON Pointer、修复状态、阶段事件和唯一终态
- [x] 1.4 为新增 Schema 添加合法与非法固定 fixture，并同步 `packages/design-contract` 的公开导出和包内容声明
- [ ] 1.5 【单元测试】验证新增 Schema 拒绝未知字段、缺失字段、非法版本、重复稳定 ID、无效引用和不一致报告计数
- [ ] 1.6 【集成测试】使用相同 fixture 验证 Python Agent 契约加载器与 TypeScript 设计契约消费方具有一致的通过/拒绝结果

## 2. LangGraph 基础模块与运行依赖

- [x] 2.1 在 `apps/server/pyproject.toml` 增加 LangGraph 和实际使用的模型适配依赖并更新 `uv.lock`，不新增未被当前实现使用的 Agent 框架或基础设施
- [x] 2.2 在 `apps/server/src/ai_design_server/agents` 建立 graph、state、events、runner、contracts 及四个专业子模块，保持子模块公开接口最小化
- [x] 2.3 扩展 `apps/server/config.py` 的强类型 AI 配置，增加节点超时、总运行超时、输入字节、输出字节、页面、节点、深度和重试上限，并同步安全示例配置
- [x] 2.4 实现从 `packages/design-contract` 加载版本化 Schema 和固定生成契约的只读契约加载器，启动时缺失或版本不兼容立即失败
- [x] 2.5 实现兼容现有 AI BaseURL、API Key、Model 和 HTTPX 生命周期的 LangGraph 模型适配依赖，不在节点中创建客户端或读取环境变量
- [x] 2.6 在 FastAPI lifespan 中构建一次 Root Graph、模型适配和只读契约依赖，并在关闭时取消未完成运行且释放上游资源
- [ ] 2.7 【单元测试】验证 Agent 配置边界、契约加载失败、资源上限和模型适配错误均转换为稳定领域错误且不泄露内部信息

## 3. 需求解析智能体

- [x] 3.1 定义需求解析子图的窄输入输出状态和版本化 prompt，使原始产品需求只输出 StandardizedPRD 候选对象
- [x] 3.2 实现需求输入的空值、字节上限和冲突前置检查，非法输入在调用模型前提前返回
- [x] 3.3 实现 StandardizedPRD 的 Schema、稳定 ID、页面与流程引用门禁，并区分明确需求、假设、未决问题和阻断冲突
- [x] 3.4 实现一次有界结构化修复重试，重试仅接收最小校验错误且不得丢失用户明确约束
- [ ] 3.5 【单元测试】覆盖完整需求、缺失设备信息、安全假设、关键冲突、明确合规约束、非法引用和重试耗尽

## 4. UI 设计智能体

- [x] 4.1 定义 UI 设计子图输入输出和版本化 prompt，仅接收已校验 StandardizedPRD 与固定 DesignGenerationContract
- [x] 4.2 实现初始 v2 DesignDocument 结构化生成，覆盖根图层、组件、内容、状态、基础样式、布局意图和响应式意图
- [x] 4.3 实现生成能力白名单，拒绝未注册组件、Token、variant、slot、图标、布局能力、目标框架绑定、CSS 字符串和任意事件处理器
- [x] 4.4 实现 PRD 页面、流程、必要状态和内容约束的覆盖检查，将无法表达项返回为结构化生成问题
- [x] 4.5 实现 v2 DesignDocument Schema、Profile 摘要、稳定 ID、父子层级、资源引用和生成契约门禁及一次有界修复重试
- [ ] 4.6 【单元测试】覆盖多页面生成、固定 Profile、受限组件、加载/空/错误状态、重复 ID、非法层级和目标框架字段拒绝

## 5. 规范校验智能体

- [x] 5.1 定义规范校验子图、版本化 prompt 和 UIValidationReport 构造函数，统一稳定错误码、严重级别、JSON Pointer 和修复状态
- [x] 5.2 实现 v2 DesignDocument Schema、Profile、生成契约、引用、ID、层级、组件属性、Token、布局能力、PRD 覆盖和可访问性的确定性检测
- [x] 5.3 建立 repairable 与 fatal 规则映射，禁止通过替换 Profile、删除核心页面、放宽约束或忽略错误获得通过状态
- [x] 5.4 实现模型候选修正，并比较修正前后的 Profile、稳定 ID、用户确认文案、业务流程和组件语义不可变项
- [x] 5.5 对候选修正文档重新执行全部确定性校验，保持报告计数、问题状态、最终结论和返回文档一致
- [ ] 5.6 【单元测试】覆盖未知 Token、非法 variant、缺少替代文本、Profile 漂移、安全修正、新增错误、不可修复能力和报告一致性

## 6. Auto Layout 智能体

- [x] 6.1 定义版本化布局计划结构和 Auto Layout 子图输入输出，模型只生成引用现有节点的布局建议
- [x] 6.2 实现纯函数布局引擎，应用 Flex 方向、主轴/交叉轴对齐、间距、内边距、换行、嵌套容器及 hug/fill/fixed 尺寸策略
- [x] 6.3 实现响应式断点覆盖，按生成契约限制方向、间距、尺寸、换行和可见性变化，拒绝目标框架媒体查询语法
- [x] 6.5 实现布局冲突、未知节点、禁用能力、最大深度、循环、孤儿、重复子节点和叶子 children 的提前拒绝
- [x] 6.6 对最终 v2 DesignDocument 执行 Schema、Profile、稳定 ID、层级和布局能力门禁，并生成布局变更摘要
- [ ] 6.7 【单元测试】覆盖工具栏、表单 fill、桌面双栏转移动单栏、嵌套布局、固定尺寸冲突、禁用能力、派生 ID 幂等和未知节点计划

## 7. Root 编排与 Runner 接口

- [x] 7.1 定义可序列化 Root State，包含 run ID、固定 Profile、任务目录、活动任务、任务谱系、各任务结果、校验报告、重试计数和唯一终态，不包含 Request、AsyncSession 或客户端对象
- [x] 7.2 构建 Root Supervisor StateGraph，注册四个专业子图和最终门禁，由模型根据输入 Schema、数据依赖和当前目标选择任务，可支持循环与可执行任务并行
- [x] 7.3 实现 Agent 能力目录、任务身份、父子谱系、任务状态机、Schema/Profile 不变式、可重试错误映射、每任务最多一次重试和未注册能力拒绝
- [x] 7.4 实现异步 runner 函数，以 `AgentRunEvent` 流式产出带 run/task/attempt 身份的 run、stage、progress 和唯一 result/failed/cancelled 终态，不暴露内部节点与上游错误
- [x] 7.5 实现总运行超时、并发额度、任务数量/深度上限和调用方取消传播，确保活动子图、模型请求和后续调度停止，终态后不再产生事件
- [ ] 7.6 【单元测试】覆盖模型选择路径、数据依赖阻止、并行任务、未注册能力、任务谱系、迟到事件、Profile 漂移、可重试成功、重试耗尽、唯一终态和序列化 State
- [x] 7.7 【集成测试】使用确定性模型替身运行动态 Root Supervisor，验证模型改变任务顺序、校验反馈循环、最终门禁、事件关联和最终 v2 DesignDocument
- [ ] 7.8 【集成测试】验证执行中取消、模型超时、子图异常、无效结构化输出和资源超限均停止后续调度且返回稳定终态

## 8. 检查与交付

- [x] 8.1 运行 `apps/server` 现有格式化、Ruff、mypy、pytest 和构建检查，记录实际结果且不修复本变更外的存量问题
- [x] 8.2 运行 `packages/design-contract` 现有格式化、lint、类型检查、单元测试和构建检查，确认新增 Schema、fixture 和公开导出一致
- [x] 8.3 核对没有公开 HTTP、数据库结构或 Web 行为变化，没有敏感配置、未使用依赖、占位实现、重复契约或未解释 TODO
