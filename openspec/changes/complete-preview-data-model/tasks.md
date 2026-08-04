## 1. 团队设计系统契约

- [x] 1.1 在 `packages/design-contract` 增加不可变版本化 `DesignSystemProfile` Schema，覆盖 Token、typography、组件/variant/命名 slot/overrides、布局能力、图标目录、资源策略以及 Profile ID/版本/内容摘要
- [x] 1.2 增加至少一个团队风格 Profile fixture 和由其确定性派生的 `DesignGenerationContract` fixture，覆盖允许节点/字段、组件、语义 Token、布局限制及固定 Profile 引用
- [x] 1.3 在 `packages/design-dsl/src/types.ts` 增加 Profile 类型和 DesignDocument 的 Profile ID/版本/内容摘要引用；移除 DesignDocument 对团队 Token、组件定义和目标 ComponentBinding 的事实所有权，文档级覆盖只保留 Profile 明确允许的部分

## 2. 领域与渲染数据类型

- [x] 2.1 在 `packages/design-dsl/src/types.ts` 提取并公开 Asset 领域类型，保持现有 `Meta.assets` 数据结构与公开契约兼容
- [x] 2.2 在 `packages/design-dsl/src/derive.ts` 定义 Frame、Text、Image、Icon 和 Component Instance 的 `DesignRenderNode` 判别联合，并定义稳定 ID、可见性、样式、布局项、语义和空叶子子节点等共享字段
- [x] 2.3 为各渲染节点类型补齐专属字段：Frame 的布局、Text 的文本与字体、Image 的已校验资源引用与资源数据、Icon 的名称、Component Instance 的引用/变体/命名 slot/覆盖值及 Profile 组件语义契约；目标 binding 不进入渲染节点
- [x] 2.4 定义携带 Profile ID/版本/内容摘要、Profile Token 视图、节点、Asset 和校验凭据的 `ValidatedDesignRenderModel`

## 3. Profile 校验与 DSL 派生

- [x] 3.1 增加 Profile 驱动的 Tree 校验，拒绝未知 Token、组件、variant、命名 slot、override、图标、资源和不允许的布局能力
- [ ] 3.2 统一首次 Tree、`DesignOperation[]`、导入、迁移和 Profile 重绑定写入口，按 Schema → Profile 解析与语义校验 → 原子规范化/应用 → Graph 校验 → 持久化执行，并透传带 Profile ID/版本/内容摘要、operation 索引和 DSL 路径的结构化错误
- [x] 3.3 实现 `deriveDesignRenderModel`，按节点 `kind` 构造类型安全的渲染节点、原样保留 Token 引用，并将结果绑定到文档固定的 Profile 引用
- [x] 3.4 保持 Root 不输出、稳定节点 ID 不变，并严格按照 Root 与 Frame 的 `childIds` 顺序派生嵌套节点
- [x] 3.5 通过文档资源表和组件表解析 Image 与 Component Instance 的跨表引用，同时确保派生过程不修改输入 Graph
- [x] 3.6 保留现有 `deriveDomPreview` 和 `PreviewNode` 兼容入口，保持参数、Result 结构和既有公共字段兼容；新调用方只使用 `deriveDesignRenderModel`、`DesignRenderModel` 与 `DesignRenderNode`

## 4. 设计稿渲染适配

- [x] 4.1 在 `packages/ui` 增加对 `@repo/design-dsl` 公开导出的 workspace 依赖，复用当前 Ant Design 依赖且不引入其他第三方包
- [x] 4.2 定义公开 `DesignRenderAdapter`、`ThemeResolver`、`LayoutMapper`、`ComponentRegistry`、`IconRegistry` 和 `AssetResolver` 接口，要求适配器声明目标标识、支持的 Profile 范围和能力集合，并明确它们只能执行 ValidatedDesignRenderModel
- [x] 4.3 实现默认 `ThemeResolver`，按 Profile 锁定值 → Profile 明确允许且已校验的文档 override → 结构化错误解析语义 Token、颜色、间距、圆角、阴影、字体和 typography
- [x] 4.4 实现默认 `LayoutMapper`，覆盖 Profile 允许的 Flex/absolute/尺寸策略；渲染器只依赖适配器接口
- [x] 4.5 实现默认 Ant Design、图标和 Asset 适配器，将目标 ComponentBinding 保留在适配器内部；对不兼容 Profile 返回 `adapter_incompatible`，对未实现能力返回结构化适配错误或安全占位

## 5. 设计稿渲染器

- [x] 5.1 为五个默认 Ant Design 注册项分别实现 variant/overrides 白名单转换，保留 Profile 允许的组件内容和属性，禁止未知 overrides 直接展开到组件或 DOM
- [x] 5.2 实现只依赖 `DesignRenderAdapter` 的 Frame、Text、Image、Icon、Component Instance 函数式递归渲染策略，跳过不可见节点并使用稳定 ID 作为 React key 与 `data-design-node-id`
- [x] 5.3 新增公开 `@repo/ui/blocks/design-renderer` 组合组件及局部样式，通过 Props 接收 ValidatedDesignRenderModel、可选渲染适配器和错误边界；拒绝裸节点数组、独立 Token 表和不兼容适配器，不读取应用接口、路由或环境变量

## 6. 验证

- [ ] 6.1 【单元测试】验证 Profile 对未知 Token、组件、variant、命名 slot、override、图标、资源和布局能力的拒绝行为，以及同 ID/版本摘要漂移失败
- [ ] 6.2 【单元测试】扩展 `packages/design-dsl/src/derive.test.ts`，验证文本内容/字体、图片 Asset、图标名称、组件属性、稳定 ID、顺序和 Token 保留
- [ ] 6.3 【单元测试】验证无效 Graph、未知 Asset 和未知组件返回可定位结构化错误且不产生部分渲染节点
- [ ] 6.4 【单元测试】覆盖默认 ThemeResolver、LayoutMapper、Ant Design、Icon 和 Asset 适配器，以及未实现能力错误
- [ ] 6.5 【单元测试】验证同一 Profile 下自定义 `DesignRenderAdapter` 可以替换目标渲染实现但不能放宽 Profile 约束，并验证默认适配器不兼容时失败关闭
- [ ] 6.6 【集成测试】验证 DesignTreeDocument 与 DesignOperation 经过同一固定摘要 Profile 校验、规范化和 DesignRenderer 后保持节点 ID、顺序和语义一致
- [ ] 6.7 【兼容测试】验证 `deriveDomPreview`/`PreviewNode` 旧调用方仍可读取既有字段，且内部结果与 `deriveDesignRenderModel` 一致
- [ ] 6.8 【集成测试】运行 `@repo/design-dsl` 与 `@repo/ui` 现有 lint 和类型检查，确认跨包公开接口、渲染组件和默认适配器兼容
