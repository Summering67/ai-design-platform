import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { test } from "vitest";
import type { DesignDocument } from "@repo/design-dsl";
import { DesignDocumentTree } from "./index";

const document: DesignDocument = {
  version: "2.0.0",
  id: "test",
  name: "测试",
  designSystem: {
    id: "system",
    version: "1.0.0",
    digest: "sha256:test",
    tokens: {},
    components: {},
  },
  assets: {},
  root: {
    id: "root",
    kind: "element",
    name: "根",
    tag: "div",
    style: {},
    props: {},
    children: [
      {
        id: "title",
        kind: "text",
        name: "标题",
        tag: "h1",
        style: {},
        props: {},
        children: [],
        text: "你好",
      },
    ],
  },
};

test("设计文档 Tree 映射规范节点并保留层级", () => {
  const markup = renderToStaticMarkup(
    <DesignDocumentTree document={document} defaultExpandedKeys={["root"]} />,
  );
  assert.match(markup, /根 \(div\)/);
  assert.match(markup, /标题 \(h1\)/);
});
