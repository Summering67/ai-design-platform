## 1. Agent 运行事件

- [x] 1.1 为默认 GenerationContract 建立服务端加载入口，并在专业任务完成事件中附带已验证输出。

## 2. 项目 generation 接入

- [x] 2.1 将项目 SSE generation 改为执行 Root Agent、转发 agent 事件并在成功终态返回最终 DesignDocument。
- [x] 2.2 保持取消、失败、助手完成说明与既有 generation 尝试语义，并补充后端 Agent 运行测试。

## 3. 工作台交付

- [x] 3.1 消费 agent 事件并显示阶段及结构化输出。
- [x] 3.2 将 completed 的最终 DesignDocument 交给共享 Workspace 并用 v2 渲染器显示在画布。

## 4. 验证

- [x] 4.1 运行服务端 Agent 与项目相关测试、Web 类型检查，并记录结果。

## 5. 调试日志

- [x] 5.1 在 Root 派发子 Agent 时输出不含需求或模型内容的结构化控制台日志。
