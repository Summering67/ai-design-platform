import assert from "node:assert/strict"
import test from "node:test"
import { renderToStaticMarkup } from "react-dom/server"

import { Workspace } from "./index"

test("工作台分离展示真实模型思考过程", () => {
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
  assert.match(markup, /模型思考过程/)
  assert.match(markup, /模型真实 reasoning/)
  assert.match(markup, /aria-label="模型思考过程"/)
})
