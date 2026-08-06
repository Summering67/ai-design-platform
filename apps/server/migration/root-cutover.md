# 根入口切换清单

本变更只新增并验证 `apps/server`，不修改 `apps/api`、根 `package.json`、Turbo 配置、Web rewrite、`API_BASE_URL` 或部署入口。当前默认根入口仍指向 Go 后端。

后续切换应单独创建变更并按以下顺序执行：

1. 将根开发/构建编排显式切换到 `apps/server` 的 `dev:standalone`，保留 Go 启动任务用于回退。
2. 将部署健康检查、端口和进程关闭策略切换到 FastAPI/Uvicorn，并验证 `API_*` 配置与密钥注入。
3. 在 Web rewrite 与 `API_BASE_URL` 不变的前提下运行双实现契约 fixture；发现差异时回退到 `apps/api`。
4. 切换后保留 Go 源码、迁移和回退入口，直到等价验证和生产观测窗口完成。
