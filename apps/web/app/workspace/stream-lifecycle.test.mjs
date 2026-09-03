import assert from "node:assert/strict"
import test from "node:test"

import { createFrameBuffer } from "./stream-buffer.ts"

test("完成时先发布 reasoning，再丢弃临时正文并清理两条通道", () => {
  const published = []
  const scheduled = []
  const schedule = (callback) => {
    scheduled.push(callback)
    return scheduled.length
  }
  const cancel = () => undefined
  const reasoning = createFrameBuffer((values) => published.push(["reasoning", ...values]), schedule, cancel)
  const stream = createFrameBuffer((values) => published.push(["stream", ...values]), schedule, cancel)

  reasoning.enqueue("思考增量")
  stream.enqueue("临时正文")
  reasoning.flush()
  stream.discard()

  assert.deepEqual(published, [["reasoning", "思考增量"]])
  reasoning.dispose()
  stream.dispose()
  reasoning.enqueue("忽略")
  stream.enqueue("忽略")
  assert.deepEqual(published, [["reasoning", "思考增量"]])
})
