## 1. 收敛 v2 契约

- [x] 1.1 在 `packages/design-contract/schema/v2/design-document.schema.json` 定义唯一当前 Schema，完整覆盖文档根、内嵌 designSystem、Asset、严格节点判别、JSON props、受限 camelCase Web style 和 source 审计字段，并对所有对象关闭未声明属性
- [x] 1.2 新增合法 v2 登录页 fixture，以及重复 ID、悬空 Asset、非法组件、props 隐藏节点、CSS 文本、运行时字段和摘要不匹配等非法 fixture
- [x] 1.3 调整 `packages/design-contract` 公开导出，使 v2 DesignDocument 成为唯一当前 DSL 契约，并将现有 v1 Schema 限制为迁移代码的只读输入
- [x] 1.4 确认标准库与现有依赖无法满足后，只加入 TypeScript Schema 类型派生和 Go JSON Schema 校验实际使用的最小依赖，不新增独立打包、测试或运行命令
- [x] 1.5 从 v2 Schema 派生并公开 TypeScript DesignDocument、DesignNode、DesignSystemSnapshot、Asset 和 JSONValue 类型，移除手写字段形状的事实所有权

## 2. TypeScript 校验与派生内核

- [x] 2.1 实现 v2 Schema 校验后的语义校验，覆盖全局 ID 唯一、kind 专用字段、Asset 引用、组件快照、props 节点嵌套和 designSystem 摘要，并返回稳定错误码与 JSON 路径
- [x] 2.2 将现有编辑 Graph 改为从 v2 Tree 建立的可丢弃投影，保证 parent 索引、children 顺序和 Tree → Graph → Tree 确定性往返
- [x] 2.3 调整操作应用边界，使批量操作只在隔离副本执行，成功后重新生成并完整校验 v2 Tree，再原子返回新规范文档
- [x] 2.4 从 component 节点的 tag、packageName 和 defaultModule 确定性收集、排序和去重依赖，不读取或写入持久化 dependencies/className
- [x] 2.5 调整 `DesignRenderModel` 与现有 DOM/组件适配输入，仅消费合法 v2 文档并保持输入不可变，不再依赖外部可变 Profile 补充设计语义

## 3. v1 到 v2 迁移

- [x] 3.1 实现 v1 Graph、v1 Tree、v2 Tree 的显式结构判别，拒绝混合、未知或歧义格式
- [x] 3.2 实现 v1 Graph 到 v2 Tree 的确定性迁移，按 childIds 保留稳定 ID、节点顺序、Asset、文本、支持的样式和组件信息
- [x] 3.3 实现 v1 Tree 到 v2 Tree 的确定性迁移，保留嵌套顺序并统一映射 semi-d2c 风格节点字段
- [x] 3.4 在迁移时按旧引用解析固定 Profile 并嵌入 designSystem 快照；缺失、版本或摘要不匹配时失败关闭
- [x] 3.5 为迁移结果提供源格式、源版本、目标版本、迁移器版本、警告、稳定错误码和源 JSON 路径，确保任何失败不产生部分 v2 结果

## 4. Go API 与持久化边界

- [x] 4.1 让 `apps/api/internal/design` 加载或嵌入 `packages/design-contract` 的同一 v2 Schema 执行结构校验，移除手写的并列必填字段契约
- [x] 4.2 在 Go 接收边界实现与 TypeScript 一致的 v2 语义不变量、错误码和路径映射，并继续执行文档大小与权限检查
- [x] 4.3 增加显式 v1 迁移入口，并将普通创建、更新和持久化入口切换为只接受完整合法 v2 文档
- [x] 4.4 确保迁移成功后只在线读取 v2，迁移失败或持久化失败时保留原 v1 payload，不实现有损 v2→v1 回写

## 5. 契约与内核验证

- [x] 5.1 【单元测试】验证 v2 Schema 接受全部合法 fixture，并拒绝未声明字段、运行时值、非法 kind、CSS 文本和缺失必填字段
- [x] 5.2 【单元测试】验证语义校验拒绝重复 ID、props 隐藏节点、悬空 Asset、非法组件与摘要不匹配，并断言稳定错误码和 JSON 路径
- [x] 5.3 【单元测试】验证 Tree → Graph → Tree 往返、节点移动和批量操作原子性，以及失败后原文档不变
- [x] 5.4 【单元测试】验证依赖收集去重与稳定排序、预览派生不修改输入、相同文档重复派生结果一致
- [x] 5.5 【单元测试】验证 v1 Graph/Tree 判别、成功迁移、迁移审计信息，以及循环、多个父节点、Profile 不匹配和不可映射字段的失败关闭
- [x] 5.6 【集成测试】让 TypeScript 和 Go/API 读取同一组 v2 合法/非法 fixture，确认结构结论、语义错误码和 JSON 路径一致
- [x] 5.7 【集成测试】验证 API 普通写入口拒绝 v1、接受合法 v2，显式迁移入口成功后持久化 v2，失败时原数据保持不变

## 6. 调用方与契约清理

- [x] 6.1 更新 `packages/ui` 设计渲染调用方和测试，继续通过派生模型渲染且不直接持有第二份 DSL 类型
- [x] 6.2 删除或停止公开旧 Tree/Graph/Profile/GenerationContract 的当前事实源入口，同步更新所有受影响的跨包公开导出和调用方
- [x] 6.3 更新 `DSL_DESIGN.md`、`CONTEXT.md` 和迁移说明，统一“规范设计文档”“派生 Graph”“设计系统快照”“派生产物”等术语
- [x] 6.4 标记 `add-design-dsl` 与 `complete-preview-data-model` 中冲突的事实源设计为被本变更取代，并在本变更完成后按独立归档流程处理旧变更
- [x] 6.5 运行受影响包现有格式化、lint、类型检查和构建入口，确认没有修改或修复任务范围外的存量问题
