import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import type { DesignDocument } from "@repo/design-dsl";
import { DesignDocumentRenderer } from "./index";

const document: DesignDocument = {
  version: "2.0.0",
  id: "geometry-test",
  name: "Geometry Test",
  designSystem: { id: "system", version: "1.0.0", digest: "sha256:test", tokens: {}, components: {} },
  assets: {},
  root: {
    id: "root",
    kind: "element",
    name: "Root",
    tag: "div",
    style: { backgroundColor: "white" },
    props: {},
    children: [{ id: "title", kind: "text", name: "Title", tag: "h1", style: {}, props: {}, children: [], text: "Hello" }],
  },
  resolvedLayouts: {
    desktop: {
      viewport: { width: 320, height: 200 },
      nodes: {
        root: { x: 0, y: 0, width: 320, height: 200 },
        title: { x: 24, y: 32, width: 120, height: 40 },
      },
    },
  },
};

test("Renderer 按 Geometry 生成绝对定位样式", () => {
  const markup = renderToStaticMarkup(<DesignDocumentRenderer document={document} viewportId="desktop" />);
  assert.match(markup, /left:24px/);
  assert.match(markup, /top:32px/);
  assert.match(markup, /width:120px/);
  assert.match(markup, /height:40px/);
});

test("Renderer 拒绝缺失 viewport Geometry", () => {
  const errors: string[] = [];
  const markup = renderToStaticMarkup(
    <DesignDocumentRenderer document={document} viewportId="mobile" onError={(message) => { errors.push(message); return null; }} />,
  );
  assert.equal(markup, "");
  assert.deepEqual(errors, ["缺少 viewport mobile 的 Geometry"]);
});
