import assert from "node:assert/strict";
import test from "node:test";

import { retryGenerationPath } from "./retry-generation.ts";

const messages = [
  { id: "server-message", client_message_id: "client-message", role: "user", content: "?" },
  { id: "assistant-message", role: "assistant", content: "回复" },
];

test("停止后用乐观消息 ID 重试时，请求地址使用后端消息 ID", () => {
  assert.equal(
    retryGenerationPath("project", messages, "client-message"),
    "/projects/project/messages/server-message/generations",
  );
});

test("刷新后用后端消息 ID 重试，找不到消息时不发起请求", () => {
  assert.equal(
    retryGenerationPath("project", messages, "server-message"),
    "/projects/project/messages/server-message/generations",
  );
  assert.equal(retryGenerationPath("project", messages, "missing"), null);
  assert.equal(retryGenerationPath("project", messages, "assistant-message"), null);
});
