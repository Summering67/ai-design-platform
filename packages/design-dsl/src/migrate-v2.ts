import type {
  ComponentBinding,
  DesignSystemProfile,
  Document,
  Style as LegacyStyle,
  TreeDocument,
  TreeNode,
} from "./types.js";
import type {
  DesignDocument,
  DesignNode,
  DesignSystemSnapshot,
} from "@repo/design-contract";
import { denormalize } from "./core.js";
import {
  type DesignValidationError,
  type V2Result,
  validateDesignDocument,
} from "./v2.js";

export type V2MigrationAudit = {
  sourceFormat: "v1-graph" | "v1-tree";
  sourceVersion: string;
  targetVersion: "2.0.0";
  migratorVersion: string;
  warnings: string[];
};

export type V2MigrationResult = {
  document: DesignDocument;
  audit: V2MigrationAudit;
};

const fail = <T>(...errors: DesignValidationError[]): V2Result<T> => ({
  ok: false,
  errors,
});
const ok = <T>(value: T): V2Result<T> => ({ ok: true, value, errors: [] });
const error = (code: string, path: string, message: string): DesignValidationError => ({ code, path, message });
const primitive = (value: unknown): value is string | number | boolean =>
  ["string", "number", "boolean"].includes(typeof value);
const jsonObject = (value: Record<string, unknown>): DesignDocument["root"]["props"] =>
  structuredClone(value) as DesignDocument["root"]["props"];

const mapStyle = (style: LegacyStyle | undefined, path: string): V2Result<Record<string, string | number | boolean>> => {
  if (!style) return ok({});
  const output: Record<string, string | number | boolean> = {};
  const aliases: Record<string, string> = {
    radius: "borderRadius",
    shadow: "boxShadow",
  };
  for (const [key, value] of Object.entries(style)) {
    const target = aliases[key] ?? key;
    if (!primitive(value))
      return fail(error("unsupported_style", `${path}/${key}`, "v1 样式值无法确定性映射到 v2"));
    output[target] = value;
  }
  return ok(output);
};

const snapshotFor = (
  profile: DesignSystemProfile,
  bindings: Record<string, ComponentBinding> | undefined,
): DesignSystemSnapshot => ({
  id: profile.id,
  version: profile.version,
  digest: profile.digest,
  tokens: jsonObject(profile.tokens),
  components: Object.fromEntries(
    Object.entries(profile.components).map(([id, component]) => {
      const targetName = bindings?.[id]?.codeBinding.exportName ?? id;
      return [targetName, {
        id: component.id,
        ...(bindings?.[id]?.codeBinding.importFrom
          ? { packageName: bindings[id]!.codeBinding.importFrom }
          : {}),
        ...(component.propsSchema ? { propsSchema: jsonObject(component.propsSchema) } : {}),
        ...(component.allowedVariants ?? component.variants
          ? { variants: structuredClone(component.allowedVariants ?? component.variants) }
          : {}),
        ...(component.slots ? { slots: structuredClone(component.slots) } : {}),
      }];
    }),
  ),
});

const assetsFor = (assets: Document["assets"]): DesignDocument["assets"] =>
  Object.fromEntries(
    Object.entries(assets).map(([id, asset]) => [
      id,
      {
        id: asset.id,
        type: "image",
        src: asset.source,
        mimeType: asset.mimeType,
        ...(asset.hash ? { hash: asset.hash } : {}),
        ...(asset.intrinsicSize?.width ? { width: asset.intrinsicSize.width } : {}),
        ...(asset.intrinsicSize?.height ? { height: asset.intrinsicSize.height } : {}),
      },
    ]),
  );

