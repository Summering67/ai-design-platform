// @vitest-environment jsdom

import assert from "node:assert/strict";
import { act, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, test, vi } from "vitest";
import type { DesignDocument } from "@repo/design-dsl";

import { Workspace } from "./index";

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

vi.mock("react-virtuoso", () => ({
  Virtuoso: ({
    data = [],
    itemContent,
  }: {
    data?: readonly unknown[];
    itemContent: (index: number, item: unknown) => ReactNode;
  }) => (
    <div>
      {data.map((item, index) => (
        <div key={index}>{itemContent(index, item)}</div>
      ))}
    </div>
  ),
}));

const fixed = { mode: "fixed" as const, value: 80 };
const designDocument: DesignDocument = {
  version: "2.0.0",
  id: "position-test",
  name: "位置测试",
  designSystem: {
    id: "system",
    version: "1.0.0",
    digest: "sha256:test",
    tokens: {},
    components: {},
    allowedTags: [],
  },
  assets: {},
  root: {
    id: "root",
    kind: "element",
    name: "根节点",
    tag: "div",
    style: {},
    props: {},
    layout: { mode: "flex", direction: "row" },
    children: [
      {
        id: "auto",
        kind: "element",
        name: "自动节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: { width: fixed, height: fixed },
      },
      {
        id: "next",
        kind: "element",
        name: "相邻节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: { width: fixed, height: fixed },
      },
      {
        id: "left-top",
        kind: "element",
        name: "左上节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: {
          position: "absolute",
          inset: { left: 10, top: 20 },
          width: fixed,
          height: fixed,
        },
      },
      {
        id: "right-bottom",
        kind: "element",
        name: "右下节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: {
          position: "absolute",
          inset: { right: 12, bottom: 14 },
          width: fixed,
          height: fixed,
        },
      },
      {
        id: "both-anchors",
        kind: "element",
        name: "双锚点节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: { position: "absolute", inset: { left: 10, right: 20, top: 5, bottom: 15 } },
      },
      {
        id: "no-anchor",
        kind: "element",
        name: "无锚点节点",
        tag: "div",
        style: {},
        props: {},
        children: [],
        layoutItem: { position: "absolute" },
      },
    ],
  },
};

const mounted: Array<ReturnType<typeof createRoot>> = [];

afterEach(() => {
  mounted.splice(0).forEach((root) => act(() => root.unmount()));
  document.body.replaceChildren();
});

const renderWorkspace = async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mounted.push(root);
  await import("../design-document-renderer");
  await act(async () => {
    root.render(
      <Workspace
        accountEmail="developer@local.test"
        document={designDocument}
        error={null}
        messages={[]}
        onLogout={() => undefined}
        onRetry={() => undefined}
        onSend={() => undefined}
        onStop={() => undefined}
        projectTitle="测试"
        reasoning={[]}
        status="idle"
      />,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  return container;
};

const select = (container: HTMLElement, id: string) => {
  const node = container.querySelector<HTMLElement>(`[data-design-node-id="${id}"]`);
  assert.ok(node, container.textContent ?? "画布节点不存在");
  act(() => node.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })));
  return node;
};

const field = (container: HTMLElement, label: string) => {
  const input = [...container.querySelectorAll<HTMLInputElement>("aside label")]
    .find((item) => item.querySelector("span")?.textContent === label)
    ?.querySelector("input");
  assert.ok(input, `缺少位置字段：${label}`);
  return input;
};

