import { deriveDomPreview, generateReactTailwindAntd } from "./derive.js";
import { normalize } from "./core.js";
import type { TreeDocument } from "./types.js";

const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message);
};
const tree: TreeDocument = {
  version: "1.0.0",
  id: "document",
  name: "测试",
  assets: {},
  tokens: { primary: "#1677ff" },
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
          id: "button",
          kind: "component-instance",
          componentRef: "ui.button",
          overrides: { children: "提交" },
        },
      ],
    },
  ],
};
const document = normalize(tree);
assert(document.ok, "测试文档必须规范化");
if (document.ok) {
  const preview = deriveDomPreview(document.value);
  const generated = generateReactTailwindAntd(document.value);
  assert(
    preview.ok && preview.value[0]?.id === "button",
    "预览必须保持节点顺序",
  );
  assert(
    generated.ok &&
      generated.value.code.includes("Button") &&
      generated.value.code.includes("提交"),
    "生成器必须输出 Ant Design 组件",
  );
}
