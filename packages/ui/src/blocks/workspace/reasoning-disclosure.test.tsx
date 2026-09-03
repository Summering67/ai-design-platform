// @vitest-environment jsdom

import assert from "node:assert/strict";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, it } from "vitest";

import { ReasoningDisclosure } from "./reasoning-disclosure";

const item = {
  id: "run:task:1",
  stage: "requirement",
  taskId: "task",
  attempt: 1,
  content: "先检查画布\n正在分析界面结构",
  status: "reasoning" as const,
};

const mounted: Array<ReturnType<typeof createRoot>> = [];

afterEach(() => {
  mounted.splice(0).forEach((root) => act(() => root.unmount()));
  document.body.replaceChildren();
});

const renderDisclosure = () => {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted.push(root);
  act(() => root.render(<ReasoningDisclosure item={item} />));
  return container;
};

describe("ReasoningDisclosure", () => {
  it("默认折叠并显示最新思考摘要", () => {
    const container = renderDisclosure();
    const details = container.querySelector("details");
    const summary = container.querySelector("summary");
    assert.equal(details?.open, false);
    assert.equal(summary?.getAttribute("aria-expanded"), "false");
    assert.match(summary?.textContent ?? "", /正在分析界面结构/);
    assert.doesNotMatch(summary?.textContent ?? "", /requirement/);
  });

  it("支持点击、Enter 和 Space 展开或收起", () => {
    const container = renderDisclosure();
    const details = container.querySelector("details");
    const summary = container.querySelector("summary");
    assert.ok(details && summary);

    act(() => summary.click());
    assert.equal(details.open, true);
    assert.equal(summary.getAttribute("aria-expanded"), "true");

    act(() => summary.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    assert.equal(details.open, false);
    act(() => summary.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true })));
    assert.equal(details.open, true);
  });
});
