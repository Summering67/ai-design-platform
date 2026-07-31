# AI Design Platform 前端开发规范

## 项目概览

本项目是使用 pnpm workspace 和 Turborepo 管理的前端 monorepo。

- `apps/web`：主业务应用，使用 Next.js、React 和 TypeScript。
- `apps/docs`：文档应用，使用 Next.js、React 和 TypeScript。
- `packages/ui`：跨应用共享的 React UI 组件。
- `packages/eslint-config`：共享 ESLint 配置。
- `packages/typescript-config`：共享 TypeScript 配置。

本文档只约束前端代码。

## 文档作用范围

- 修改任何目录时均遵守本文件。
- 修改 `apps/web` 时，同时遵守 `apps/web/AGENTS.md`。
- 修改 `packages/ui` 时，同时遵守 `packages/ui/AGENTS.md`。
- 子目录文档只补充所在目录的规则；发生冲突时，以距离目标文件最近的文档为准。
- `apps/docs` 当前继承本文件，不单独维护规则。

## Workspace 边界

- 应用代码放在 `apps/*`，共享代码放在 `packages/*`。
- `apps/*` 可以依赖 `packages/*`，`packages/*` 禁止依赖 `apps/*`。
- 仅服务于单个应用的页面、业务组件和业务逻辑保留在对应应用中。
- 只有被多个应用实际需要、API 稳定且不依赖应用环境的代码才放入共享包。
- 跨包调用必须使用目标包的公开导出路径，禁止引用其内部文件。

## 开发规则

- 使用 TypeScript 严格模式，不使用 `any`；不确定数据使用 `unknown` 并进行类型收窄。
- 优先修改已有实现，不创建功能重复的组件、工具或类型。
- 参数无效、数据缺失或条件不满足时提前返回。
- 只修改当前需求涉及的代码，不顺带修复无关问题。
- 不新增当前需求未使用的依赖、配置、脚本或文件。
- 注释只解释设计意图、约束或非显然原因，不复述代码行为。

## 质量检查

- 仓库级代码检查入口为 `pnpm lint`。
- 仓库级类型检查入口为 `pnpm check-types`。
- 当前仓库没有统一测试脚本，不虚构测试流程或测试要求。
- 验证范围应与改动范围一致，不处理本任务之外的存量问题。
