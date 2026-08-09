import assert from "node:assert/strict"
import test from "node:test"

import { settleGenerationStatus } from "./workspace-status.ts"

test("生成流结束时保留等待回答状态", () => {
  assert.equal(settleGenerationStatus("awaiting_input"), "awaiting_input")
})

test("普通加载完成后恢复为空闲状态", () => {
  assert.equal(settleGenerationStatus("loading"), "idle")
})
