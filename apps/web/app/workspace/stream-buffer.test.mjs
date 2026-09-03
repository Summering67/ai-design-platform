import assert from "node:assert/strict"
import test from "node:test"

import { createFrameBuffer } from "./stream-buffer.ts"

const setup = () => {
  const callbacks = []
  const flushed = []
  const buffer = createFrameBuffer(
    (values) => flushed.push([...values]),
    (callback) => {
      callbacks.push(callback)
      return callbacks.length
    },
    () => undefined,
  )
  return { buffer, callbacks, flushed }
}

test("帧缓冲合并同一帧并保留顺序", () => {
  const { buffer, callbacks, flushed } = setup()
  buffer.enqueue("先")
  buffer.enqueue("后")
  assert.equal(callbacks.length, 1)
  callbacks[0]()
  assert.deepEqual(flushed, [["先", "后"]])
})

test("帧缓冲支持显式提交并丢弃待处理内容", () => {
  const { buffer, callbacks, flushed } = setup()
  buffer.enqueue("未提交")
  buffer.flush()
  assert.deepEqual(flushed, [["未提交"]])
  buffer.enqueue("将丢弃")
  buffer.discard()
  callbacks[0]?.()
  assert.deepEqual(flushed, [["未提交"]])
})

test("帧缓冲卸载后忽略后续增量且清理幂等", () => {
  const { buffer, callbacks, flushed } = setup()
  buffer.enqueue("待卸载")
  buffer.dispose()
  buffer.dispose()
  buffer.enqueue("忽略")
  callbacks[0]?.()
  assert.deepEqual(flushed, [])
})
