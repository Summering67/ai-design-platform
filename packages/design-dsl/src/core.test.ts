import {
  applyOperations,
  denormalize,
  normalize,
  validateDocument,
  validateTree,
} from "./core.js";
import type { TreeDocument } from "./types.js";

const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message);
};
const tree: TreeDocument = {
  version: "1.0.0",
  id: "document",
  name: "测试",
  assets: {},
  tokens: {},
  componentDefinitions: {
    "ui.button": {
      id: "ui.button",
      propsSchema: {},
      appearance: {
        id: "appearance",
        kind: "text",
        text: "按钮",
        typography: {},
      },
    },
  },
  componentBindings: {
    "ui.button": {
      componentRef: "ui.button",
      target: "react-tailwind-antd",
      codeBinding: { importFrom: "antd", exportName: "Button" },
    },
  },
  pages: [
    {
      id: "page",
      name: "页面",
      rootId: "root",
      children: [
        {
          id: "frame",
          kind: "frame",
          layout: { mode: "flex", direction: "column" },
          children: [
            { id: "text", kind: "text", text: "你好", typography: {} },
            {
              id: "button",
              kind: "component-instance",
              componentRef: "ui.button",
            },
          ],
        },
      ],
    },
  ],
};

const normalized = normalize(tree);
assert(normalized.ok, "合法 Tree 必须规范化");
if (normalized.ok) {
  const restored = denormalize(normalized.value);
  assert(restored.ok, "合法 Graph 必须反规范化");
  if (restored.ok) {
    const rebuilt = normalize(restored.value);
    assert(
      rebuilt.ok &&
        JSON.stringify(rebuilt.value) === JSON.stringify(normalized.value),
      "往返必须保持 Graph",
    );
  }
  const updated = applyOperations(normalized.value, [
    { type: "set-text", pageId: "page", nodeId: "text", text: "已更新" },
  ]);
  assert(
    updated.ok &&
      updated.value.pages[0]?.nodes.text?.kind === "text" &&
      updated.value.pages[0].nodes.text.text === "已更新",
    "文本操作必须更新副本",
  );
  const rejected = applyOperations(normalized.value, [
    {
      type: "replace-component",
      pageId: "page",
      nodeId: "button",
      componentRef: "unknown",
    },
  ]);
  assert(
    !rejected.ok &&
      normalized.value.pages[0]?.nodes.button?.kind === "component-instance" &&
      normalized.value.pages[0].nodes.button.componentRef === "ui.button",
    "失败操作不得修改原文档",
  );
}
assert(
  !validateTree({ ...tree, version: "1.0.1" } as unknown as TreeDocument).ok,
  "不兼容版本必须拒绝",
);
assert(
  !validateDocument({ ...tree, pages: [] } as never).ok,
  "非法 Graph 必须拒绝",
);
