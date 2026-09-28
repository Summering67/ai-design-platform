import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { test } from "vitest";
import type { DesignDocument } from "@repo/design-dsl";
import { DesignDocumentRenderer } from "./index";

const document: DesignDocument = {
  version: "2.0.0",
  id: "flow-renderer-test",
  name: "Flow Renderer",
  designSystem: {
    id: "system",
    version: "1.0.0",
    digest: "sha256:test",
    tokens: {},
    components: {
      Button: { id: "Button", packageName: "antd" },
      Unknown: { id: "Unknown", packageName: "custom" },
    },
    allowedTags: ["Button", "Unknown"],
  },
  assets: {
    logo: {
      id: "logo",
      type: "image",
      src: "/logo.png",
      mimeType: "image/png",
      alt: "Logo",
    },
  },
  root: {
    id: "root",
    kind: "element",
    name: "Root",
    tag: "div",
    style: {},
    layout: {
      mode: "flex",
      direction: "row",
      gap: 8,
      padding: { top: 16, right: 16, bottom: 16, left: 16 },
    },
    props: {},
    children: [
      {
        id: "title",
        kind: "text",
        name: "Title",
        tag: "text",
        style: { fontSize: 24 },
        layoutItem: { width: { mode: "hug" }, height: { mode: "hug" } },
        props: {},
        children: [],
        text: "欢迎",
      },
      {
        id: "logo-node",
        kind: "image",
        name: "Logo",
        tag: "image",
        style: {},
        layoutItem: {
          width: { mode: "fixed", value: 80 },
          height: { mode: "fixed", value: 40 },
        },
        props: {},
        children: [],
        assetId: "logo",
      },
      {
        id: "button",
        kind: "component",
        name: "搜索按钮",
        tag: "Button",
        packageName: "antd",
        style: {},
        layoutItem: { width: { mode: "hug" }, height: { mode: "hug" } },
        props: { children: "搜索", type: "primary" },
        children: [],
      },
      {
        id: "unknown",
        kind: "component",
        name: "自定义组件",
        tag: "Unknown",
        packageName: "custom",
        style: {},
        props: {},
        children: [
          {
            id: "unknown-text",
            kind: "text",
            name: "Fallback",
            tag: "text",
            style: {},
            props: {},
            children: [],
            text: "占位",
          },
        ],
      },
    ],
  },
};

test("Renderer 在没有 resolvedLayouts 时按 Flex 文档渲染", () => {
  const markup = renderToStaticMarkup(<DesignDocumentRenderer document={document} />);
  assert.match(markup, /width:1440px/);
  assert.match(markup, /height:900px/);
  assert.match(markup, /display:flex/);
  assert.match(markup, /flex-direction:row/);
  assert.match(markup, /gap:8px/);
  assert.match(markup, /<span[^>]*>欢迎<\/span>/);
  assert.match(markup, /src="\/logo\.png"/);
  assert.match(markup, /搜\s*索/);
  assert.match(markup, /自定义组件/);
});

test("Renderer 使用稳定节点标识并渲染选中状态", () => {
  const markup = renderToStaticMarkup(
    <DesignDocumentRenderer document={document} selectedNodeId="title" />,
  );
  assert.match(markup, /data-design-node-id="title"/);
  assert.match(markup, /data-design-selected="true"/);
});

test("Renderer 返回文档校验错误而不是抛出异常", () => {
  const errors: string[] = [];
  const invalid = {
    ...document,
    root: { ...document.root, id: "" },
  } as DesignDocument;
  const markup = renderToStaticMarkup(
    <DesignDocumentRenderer
      document={invalid}
      onError={(message) => {
        errors.push(message);
        return null;
      }}
    />,
  );
  assert.equal(markup, "");
  assert.ok(errors.length);
});
