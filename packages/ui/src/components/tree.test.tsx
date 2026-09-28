import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { test } from "vitest";

import { Tree, type TreeNodeData } from "./tree";

const treeData: readonly TreeNodeData[] = [
  {
    key: "root",
    label: "根节点",
    children: [
      { key: "child-a", label: "子节点 A" },
      { key: "child-b", label: "子节点 B" },
    ],
  },
];

test("Tree 渲染递归节点和 ARIA 层级", () => {
  const markup = renderToStaticMarkup(
    <Tree treeData={treeData} defaultExpandedKeys={["root"]} aria-label="文件树" />,
  );
  assert.match(markup, /role="tree"/);
  assert.match(markup, /role="treeitem"/);
  assert.match(markup, /根节点/);
  assert.match(markup, /子节点 A/);
});

test("Tree 拒绝重复 key 数据", () => {
  const invalid = [
    { key: "duplicate", label: "A" },
    { key: "duplicate", label: "B" },
  ];
  assert.equal(renderToStaticMarkup(<Tree treeData={invalid} />), "");
});

test("Tree 搜索仅显示匹配路径", () => {
  const markup = renderToStaticMarkup(
    <Tree treeData={treeData} search={{ value: "子节点 B", showMatchedOnly: true }} />,
  );
  assert.match(markup, /根节点/);
  assert.match(markup, /子节点 B/);
  assert.doesNotMatch(markup, /子节点 A/);
});

test("Tree 勾选状态输出 aria-checked", () => {
  const markup = renderToStaticMarkup(
    <Tree
      treeData={treeData}
      checkable
      defaultCheckedKeys={["child-a"]}
      defaultExpandedKeys={["root"]}
    />,
  );
  assert.match(markup, /aria-checked="true"/);
});
