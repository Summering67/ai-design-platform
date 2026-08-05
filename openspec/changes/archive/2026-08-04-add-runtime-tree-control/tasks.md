## 1. 公开接口与纯函数内核

- [x] 1.1 在 `packages/ui` 定义并导出泛型 `TreeNodeData<T>`、分组配置、状态变化详情、拖拽意图、渲染上下文与 `TreeHandle` 类型，保持字符串 key 和只读 treeData 约束
- [x] 1.2 实现 Tree 数据前置校验，遇到空 key、重复 key 或非法 children 时提前返回稳定结果
- [x] 1.3 实现私有节点索引、祖先与后代查询、可见节点扁平化及同级位置派生，不导出或持久化内部结构
- [x] 1.4 实现 related、independent、leafOnly、disabled 与 disableCheckbox 组合下的 checked 和 halfChecked 纯函数
- [x] 1.5 【单元测试】覆盖数据校验、索引、扁平化、祖先后代查询和全部勾选传播规则

## 2. 基础 Tree 与受控状态

- [x] 2.1 新增函数式 `Tree<T>` 客户端组件，接入 treeData、全局禁用、样式透传、默认空状态和公开子路径导出
- [x] 2.2 实现展开状态的受控与非受控模式，以及包含下一组 keys、触发节点和展开状态的变化事件
- [x] 2.3 实现 none、single、multiple 选择与独立勾选状态轴，确保受控值未回传时显示状态不自行变化
- [x] 2.4 实现默认节点行、缩进、展开按钮、图标、勾选框、标签和加载状态，并提供 renderLabel、renderIcon、renderNode 与 emptyContent 扩展点
- [x] 2.5 【集成测试】覆盖受控与非受控展开、选择、勾选、禁用节点、半选视觉状态和自定义节点渲染

## 3. 搜索与异步加载

- [x] 3.1 实现受控与非受控搜索输入、默认标签匹配、自定义 filterNode、匹配上下文和 showMatchedOnly
- [x] 3.2 实现搜索祖先自动展开的派生视图，并在清空搜索后恢复原 expanded keys，不修改受控展开状态
- [x] 3.3 实现 loadChildren、受控与非受控 loaded keys、loading 状态、失败事件和失败重试
- [x] 3.4 合并同一节点的并发加载请求，并在 treeData 更新后继续使用调用方提供的 children
- [x] 3.5 【单元测试】覆盖搜索匹配路径、仅显示匹配分支、清空搜索恢复展开、加载成功、加载失败重试和并发请求合并

## 4. 拖拽、虚拟化与可访问性

- [x] 4.1 实现 before、inside、after 拖拽落点计算、canDrop 校验和结构化 onDrop 意图，不直接重排 treeData
- [x] 4.2 拒绝拖入自身或后代，并处理调用方拒绝、禁用节点和无效目标的落点状态
- [x] 4.3 使用现有 `react-virtuoso` 接入可选虚拟化，让普通模式与虚拟模式共享同一可见扁平列表
- [x] 4.4 实现 `TreeHandle.scrollToKey`，对可见、不可见和未知 key 返回稳定结果并支持 start、center、end、auto 对齐
- [x] 4.5 实现 tree/treeitem 语义、aria 层级与集合属性、roving tabindex，以及方向键、Home、End、Enter、Space 交互
- [x] 4.6 【集成测试】覆盖合法与循环拖拽落点、虚拟列表挂载范围、scrollToKey、ARIA 属性和完整键盘导航

## 5. 验证与边界确认

- [x] 5.1 为 `packages/ui` 接入完成单元测试和组件集成测试所需的最小开发测试能力，不新增运行时依赖或仓库级测试命令
- [x] 5.2 【单元测试】运行 Tree 纯函数相关测试并确认全部通过
- [x] 5.3 【集成测试】运行 Tree 组件交互相关测试并确认全部通过
- [x] 5.4 运行 `packages/ui` 现有格式化、lint、类型检查和构建相关检查，只处理本变更引入的问题