const enter = (input: HTMLInputElement, value: string) => {
  act(() => {
    input.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    assert.ok(setter);
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  assert.equal(input.value, value, "输入阶段未保留草稿");
  assert.equal(input.getAttribute("value"), value, "输入事件未更新 React 草稿");
  assert.equal(document.activeElement, input, "输入框没有获得焦点");
  act(() => input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
  assert.notEqual(document.activeElement, input, "Enter 没有提交输入");
};

test("自动布局节点向四个方向偏移，仍保留 Flex 占位与切换后的配置值", async () => {
  const container = await renderWorkspace();
  const node = select(container, "auto");
  const sibling = container.querySelector<HTMLElement>('[data-design-node-id="next"]');
  assert.ok(sibling);
  assert.equal(node.parentElement?.style.display, "flex");
  for (const [axis, value, property] of [
    ["X", "-20", "left"],
    ["X", "20", "left"],
    ["Y", "-15", "top"],
    ["Y", "15", "top"],
  ] as const) {
    enter(field(container, axis), value);
    assert.equal(container.querySelector('[role="alert"]')?.textContent, undefined, "DSL 更新失败");
    assert.equal(field(container, axis).value, value, "提交后配置值未更新");
    assert.equal(node.style[property], `${value}px`);
    assert.equal(node.style.position, "relative");
    assert.equal(sibling.style.position, "");
  }
  select(container, "next");
  assert.equal(field(container, "X").value, "0");
  select(container, "auto");
  assert.equal(field(container, "X").value, "20");
  assert.equal(field(container, "Y").value, "15");
  select(container, "root");
  assert.equal(container.querySelector("aside")?.textContent?.includes("位置偏移"), false);
});

test("绝对定位按已有锚点修改距离，不写入无效负距离", async () => {
  const container = await renderWorkspace();
  const leftTop = select(container, "left-top");
  assert.equal(field(container, "左侧距离").value, "10");
  assert.equal(field(container, "顶部距离").value, "20");
  enter(field(container, "左侧距离"), "30");
  enter(field(container, "顶部距离"), "40");
  assert.equal(leftTop.style.left, "30px");
  assert.equal(leftTop.style.top, "40px");
  assert.equal(leftTop.style.position, "absolute");
  assert.equal(leftTop.style.right, "");
  const rightBottom = select(container, "right-bottom");
  assert.equal(field(container, "右侧距离").value, "12");
  assert.equal(field(container, "底部距离").value, "14");
  enter(field(container, "右侧距离"), "22");
  enter(field(container, "底部距离"), "24");
  assert.equal(rightBottom.style.right, "22px");
  assert.equal(rightBottom.style.bottom, "24px");
  enter(field(container, "右侧距离"), "-1");
  assert.equal(field(container, "右侧距离").value, "22");
  assert.equal(rightBottom.style.right, "22px");
  const both = select(container, "both-anchors");
  enter(field(container, "左侧距离"), "15");
  assert.equal(both.style.left, "15px");
  assert.equal(both.style.right, "15px");
  enter(field(container, "顶部距离"), "10");
  assert.equal(both.style.top, "10px");
  assert.equal(both.style.bottom, "10px");
  enter(field(container, "左侧距离"), "31");
  assert.equal(field(container, "左侧距离").value, "15");
  const noAnchor = select(container, "no-anchor");
  enter(field(container, "左侧距离"), "7");
  enter(field(container, "顶部距离"), "9");
  assert.equal(noAnchor.style.left, "7px");
  assert.equal(noAnchor.style.top, "9px");
});

test("位置字段保留临时输入，无效值失焦后恢复原值", async () => {
  const container = await renderWorkspace();
  const node = select(container, "auto");
  const input = field(container, "X");
  act(() => {
    input.focus();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    assert.ok(setter);
    setter.call(input, "-");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  assert.equal(input.value, "-");
  act(() => input.blur());
  assert.equal(input.value, "0");
  assert.equal(node.style.left, "");
  enter(input, "abc");
  assert.equal(input.value, "0");
  assert.equal(node.style.left, "");
});

test("DSL 拒绝配置时提示原因并保留画布原值", async () => {
  const container = await renderWorkspace();
  const node = select(container, "auto");
  const width = field(container, "固定值");
  act(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    assert.ok(setter);
    setter.call(width, "-1");
    width.dispatchEvent(new Event("input", { bubbles: true }));
  });
  assert.ok(container.querySelector('[role="alert"]')?.textContent);
  assert.equal(node.style.width, "80px");
  enter(field(container, "X"), "12");
  assert.equal(container.querySelector('[role="alert"]'), null);
  assert.equal(node.style.left, "12px");
});