const mapNode = (
  node: TreeNode,
  document: TreeDocument,
  profile: DesignSystemProfile,
  path: string,
): V2Result<DesignNode> => {
  const style = mapStyle(node.style, `${path}/style`);
  if (!style.ok) return style;
  if (node.kind === "icon")
    return fail(error("unsupported_node", path, "v1 icon 节点没有 v2 的确定性组件契约"));
  if (node.kind === "frame") {
    const children: DesignNode[] = [];
    for (const [index, child] of node.children.entries()) {
      const mapped = mapNode(child, document, profile, `${path}/children/${index}`);
      if (!mapped.ok) return mapped;
      children.push(mapped.value);
    }
    return ok({
      id: node.id,
      kind: "element",
      name: node.name ?? node.id,
      tag: "div",
      style: style.value,
      props: {},
      children,
      source: { tool: "v1", type: node.kind, ...(node.id ? { id: node.id } : {}) },
    });
  }
  if (node.kind === "text")
    return ok({
      id: node.id,
      kind: "text",
      name: node.name ?? node.id,
      tag: "span",
      style: style.value,
      props: {},
      children: [],
      text: node.text,
      source: { tool: "v1", type: node.kind, ...(node.id ? { id: node.id } : {}) },
    });
  if (node.kind === "image")
    return ok({
      id: node.id,
      kind: "image",
      name: node.name ?? node.id,
      tag: "img",
      style: style.value,
      props: {},
      children: [],
      assetId: node.assetId,
      ...(node.alt ? { alt: node.alt } : {}),
      source: { tool: "v1", type: node.kind, ...(node.id ? { id: node.id } : {}) },
    });
  const binding = document.componentBindings?.[node.componentRef];
  const component = profile.components[node.componentRef];
  if (!binding || !component)
    return fail(error("unknown_component", `${path}/componentRef`, "v1 组件缺少固定定义或 binding"));
  return ok({
    id: node.id,
    kind: "component",
    name: node.name ?? node.id,
    tag: binding.codeBinding.exportName,
    packageName: binding.codeBinding.importFrom,
    style: style.value,
    props: {
      ...(node.variant ? { variant: structuredClone(node.variant) } : {}),
      ...(node.slots ? { slots: structuredClone(node.slots) } : {}),
      ...(node.overrides ? structuredClone(node.overrides) : {}),
    },
    children: [],
    source: { tool: "v1", type: node.kind, ...(node.id ? { id: node.id } : {}) },
  });
};

const asTree = (input: unknown): V2Result<{ tree: TreeDocument; sourceFormat: V2MigrationAudit["sourceFormat"] }> => {
  if (!input || typeof input !== "object") return fail(error("invalid_format", "/", "旧文档必须是对象"));
  const record = input as { version?: unknown; pages?: unknown };
  if (typeof record.version !== "string" || !Array.isArray(record.pages)) return fail(error("invalid_format", "/", "无法判别 v1 文档格式"));
  const pages = record.pages as Array<Record<string, unknown>>;
  if (pages.length !== 1) return fail(error("unsupported_pages", "/pages", "v2 只支持单根文档，不能迁移多页 v1 文档"));
  const page = pages[0];
  const hasGraph = Boolean(page && page.nodes && typeof page.nodes === "object");
  const hasTree = Boolean(page && Array.isArray(page.children));
  if (hasGraph === hasTree) return fail(error("ambiguous_format", "/pages/0", "v1 Graph 与 Tree 结构缺失或混用"));
  if (hasGraph) {
    const converted = denormalize(input as Document);
    if (!converted.ok) return fail(...converted.errors);
    return ok({ tree: converted.value, sourceFormat: "v1-graph" });
  }
  return ok({ tree: input as TreeDocument, sourceFormat: "v1-tree" });
};

export const migrateV1ToV2 = (
  input: unknown,
  profile: DesignSystemProfile,
): V2Result<V2MigrationResult> => {
  const source = asTree(input);
  if (!source.ok) return source;
  const { tree, sourceFormat } = source.value;
  if (
    tree.profile &&
    (tree.profile.id !== profile.id ||
      tree.profile.version !== profile.version ||
      tree.profile.digest !== profile.digest)
  )
    return fail(error("profile_mismatch", "/profile", "v1 Profile 引用与迁移快照不匹配"));
  const root = mapNode(
    {
      id: tree.pages[0]!.rootId,
      kind: "frame",
      name: tree.name,
      style: {},
      children: tree.pages[0]!.children,
    },
    tree,
    profile,
    "/root",
  );
  if (!root.ok) return root;
  const document: DesignDocument = {
    version: "2.0.0",
    id: tree.id,
    name: tree.name,
    designSystem: snapshotFor(profile, tree.componentBindings),
    assets: assetsFor(tree.assets),
    root: root.value,
  };
  const checked = validateDesignDocument(document);
  if (!checked.ok) return checked;
  return ok({
    document: checked.value,
    audit: {
      sourceFormat,
      sourceVersion: tree.version,
      targetVersion: "2.0.0",
      migratorVersion: "2.0.0",
      warnings: [],
    },
  });
};
