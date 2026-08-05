import treeFixture from "@repo/design-contract/legacy/fixtures/v1/login-page.tree.json" with { type: "json" };
import profileFixture from "@repo/design-contract/legacy/fixtures/v1/team-default.profile.json" with { type: "json" };
import { migrateV1ToV2 } from "./migrate-v2.js";
import { normalize } from "./core.js";
import type { DesignSystemProfile, TreeDocument } from "./types.js";

const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message);
};

const migrated = migrateV1ToV2(
  treeFixture as TreeDocument,
  profileFixture as DesignSystemProfile,
);
assert(migrated.ok, "合法 v1 Tree 必须迁移");
if (migrated.ok) {
  assert(migrated.value.document.version === "2.0.0", "迁移目标版本必须是 2.0.0");
  assert(migrated.value.audit.sourceFormat === "v1-tree", "迁移审计必须记录源格式");
  assert(migrated.value.document.root.children[0]?.children[1]?.kind === "component", "组件节点必须映射为 v2 component");
}

const ambiguous = migrateV1ToV2(
  {
    ...(treeFixture as TreeDocument),
    pages: [{ ...(treeFixture as TreeDocument).pages[0]!, nodes: {} }],
  },
  profileFixture as DesignSystemProfile,
);
assert(!ambiguous.ok, "混合或缺失结构必须失败关闭");

const graph = normalize(treeFixture as TreeDocument);
assert(graph.ok, "v1 Tree fixture 必须先能规范化为 Graph");
if (graph.ok) {
  const migratedGraph = migrateV1ToV2(graph.value, profileFixture as DesignSystemProfile);
  assert(migratedGraph.ok && migratedGraph.value.audit.sourceFormat === "v1-graph", "v1 Graph 必须迁移并记录源格式");
}

const mismatch = migrateV1ToV2(treeFixture as TreeDocument, {
  ...(profileFixture as DesignSystemProfile),
  digest: "sha256:other",
});
assert(!mismatch.ok && mismatch.errors[0]?.code === "profile_mismatch", "Profile 摘要不匹配必须失败关闭");
