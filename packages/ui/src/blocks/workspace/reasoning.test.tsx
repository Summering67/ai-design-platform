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
  assert.match(markup, /思考过程/)
  assert.doesNotMatch(markup, /requirement/)
  assert.doesNotMatch(markup, /<details[^>]*open/)
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
        content: "先检查画布\n正在分析界面结构",
        status: "reasoning",
      }]}
      status="loading"
    />,
  )
  assert.match(markup, /正在分析界面结构/)
  assert.match(markup, /正在思考/)
  assert.doesNotMatch(markup, /ui_design/)
  assert.doesNotMatch(markup, /<details[^>]*open/)
})

test("工作台明确提示模型思考内容已截断", () => {
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
        stage: "auto_layout",
        taskId: "task",
        attempt: 1,
        content: "已展示的思考内容",
        status: "truncated",
      }]}
      status="loading"
    />,
  )
  assert.match(markup, /思考内容已达到展示上限/)
})

test("工作台按 reasoning、临时助手正文和持久化消息稳定排列", () => {
  const markup = renderToStaticMarkup(
    <Workspace
      accountEmail="developer@local.test"
      document={null}
      error={null}
      messages={[{ id: "saved", role: "assistant", content: "已保存回答" }]}
      onLogout={() => undefined}
      onRetry={() => undefined}
      onSend={() => undefined}
      onStop={() => undefined}
      projectTitle="测试项目"
      reasoning={[{
        id: "run:task:1",
        stage: "root",
        taskId: "task",
        attempt: 1,
        content: "正在分析",
        status: "reasoning",
      }]}
      status="loading"
      streamingMessage={{ id: "streaming-assistant", content: "临时回答" }}
    />,
  )
  assert.ok(markup.indexOf("已保存回答") < markup.indexOf("正在分析"))
  assert.ok(markup.indexOf("正在分析") < markup.indexOf("临时回答"))
  assert.doesNotMatch(markup, /streaming-assistant/)
})

test("空流式正文不会创建临时助手条目", () => {
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
      reasoning={[]}
      status="loading"
      streamingMessage={null}
    />,
  )
  assert.doesNotMatch(markup, /streaming-assistant/)
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
