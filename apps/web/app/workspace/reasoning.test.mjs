import assert from "node:assert/strict"
import test from "node:test"

import { applyReasoningEvent } from "./reasoning.ts"

test("按任务和尝试顺序聚合 reasoning 增量", () => {
  const first = applyReasoningEvent([], {
    event: "progress",
    runId: "run-1",
    taskId: "task-1",
    stage: "requirement",
    attempt: 1,
    payload: { status: "reasoning", delta: "先分析" },
  })
  const second = applyReasoningEvent(first, {
    event: "progress",
    runId: "run-1",
    taskId: "task-1",
    stage: "requirement",
    attempt: 1,
    payload: { status: "reasoning", delta: "需求" },
  })
  assert.deepEqual(second[0], {
    id: "run-1:task-1:1",
    stage: "requirement",
    taskId: "task-1",
    attempt: 1,
    content: "先分析需求",
    status: "reasoning",
  })
  const completed = applyReasoningEvent(second, {
    event: "progress",
    runId: "run-1",
    taskId: "task-1",
    stage: "requirement",
    attempt: 1,
    payload: { status: "completed" },
  })
  assert.equal(completed[0]?.status, "completed")
})

test("reasoning 截断只改变状态，不伪造缺失内容", () => {
  const result = applyReasoningEvent(
    applyReasoningEvent([], {
      event: "progress",
      runId: "run-1",
      taskId: "task-1",
      stage: "root",
      attempt: 1,
      payload: { status: "reasoning", delta: "已收到" },
    }),
    {
      event: "progress",
      runId: "run-1",
      taskId: "task-1",
      stage: "root",
      attempt: 1,
      payload: { status: "reasoning_truncated" },
    },
  )
  assert.equal(result[0]?.content, "已收到")
  assert.equal(result[0]?.status, "truncated")
})

test("Root 完成任务选择后将 reasoning 标记为可展示", () => {
  const result = applyReasoningEvent(
    applyReasoningEvent([], {
      event: "progress",
      runId: "run-1",
      taskId: "root",
      stage: "root",
      attempt: 1,
      payload: { status: "reasoning", delta: "选择需求分析阶段" },
    }),
    {
      event: "progress",
      runId: "run-1",
      taskId: "root",
      stage: "root",
      attempt: 1,
      payload: { status: "reasoning_completed" },
    },
  )
  assert.equal(result[0]?.status, "completed")
})
