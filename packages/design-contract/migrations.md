# DSL 迁移

当前唯一事实源是 `DesignDocument 2.0.0` 树形 JSON，由
`schema/v2/design-document.schema.json` 定义。v1 Graph 和 v1 Tree 仅允许通过
`packages/design-dsl` 的显式迁移入口转换为 v2；普通写入口不得继续接受 v1。

迁移必须先判别 v1 Graph/v1 Tree 结构，再解析与旧文档摘要一致的固定 Profile，生成内嵌
`designSystem` 快照，最后执行完整 v2 Schema 和语义校验。循环、重复 ID、悬空资源、未知组件、
无法映射的样式或 Profile 摘要不匹配时，整次迁移失败且不得写入部分结果。

成功结果记录源格式、源版本、目标版本、迁移器版本和警告；在线读取只使用 v2 文档，原始 v1
payload 由现有备份或审计边界保留，不执行有损 v2→v1 回写。
