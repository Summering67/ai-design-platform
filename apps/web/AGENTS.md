# Web 应用开发规范

## 定位

`apps/web` 是项目的主业务应用，使用 Next.js App Router、React、TypeScript、Tailwind CSS 和 `@repo/ui`。

修改本目录时，同时遵守仓库根目录的 `AGENTS.md`。

## Next.js

- 遵循 App Router 的目录和路由约定。
- 页面、布局以及只服务于特定路由的组件放在对应路由附近。
- 新增或重构组件时默认使用 Server Component。
- 只有使用事件、状态、客户端 Hook 或浏览器 API 时才添加 `"use client"`。
- 客户端边界应控制在实际需要交互的最小范围。
- 页面负责路由级数据与组件组合，不堆积可独立拆分的复杂实现。

## 组件归属

- shadcn/ui 基础组件统一从 `@repo/ui/components/*` 导入。
- 页面组件和具有业务语义的组件保留在 `apps/web`。
- Next.js 路由、导航和查询参数处理保留在 `apps/web`，不得迁入共享包。
- 迁入 `packages/ui` 的界面组件必须通过 Props 和回调接入应用能力。
- 新增组件前先检查 `@repo/ui/components/*` 是否已有适用实现。
- 优先使用 shadcn/ui 已有的 `variant` 和 `size`，不重复实现已有能力。

## TypeScript 与 React

- 不使用 `any`、非必要类型断言或 `@ts-ignore`。
- Props、事件参数和外部数据必须具有明确类型。
- 优先使用函数式组件和箭头函数。
- 参数或数据无效时提前返回，减少嵌套。
- 不为简单逻辑增加无意义的 Hook、Provider 或包装组件。

## 样式

- 使用 Tailwind CSS 时，优先通过 `@theme` 将 CSS 变量映射为可复用的主题令牌。
- CSS 变量和 `@theme` 配置集中定义在外部 CSS 文件中。
- 禁止在 React 组件中使用 `<style>` 或重复声明全局变量。
- CSS Module 与对应的 TSX/JSX 文件放在同一目录。
- 全局设计变量统一声明在 `@theme` 或 `:root` 中。
- Web 根布局通过 `@repo/ui/globals.css` 加载共享主题样式。

## 样式职责划分

- 简单、一次性的尺寸、间距、排列和对齐优先使用 Tailwind。
- 复杂布局、响应式规则、伪类、动画和多处复用的样式使用 CSS Module。
- 禁止仅为一两个可直接表达的 Tailwind 属性创建 CSS Module Class。
- Class 应表达组件区域、复杂状态或可复用样式，不为每个 JSX 节点机械创建 Class。
- 组件内部结构固定时，可以通过根 Class 的直接子级选择器管理私有节点，选择器嵌套原则上不超过一层。
- CSS Module 已具有局部作用域，类名使用 `header`、`menu`、`account` 等简洁名称，不重复添加组件名称前缀。
- 只有重复使用或具有明确业务含义的尺寸、栏宽和间距才提取为 CSS 变量。
- 不对一次性数值进行过早抽象。

## 可访问性

- 优先使用语义化 HTML 元素。
- 可点击操作使用 `button` 或 `a`，不使用普通元素模拟。
- 仅有图标的按钮必须提供可访问名称。
- 不移除焦点样式，除非提供清晰的替代样式。

## 修改原则

- 只处理当前需求涉及的页面、组件和样式。
- 不顺带重构无关模块或修复无关类型问题。
- 修改后使用本应用已有的 lint 和类型检查入口进行验证。
