# 根入口切换清单

当前根开发入口已切换到 `apps/server`，但本变更不删除或修改 `apps/api`，也不改变 Web rewrite 的 `/backend` 路径。Go 保留为删除前定向回退和一次性 live parity 基准。

后续切换应单独创建变更并按以下顺序执行：

1. 根 `dev` 已通过 `turbo run dev --filter=!api` 选择 `apps/server`；Go 回退仍使用 `pnpm --filter api dev`。
2. Server 入口已读取 `API_SERVER_ADDRESS`、idle timeout 和 shutdown timeout；部署仍需验证实际健康检查、端口和密钥注入。
3. Web rewrite 与 `API_BASE_URL` 保持不变；进程内冻结契约测试可在无 Go runtime 时执行，双实现 live parity 仍是删除前门禁。
4. 在 migration、隔离 PostgreSQL 集成测试和 live parity 完成前，保留 Go 源码、迁移和回退入口。
