# Python 迁移队列

状态：`pending → ready → in_progress → verified`。当前实现完成后只将目标项标记 `verified`，不删除或退役 `apps/api`。

| ID | 波次 | Go 来源/目标 | 前置 | 验证 | 状态 | 证据/阻塞 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | 1 | 环境 → `apps/server` | — | 文档 | verified | Python 3.14.3、uv 0.11.12 |
| 1.2 | 1 | 迁移规则 → `migration/rules.md` | 1.1 | 文档 | verified | 已建立 |
| 1.3 | 1 | 依赖图 → `migration/dependency-map.md` | 1.2 | 文档 | verified | 21 个 Go 文件及非 import 边 |
| 1.4 | 1 | 队列 → `migration/queue.md` | 1.3 | 文档 | verified | 49 项任务映射 |
| 1.5 | 1 | Go 单元基线 | 1.3 | 单元测试 | verified | `GOCACHE=/tmp/aidp-go-build-cache go -C apps/api test ./...` 通过 |
| 1.6 | 1 | Go 集成基线 | 1.3 | 集成测试 | pending | PostgreSQL DSN 未确认 |
| 2.1–2.7 | 2 | 工程/配置/日志/DTO/Design → `src/ai_design_server` | 1.4 | 静态检查 | verified | Ruff、mypy 通过 |
| 2.8 | 2 | 基础单元测试 | 2.7 | 单元测试 | in_progress | 配置与 Chat SSE fixture 已覆盖 |
| 3.1–3.5 | 3 | GORM/Chat → SQLAlchemy/HTTPX | 2.8 | 代码检查 | in_progress | SQLAlchemy/HTTPX 实现完成，隔离 PostgreSQL 未执行 |
| 4.1–4.2 | 4 | Auth → `auth/` | 3.1 | 代码检查 | in_progress | 路由与会话实现完成 |
| 5.1–5.5 | 5 | Project/Generation → `project/` | 4.4 | 代码检查 | in_progress | JSON/SSE 路由实现完成，隔离 PostgreSQL 未执行 |
| 6.1–6.3 | 6 | Server/Router → `app.py`/`main.py` | 5.8 | 代码检查/构建 | in_progress | Ruff、mypy、pytest、wheel 构建通过 |
| 7.1–7.6 | 7 | 双实现等价 → fixtures | 6.5 | 集成测试 | pending | Go/Python 比较待执行 |
| 8.1–8.5 | 8 | 保留 Go、交付切换清单 | 7.6 | 集成测试/文档 | pending | 根入口切换不属于本变更 |
