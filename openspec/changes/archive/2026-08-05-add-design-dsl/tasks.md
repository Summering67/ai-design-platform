## 1. 契约包与固定样例

- [x] 1.1 新增 `packages/design-contract` 工作区包、公开文件清单和 TypeScript 配置，仅包含语言无关的 schema、fixture 与迁移说明
- [x] 1.2 定义 v1 `design-document.schema.json`，覆盖版本、元数据、页面、Root、规范化节点 Graph、令牌、资源、样式、布局、语义、组件定义与组件绑定
- [x] 1.3 定义 v1 `design-tree-document.schema.json` 与 `design-operation.schema.json`，覆盖嵌套节点、插入子树、移动、删除、文本、样式 patch、布局和组件替换
- [x] 1.4 编写合法登录页 Tree 与预期 Graph fixture，覆盖 Flex、absolute、文本、资源、令牌及至少一个 Ant Design 组件实例
- [x] 1.5 添加契约 Schema 单元测试：验证合法 fixture 通过，并验证不兼容版本、CSS 字符串、重复 ID 与非法联合类型被拒绝

## 2. TypeScript DSL 内核

- [x] 2.1 新增 `packages/design-dsl` 工作区包及公开导出，定义由 v1 契约派生或同步的 TypeScript 领域类型与结构化错误结果
- [x] 2.2 实现 Tree 结构、布局、资源、令牌与组件引用校验，并实现确定性的 Tree → Graph 规范化，保留合法 ID 与 child 顺序
- [x] 2.3 实现 Graph 不变量校验与 Graph → Tree 反规范化，拒绝循环、孤儿、缺失引用、重复 child 和父子关系不一致
- [x] 2.4 实现副本上的 `DesignOperation[]` 原子应用，支持所有 v1 操作并保证失败批次不改变原文档
- [x] 2.5 添加规范化与反规范化单元测试：以 fixture 验证 Tree → Graph、Graph → Tree → Graph 往返和 canonicalize 不变量
- [x] 2.6 添加操作处理器单元测试：覆盖成功混合批次、节点冲突、期望父节点冲突、非法索引、非法组件引用和无半更新保证

## 3. Go API 侧契约边界

- [x] 3.1 在 `apps/api/internal/design` 建立最小领域模块，定义输入大小限制、稳定错误与版本检查入口，不新增设计文档 HTTP 路由
- [x] 3.2 实现 Go 对 v1 Schema 和 Graph 约束的解析、校验及支持的低次版本迁移，拒绝不兼容主版本与未来版本
- [x] 3.3 实现持久化前边界，保留原始版本、迁移警告与规范化 Graph；确保无效输入不进入持久化调用
- [x] 3.4 添加 Go 单元测试：复用 v1 fixture 验证解析、Tree/Graph 往返、版本拒绝和损坏 Graph 错误
- [x] 3.5 添加 Go 集成测试：验证 API 设计领域边界对超限、无效与可迁移输入的稳定错误或警告结果，且不暴露内部细节

## 4. 预览与代码派生适配器

- [x] 4.1 实现只消费已校验 Graph 的 DOM/CSS 预览输入适配器，映射可见性、结构化样式、Flex、absolute、尺寸策略和有序子节点，且不渲染 Root
- [x] 4.2 实现 `react-tailwind-antd` 代码生成器接口，派生 token、布局和基础原子节点的 React/Tailwind 输出
- [x] 4.3 实现 `ui.button`、`ui.input`、`ui.card`、`ui.form` 和 `ui.menu` 的组件绑定校验与 Ant Design import/JSX 输出，对未知或无效绑定返回结构化错误
- [x] 4.4 添加派生适配器单元测试：验证 DOM 输入和代码输出保持节点顺序、可见性、布局意图、token 引用与组件语义
- [x] 4.5 添加代码生成器单元测试：验证合法组件输出、未知绑定和非法 overrides 的错误行为，以及生成代码不影响输入 Graph

## 5. 契约同步与验证

- [x] 5.1 更新相关工作区公开导出、依赖声明和 OpenSpec 制品，确认共享包不依赖应用包且 API 不承担 DOM 或 JSX 职责
- [x] 5.2 对 TypeScript 变更执行格式化、相关单元测试、lint、类型检查和构建
- [x] 5.3 对 Go 变更执行 `gofmt`、相关单元测试、集成测试、静态检查、类型检查和构建
- [x] 5.4 审查 v1 版本演进、原始文档保留与回滚边界；将 Canvas/SVG 像素级一致性、协作、历史、撤销重做与代码反向同步记录为明确的后续风险，而不纳入本次验收
