## ADDED Requirements

### Requirement: 运行时 Tree 数据接口
系统 SHALL 提供通用递归 `TreeNodeData<T>[]` 输入，其中每个节点 MUST 具有整棵树内唯一的非空字符串 key，并可携带标签、图标、业务数据、禁用状态、叶节点标记与 children。Tree 控件 MUST 将输入数据视为只读，不得把选择、展开、搜索、加载或拖拽状态写入节点对象。

#### Scenario: 渲染合法递归数据
- **WHEN** 调用方传入具有唯一 key 的多层 TreeNodeData
- **THEN** 控件按 children 顺序渲染层级，并在事件中返回原节点及稳定 key

#### Scenario: 拒绝重复或空 key
- **WHEN** TreeNodeData 包含空 key 或整棵树内重复 key
- **THEN** 控件提前返回稳定错误或不渲染无效 Tree，且不继续构建索引和交互状态

### Requirement: 展开状态控制
系统 SHALL 支持 `expandedKeys` 受控模式与 `defaultExpandedKeys` 非受控模式，并通过展开变化事件返回下一组 key、触发节点和展开状态。受控值存在时，控件 MUST NOT 在调用方回传新值前自行改变受控展开状态。

#### Scenario: 非受控展开节点
- **WHEN** 用户展开一个具有 children 的非受控节点
- **THEN** 控件显示其直接 children 并发出包含下一组 expanded keys 的事件

#### Scenario: 受控展开保持调用方值
- **WHEN** 用户操作受控 Tree 的展开按钮但调用方未更新 expandedKeys
- **THEN** 控件发出变化事件且显示状态继续匹配当前 expandedKeys

### Requirement: 选择与勾选状态
系统 SHALL 将节点选择与节点勾选建模为相互独立的状态轴。选择 MUST 支持 none、single 和 multiple；勾选 MUST 支持 related 与 independent 关系、禁用节点、禁止勾选节点和 leafOnly 返回策略，并在 related 模式计算祖先半选状态。

#### Scenario: 单选节点
- **WHEN** selection mode 为 single 且用户选择可用节点
- **THEN** 下一组 selected keys 只包含该节点并触发选择变化事件

#### Scenario: 关联勾选传播
- **WHEN** check relation 为 related 且用户勾选具有可勾选后代的节点
- **THEN** 控件勾选其可勾选后代并根据后代状态计算祖先的 checked 或 halfChecked 状态

#### Scenario: 独立勾选不传播
- **WHEN** check relation 为 independent 且用户切换一个节点
- **THEN** 只有该节点的 checked 状态变化，祖先和后代保持不变

#### Scenario: 禁用节点不响应状态变更
- **WHEN** 用户尝试选择 disabled 节点或勾选 disabled、disableCheckbox 节点
- **THEN** 控件不改变对应状态且不发出成功变更事件

### Requirement: 搜索与过滤视图
系统 SHALL 支持受控或非受控搜索文本、默认标签匹配、自定义 filterNode、自动显示匹配节点祖先以及仅显示匹配分支。搜索展开 MUST 是派生视图，不得覆盖调用方的 expandedKeys；清空搜索后 MUST 恢复非搜索展开视图。

#### Scenario: 搜索显示匹配路径
- **WHEN** 搜索文本匹配一个折叠的深层节点
- **THEN** 控件显示该节点及其祖先路径，并向渲染上下文提供 matched 与 searchValue

#### Scenario: 清空搜索恢复展开状态
- **WHEN** 用户清空已有搜索文本
- **THEN** 搜索产生的临时展开消失，控件重新使用搜索前的受控或非受控 expanded keys

### Requirement: 异步子节点加载
系统 SHALL 在提供 loadChildren 时支持按节点异步加载。首次展开尚未加载且没有 children 的非叶节点 MUST 调用加载函数，并在 Promise 期间显示 loading；成功后 MUST 更新 loaded 状态，失败后 MUST 清除 loading、保留可重试状态并提供失败事件。同一 key 的并发加载 MUST 合并为一次调用。

