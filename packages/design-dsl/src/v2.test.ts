import fixture from "@repo/design-contract/fixtures/v2/login-page.document.json" with { type: "json" };
import {
  applyV2Operations,
  collectDesignDependencies,
  deriveV2RenderModel,
  fromDesignGraph,
  toDesignGraph,
  validateDesignDocument,
} from "./v2.js";
import type { DesignDocument } from "@repo/design-contract";

const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message);
};

const document = fixture as DesignDocument;
const checked = validateDesignDocument(document);
assert(checked.ok, "v2 fixture 必须通过校验");

const graph = toDesignGraph(document);
assert(graph.ok, "合法文档必须建立 Graph");
if (graph.ok) {
  const restored = fromDesignGraph(document, graph.value);
  assert(
    restored.ok && JSON.stringify(restored.value) === JSON.stringify(document),
    "Tree → Graph → Tree 必须保持文档结构",
  );
}

const dependencies = collectDesignDependencies(document);
assert(
  dependencies.ok &&
    dependencies.value.length === 1 &&
    dependencies.value[0]?.componentName === "Button",
  "组件依赖必须去重并保持稳定",
);
const beforeRender = JSON.stringify(document);
const renderModel = deriveV2RenderModel(document);
assert(renderModel.ok, "合法文档必须派生渲染模型");
assert(JSON.stringify(document) === beforeRender, "渲染派生不得修改输入文档");
const secondRenderModel = deriveV2RenderModel(document);
assert(
  secondRenderModel.ok &&
    JSON.stringify(secondRenderModel.value) ===
      JSON.stringify(renderModel.ok ? renderModel.value : null),
  "相同文档的重复派生结果必须一致",
);

const updated = applyV2Operations(document, [
  { type: "set-text", nodeId: "title", text: "已更新" },
]);
assert(
  updated.ok && updated.value.root.children[1]?.text === "已更新",
  "文本操作必须生成新的规范文档",
);
assert(document.root.children[1]?.text === "欢迎登录", "操作不得修改输入文档");

const failed = applyV2Operations(document, [
  { type: "remove-node", nodeId: "missing" },
]);
assert(!failed.ok, "无效操作必须失败");

const layoutUpdated = applyV2Operations(document, [
  {
    type: "patch-style",
    nodeId: "root",
    patches: { backgroundColor: "#f8fafc" },
  },
  { type: "patch-layout", nodeId: "root", patches: { direction: "row" } },
  {
    type: "patch-layout-item",
    nodeId: "submit",
    patches: { width: { mode: "fixed", value: 240 } },
  },
]);
assert(
  layoutUpdated.ok &&
    !layoutUpdated.value.resolvedLayouts &&
    layoutUpdated.value.root.style.backgroundColor === "#f8fafc" &&
    layoutUpdated.value.root.layout?.direction === "row" &&
    layoutUpdated.value.root.children[2]?.layoutItem?.width?.mode === "fixed",
  "布局和样式操作必须更新文档并清除旧 Geometry",
);
assert(
  document.root.style.backgroundColor !== "#f8fafc",
  "布局操作不得修改输入文档",
);
