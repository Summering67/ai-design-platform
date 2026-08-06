## ADDED Requirements

### Requirement: Go API 删除门禁

系统 SHALL 在删除 `apps/api` 前确认 Python runtime 的根入口、配置透传、自包含构建、冻结契约回归、隔离 PostgreSQL 集成测试和一次性 Go/Python live parity 均具有实际通过证据。任何 SQL migration 缺口、跳过的关键集成测试或未解析仓库引用存在时，`apps/api` MUST 保持未删除状态。

#### Scenario: 删除门禁存在阻塞

- **WHEN** migration、PostgreSQL 集成测试、双实现实跑或仓库引用清理中的任一项未完成
- **THEN** 迁移队列记录真实阻塞，系统不删除 `apps/api` 且不宣称退役完成

#### Scenario: 删除门禁全部满足

- **WHEN** 所有删除门禁均有可审查的实际通过证据
- **THEN** 后续独立退役变更可以删除 Go runtime，并同步 workspace、锁文件、规格和文档

## MODIFIED Requirements

### Requirement: 双实现等价验证

系统 SHALL 在删除 Go runtime 前对 Go 与 Python 实现运行相同的契约 fixture，并比较规范化 HTTP 状态、JSON、Cookie、SSE 事件和数据库结果。写数据库的比较 SHALL 使用相同初始数据的隔离数据库或 Schema，MUST NOT 让两个实现并发修改同一测试记录。比较通过后，系统 SHALL 固化不依赖 Go 进程的契约 fixture，供 Python runtime 在删除后持续回归。

#### Scenario: 比较只读请求

- **WHEN** 同一只读 fixture 分别提交给 Go 和 Python 实现
- **THEN** 两个实现返回契约等价的规范化结果

#### Scenario: 比较写入请求

- **WHEN** 同一写入 fixture 需要分别验证两个实现
- **THEN** 每个实现从相同隔离初始状态执行，测试比较最终数据库状态且不存在跨实现数据干扰

#### Scenario: 固化删除后回归面

- **WHEN** 双实现比较实际通过并准备退役 Go runtime
- **THEN** 规范化契约结果被保存为不含敏感数据的 fixture，Python 测试无需 Go 进程即可重复验证