#### Scenario: 成功加载子节点
- **WHEN** 用户展开尚未加载的非叶节点且 loadChildren 成功完成
- **THEN** 控件按顺序发出 loading 与 loaded 状态变化，并在调用方回传新 treeData 后显示 children

#### Scenario: 加载失败后重试
- **WHEN** loadChildren 拒绝且用户再次展开该节点
- **THEN** 节点不被标记为 loaded，控件允许重新调用 loadChildren

#### Scenario: 合并并发加载
- **WHEN** 同一节点在加载完成前被多次触发展开
- **THEN** 控件只保持一个进行中的 loadChildren 调用

### Requirement: 拖拽落点意图
系统 SHALL 在启用拖拽时计算 before、inside、after 三种落点，并向 canDrop 与 onDrop 提供 dragKey、targetKey、position 和对应节点。控件 MUST NOT 直接修改 treeData，并 MUST 拒绝拖入自身或自身后代。

#### Scenario: 发出合法落点
- **WHEN** 用户把可拖拽节点放到 canDrop 接受的目标位置
- **THEN** 控件发出结构化 onDrop 意图并等待调用方更新 treeData

#### Scenario: 拒绝循环落点
- **WHEN** 用户试图把节点放入自身或任一后代内部
- **THEN** 控件标记该落点无效且不发出成功 onDrop 事件

### Requirement: 组合式节点渲染
系统 SHALL 提供默认的缩进、展开按钮、图标、勾选框、标签和状态渲染，并允许调用方定制标签、图标、整行节点和空状态。自定义节点渲染上下文 MUST 仅暴露稳定节点数据、公开状态和必要动作，不得暴露内部索引、扁平节点或虚拟列表实现。

#### Scenario: 自定义整行节点
- **WHEN** 调用方提供 renderNode
- **THEN** 控件向其传入节点、深度、展开、选择、勾选、半选、禁用、加载和匹配状态，并保留 Tree 必需的语义和交互连接

#### Scenario: 空数据内容
- **WHEN** treeData 为空或搜索没有可显示节点
- **THEN** 控件显示默认或调用方提供的 emptyContent，且不存在可聚焦 treeitem

### Requirement: 虚拟化与节点定位
系统 SHALL 支持可选虚拟化配置，并使用与普通模式相同的可见扁平列表和交互状态。运行时句柄 MUST 支持按 key 将可见节点滚动到 start、center、end 或 auto 对齐位置；未知或当前不可见 key MUST 返回失败结果且不得抛出未处理异常。

#### Scenario: 虚拟化大规模节点
- **WHEN** 启用虚拟化并展开大量节点
- **THEN** 控件仅挂载视口及 overscan 范围内的行，同时保持选择、搜索和键盘状态一致

#### Scenario: 定位可见节点
- **WHEN** 调用方通过句柄滚动到一个当前可见 key
- **THEN** 控件按请求对齐方式定位对应行并返回成功结果

### Requirement: Tree 可访问性与键盘交互
系统 SHALL 实现 WAI-ARIA Tree 语义、单一 roving tabindex 焦点和键盘导航。方向键 MUST 在可见节点间移动或展开收起，Home 与 End MUST 定位首尾可见节点，Enter MUST 执行选择，Space MUST 执行勾选；过滤或折叠后不可见节点 MUST NOT 保留可聚焦状态。

#### Scenario: 键盘遍历可见节点
- **WHEN** Tree 获得焦点且用户按上下方向键、Home 或 End
- **THEN** 焦点仅在当前可见且可聚焦的 treeitem 间按视觉顺序移动

#### Scenario: 键盘展开和收起
- **WHEN** 焦点位于具有 children 的节点且用户按右方向键或左方向键
- **THEN** 控件分别展开、进入首个子节点、收起或返回父节点，并发出适用的展开事件

#### Scenario: 暴露节点语义状态
- **WHEN** 节点被渲染为 treeitem
- **THEN** 控件提供正确的 aria-level、aria-expanded、aria-selected、aria-checked、aria-posinset 和 aria-setsize
