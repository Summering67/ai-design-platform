## ADDED Requirements

### Requirement: Flex Auto Layout 能力
Auto Layout 智能体 SHALL 基于修正后的 v2 `DesignDocument`、StandardizedPRD 响应式要求和 DesignGenerationContract 布局能力，为根图层及其容器生成可验证的 Flex 方向、主轴与交叉轴对齐、间距、内边距、换行和嵌套布局规则。

#### Scenario: 自动排列工具栏
- **WHEN** 图层包含标题、可伸缩空白区和操作按钮组，且契约允许水平 Flex
- **THEN** 输出使用水平排列、合法对齐与间距，并保持标题和按钮的稳定节点 ID

#### Scenario: 契约禁止某布局能力
- **WHEN** 布局计划请求契约未允许的 absolute 定位或尺寸策略
- **THEN** 确定性布局门禁拒绝该计划，不把禁止能力写入最终文档

### Requirement: 尺寸与内容适配策略
Auto Layout 智能体 SHALL 在契约允许范围内表达 hug、fill 和 fixed 尺寸策略，并根据内容类型、父容器约束和同级关系避免负尺寸、无界增长、冲突约束和不可达布局。

#### Scenario: 表单控件填充容器
- **WHEN** PRD 要求窄屏表单占满可用宽度且输入组件支持 fill
- **THEN** 最终文档为输入容器设置合法 fill 策略，并保留按钮的最小可操作尺寸约束

#### Scenario: 固定尺寸发生冲突
- **WHEN** 子节点固定宽度总和超过父容器且不允许换行或滚动
- **THEN** 智能体返回可定位布局错误，不生成相互矛盾的最终约束

### Requirement: 响应式断点适配
Auto Layout 智能体 SHALL 根据标准 PRD 和生成契约允许的断点，为需要变化的容器定义方向、间距、尺寸、换行或可见性覆盖。未声明断点能力时 MUST 保留单一基础布局，不得虚构媒体查询或目标框架语法。

#### Scenario: 桌面双栏转移动单栏
- **WHEN** PRD 要求桌面双栏和移动端单栏，且契约允许相应断点与方向覆盖
- **THEN** 最终文档在固定断点将目标容器从水平布局切换为垂直布局，并保持子节点顺序和身份

#### Scenario: 无响应式能力
- **WHEN** PRD 要求断点适配但 DesignGenerationContract 未提供任何响应式能力
- **THEN** 智能体返回能力不足错误，不在文档中加入未定义断点字段

### Requirement: 图层层级与稳定身份
Auto Layout 变换 MUST 保持页面 ID、业务节点 ID、组件语义和内容。只有现有结构无法表达合法布局时才能增加纯布局容器；新增容器 MUST 使用确定性派生 ID，保持父子引用一致，禁止循环、孤儿、重复子节点和叶子节点持有 children。

#### Scenario: 增加布局分组容器
- **WHEN** 多个兄弟节点需要作为整体参与父容器布局且现有结构无法表达
- **THEN** 智能体增加具有确定性 ID 的 Frame 容器，按原顺序移动节点并保持所有业务节点 ID 不变

#### Scenario: 重复执行布局
- **WHEN** 对相同 PRD、相同修正文档和相同生成契约重复应用确定性布局计划
- **THEN** 输出的图层层级、派生 ID 和布局字段一致，不重复增加容器

### Requirement: 模型规划与确定性应用分离
模型 SHALL 只输出符合版本化布局计划约束的建议，纯函数布局引擎 MUST 负责应用、规范化和校验变换。最终 v2 `DesignDocument` MUST 再次通过 Schema、Profile、稳定 ID、层级和布局能力门禁，未通过时不得返回成功结果。

#### Scenario: 模型计划引用未知节点
- **WHEN** 布局计划包含输入文档不存在的节点 ID
- **THEN** 布局引擎拒绝计划并返回路径明确的错误，不创建猜测节点

#### Scenario: 最终门禁成功
- **WHEN** 布局计划合法且应用后的文档满足全部契约
- **THEN** Auto Layout 智能体返回通过最终门禁的完整 v2 DesignDocument 和布局变更摘要
