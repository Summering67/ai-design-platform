## 1. 根入口与运行配置

- [x] 1.1 将根开发任务切换为排除 Go `api` 并保留定向 Go 回退入口
- [x] 1.2 实现统一 Python 进程入口，将 `API_SERVER_ADDRESS`、idle timeout 和 shutdown timeout 映射到 Uvicorn
- [x] 1.3 在 Server Turbo 任务中声明并透传 `API_*` 运行配置
- [x] 1.4 【单元测试】覆盖监听地址解析和 Uvicorn 参数映射
- [x] 1.5 【集成测试】检查根 dev 任务图包含 Server/Web 且不包含 Go API

## 2. 自包含构建

- [x] 2.1 让 wheel 从 `packages/design-contract` 的唯一来源包含 Design v2 Schema
- [x] 2.2 修改 Design v2 校验优先读取包资源并保留源码 workspace 回退
- [x] 2.3 【单元测试】验证 Design v2 Schema 资源加载和有效/无效文档校验
- [x] 2.4 【集成测试】构建 wheel 并确认安装态资源不依赖仓库相对路径

## 3. 删除门禁与验证

- [x] 3.1 将 Go/Python live parity 明确为删除前门禁，并保留不依赖 Go 进程的冻结契约回归
- [x] 3.2 更新 migration queue 与 root cutover，记录 migration、PostgreSQL 和 live parity 的真实阻塞状态
- [x] 3.3 运行 Server Ruff、mypy、pytest、build 与 OpenSpec 校验，记录实际结果和跳过项
