import assert from "node:assert/strict"
import test from "node:test"
import { renderToStaticMarkup } from "react-dom/server"

import { Workspace } from "./index"

test("工作台展示已完成阶段的模型思考过程", () => {
  const markup = renderToStaticMarkup(
    <Workspace
      accountEmail="developer@local.test"
      document={null}
      error={null}
      messages={[]}
      onLogout={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
      onStop={() => undefined}
      projectTitle="测试项目"
      reasoning={[
        {
          id: "run:task:1",
          stage: "requirement",
          taskId: "task",
          attempt: 1,
          content: "模型真实 reasoning",
          status: "completed",
        },
      ]}
      status="idle"
    />,
  )
  assert.match(markup, /模型真实 reasoning/)
  assert.doesNotMatch(markup, />requirement</)
})

test("工作台展示任意 Agent 尚未完成的模型思考过程", () => {
  const markup = renderToStaticMarkup(
    <Workspace
      accountEmail="developer@local.test"
      document={null}
      error={null}
      messages={[]}
      onLogout={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
      onStop={() => undefined}
      projectTitle="测试项目"
      reasoning={[{
        id: "run:task:1",
        stage: "ui_design",
        taskId: "task",
        attempt: 1,
        content: "UI Design Agent 正在分析界面结构",
        status: "reasoning",
      }]}
      status="loading"
    />,
  )
  assert.match(markup, /UI Design Agent 正在分析界面结构/)
})

test("工作台展示阻断问题并要求逐题回答", () => {
  const markup = renderToStaticMarkup(
    <Workspace
      accountEmail="developer@local.test"
      document={null}
      error={null}
      inputRequest={{
        id: "request-1",
        generationId: "generation-1",
        round: 1,
        questions: [{
          id: "brand-color",
          header: "品牌颜色",
          question: "品牌主色是什么？",
          isOther: true,
          options: [
            { label: "沿用现有蓝色（推荐）", description: "保持产品视觉一致。" },
            { label: "改用紫色", description: "增强设计工具的创意感。" },
          ],
        }],
      }}
      messages={[]}
      onAnswer={() => undefined}
      onLogout={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
      onStop={() => undefined}
      projectTitle="测试项目"
      reasoning={[]}
      status="awaiting_input"
    />,
  )
  assert.match(markup, /需要你的确认/)
  assert.match(markup, /品牌主色是什么？/)
  assert.match(markup, /沿用现有蓝色（推荐）/)
  assert.match(markup, /保持产品视觉一致。/)
  assert.match(markup, /其他/)
  assert.match(markup, /aria-label="品牌主色是什么？"/)
  assert.match(markup, /aria-label="追问列表"/)
  assert.match(markup, /<button[^>]*value="沿用现有蓝色（推荐）"/)
  assert.match(markup, /<button[^>]*value="改用紫色"/)
  assert.match(markup, /<button[^>]*type="button"[^>]*>提交回答并继续/)
  assert.doesNotMatch(markup, /type="radio"/)
})
