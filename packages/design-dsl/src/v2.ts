import { Ajv2020 } from "ajv/dist/2020.js";
import * as addFormatsModule from "ajv-formats";
import schema from "@repo/design-contract/schema/v2/design-document.schema.json" with {
  type: "json",
};
import {
  type DesignDocument,
  type DesignNode,
} from "@repo/design-contract";
export type { DesignDocument, DesignNode } from "@repo/design-contract";

export type DesignValidationError = {
  code: string;
  path: string;
  message: string;
};

const ajv = new Ajv2020({
  allErrors: true,
  strict: true,
  strictSchema: false,
  strictRequired: false,
});
const addFormats = addFormatsModule.default as unknown as (
  instance: Ajv2020,
) => void;
addFormats(ajv);
const validateSchema = ajv.compile<DesignDocument>(schema);
const pathFor = (path: string | undefined): string =>
  path?.replaceAll("~1", "/").replaceAll("~0", "~") || "/";
const containsDesignNode = (value: unknown): boolean => {
  if (!value || typeof value !== "object") return false;
  if (Array.isArray(value)) return value.some(containsDesignNode);
  const record = value as Record<string, unknown>;
  return (
    (typeof record.id === "string" &&
      typeof record.kind === "string" &&
      Array.isArray(record.children)) ||
    Object.values(record).some(containsDesignNode)
  );
};
const componentFor = (document: DesignDocument, node: DesignNode) =>
  Object.values(document.designSystem.components).find(
    (component) => component.id === node.tag,
  ) ?? document.designSystem.components[node.tag];
export const validateDesignDocument = (
  input: unknown,
): V2Result<DesignDocument> => {
  if (!validateSchema(input))
    return fail(
      ...(validateSchema.errors ?? []).map((item) => ({
        code: "schema_validation",
        path: pathFor(item.instancePath),
        message: item.message ?? "设计文档不符合 Schema",
      })),
    );
  const document = input as DesignDocument;
  const errors: DesignValidationError[] = [];
  const ids = new Set<string>();
  const visit = (node: DesignNode, path: string): void => {
    if (ids.has(node.id))
      errors.push({
        code: "duplicate_id",
        path: `${path}/id`,
        message: "节点 ID 必须在文档内唯一",
      });
    ids.add(node.id);
    if (node.kind === "image" && !document.assets[node.assetId!])
      errors.push({
        code: "unknown_asset",
        path: `${path}/assetId`,
        message: "资源不存在",
      });
    if (node.kind === "component" && !componentFor(document, node))
      errors.push({
        code: "unknown_component",
        path: `${path}/tag`,
        message: "组件未在 designSystem 快照中注册",
      });
    if (
      node.kind === "component" &&
      document.designSystem.allowedTags &&
      !document.designSystem.allowedTags.includes(node.tag)
    )
      errors.push({
        code: "tag_not_allowed",
        path: `${path}/tag`,
        message: "节点 tag 未被 designSystem 允许",
      });
    if (containsDesignNode(node.props))
      errors.push({
        code: "nested_design_node",
        path: `${path}/props`,
        message: "props 不得隐藏 DesignNode",
      });
    node.children.forEach((child, index) =>
      visit(child, `${path}/children/${index}`),
    );
  };
  visit(document.root, "/root");
  return errors.length ? fail(...errors) : ok(document);
};

export type DesignGraphEntry = {
  node: DesignNode;
  parentId: string | null;
  childIds: string[];
};

export type DesignGraph = {
  rootId: string;
  nodes: Record<string, DesignGraphEntry>;
};

export type V2Result<T> =
  | { ok: true; value: T; errors: [] }
  | { ok: false; errors: DesignValidationError[] };

const fail = <T>(...errors: DesignValidationError[]): V2Result<T> => ({
  ok: false,
  errors,
});

const ok = <T>(value: T): V2Result<T> => ({ ok: true, value, errors: [] });
const clone = <T>(value: T): T => structuredClone(value);

const graphEntry = (
  node: DesignNode,
  parentId: string | null,
): DesignGraphEntry => ({
  node: clone(node),
  parentId,
  childIds: node.children.map((child) => child.id),
});

export const toDesignGraph = (input: unknown): V2Result<DesignGraph> => {
  const checked = validateDesignDocument(input);
  if (!checked.ok) return checked;
  const graph: DesignGraph = { rootId: checked.value.root.id, nodes: {} };
  const visit = (node: DesignNode, parentId: string | null): void => {
    graph.nodes[node.id] = graphEntry(node, parentId);
    node.children.forEach((child) => visit(child, node.id));
  };
  visit(checked.value.root, null);
  return ok(graph);
};

export const fromDesignGraph = (
  document: DesignDocument,
  graph: DesignGraph,
): V2Result<DesignDocument> => {
  const root = graph.nodes[graph.rootId];
  if (!root || root.parentId !== null)
    return fail({
      code: "invalid_root",
      path: "/root",
      message: "Graph 必须包含 parentId 为 null 的 Root",
    });

  const visiting = new Set<string>();
  const visited = new Set<string>();
  const errors: DesignValidationError[] = [];
  const build = (
    id: string,
    parentId: string | null,
    path: string,
  ): DesignNode | null => {
    const entry = graph.nodes[id];
    if (!entry) {
      errors.push({
        code: "missing_node",
        path,
        message: "Graph 节点不存在",
      });
      return null;
    }
    if (entry.parentId !== parentId || visiting.has(id)) return null;
    visiting.add(id);
    visited.add(id);
    const node = clone(entry.node);
    node.children = entry.childIds
      .map((childId) => build(childId, id, `${path}/children/${childId}`))
      .filter((child): child is DesignNode => Boolean(child));
    visiting.delete(id);
    return node;
  };

  const rebuilt = build(graph.rootId, null, "/root");
  if (errors.length) return fail(...errors);
  if (!rebuilt || visited.size !== Object.keys(graph.nodes).length)
    return fail({
      code: "invalid_graph",
      path: "/",
      message: "Graph 存在断链、循环或不可达节点",
    });
  const result = validateDesignDocument({ ...clone(document), root: rebuilt });
  return result.ok ? result : result;
};

export type V2Operation =
  | {
      type: "insert-subtree";
      parentId: string;
      index: number;
      subtree: DesignNode;
    }
  | {
      type: "move-node";
      nodeId: string;
      parentId: string;
      index: number;
      expectedParentId?: string;
    }
  | { type: "remove-node"; nodeId: string; expectedParentId?: string }
  | { type: "set-text"; nodeId: string; text: string }
  | {
      type: "patch-style";
      nodeId: string;
      patches: Record<string, unknown | null>;
    }
  | {
      type: "patch-layout";
      nodeId: string;
      patches: Record<string, unknown | null>;
    }
  | {
      type: "patch-layout-item";
      nodeId: string;
      patches: Record<string, unknown | null>;
    };

const subtreeIds = (graph: DesignGraph, id: string): string[] => {
  const entry = graph.nodes[id];
  return entry
    ? [id, ...entry.childIds.flatMap((childId) => subtreeIds(graph, childId))]
    : [];
};

const treeIds = (node: DesignNode): string[] => [
  node.id,
  ...node.children.flatMap(treeIds),
];

const addSubtree = (
  graph: DesignGraph,
  node: DesignNode,
  parentId: string,
): void => {
  graph.nodes[node.id] = graphEntry(node, parentId);
  node.children.forEach((child) => addSubtree(graph, child, node.id));
};

const removeSubtree = (graph: DesignGraph, id: string): void => {
  subtreeIds(graph, id).forEach((nodeId) => delete graph.nodes[nodeId]);
};

export const applyV2Operations = (
  document: DesignDocument,
  operations: V2Operation[],
): V2Result<DesignDocument> => {
  const initial = toDesignGraph(document);
  if (!initial.ok) return initial;
  const graph = clone(initial.value);
  try {
    for (const [index, operation] of operations.entries()) {
      const target = graph.nodes["nodeId" in operation ? operation.nodeId : ""];
      if ("nodeId" in operation && !target)
        throw {
          code: "invalid_node",
          path: `/operations/${index}/nodeId`,
          message: "节点不存在",
        };
      if (operation.type === "insert-subtree") {
        const parent = graph.nodes[operation.parentId];
        if (
          !parent ||
          operation.index < 0 ||
          operation.index > parent.childIds.length
        )
          throw {
            code: "invalid_parent",
            path: `/operations/${index}/parentId`,
            message: "父节点或插入位置无效",
          };
        const ids = treeIds(operation.subtree);
        const addedIds = new Set(ids);
        if (
          addedIds.size !== ids.length ||
          Object.keys(graph.nodes).some((id) => addedIds.has(id))
        )
          throw {
            code: "duplicate_id",
            path: `/operations/${index}/subtree`,
            message: "子树包含重复或冲突 ID",
          };
        addSubtree(graph, operation.subtree, operation.parentId);
        parent.childIds.splice(operation.index, 0, operation.subtree.id);
        continue;
      }
      if (!target) continue;
      if (operation.type === "move-node") {
        if (operation.nodeId === graph.rootId)
          throw {
            code: "invalid_node",
            path: `/operations/${index}/nodeId`,
            message: "Root 不可移动",
          };
        const parent = graph.nodes[operation.parentId];
        if (
          !parent ||
          subtreeIds(graph, operation.nodeId).includes(operation.parentId)
        )
          throw {
            code: "invalid_parent",
            path: `/operations/${index}/parentId`,
            message: "父节点无效或会形成循环",
          };
        if (
          operation.expectedParentId &&
          target.parentId !== operation.expectedParentId
        )
          throw {
            code: "parent_conflict",
            path: `/operations/${index}/expectedParentId`,
            message: "期望父节点不匹配",
          };
        const oldParent = target.parentId
          ? graph.nodes[target.parentId]
          : undefined;
        oldParent?.childIds.splice(
          oldParent.childIds.indexOf(operation.nodeId),
          1,
        );
        target.parentId = operation.parentId;
        parent.childIds.splice(operation.index, 0, operation.nodeId);
        continue;
      }
      if (operation.type === "remove-node") {
        if (operation.nodeId === graph.rootId)
          throw {
            code: "invalid_node",
            path: `/operations/${index}/nodeId`,
            message: "Root 不可删除",
          };
        if (
          operation.expectedParentId &&
          target.parentId !== operation.expectedParentId
        )
          throw {
            code: "parent_conflict",
            path: `/operations/${index}/expectedParentId`,
            message: "期望父节点不匹配",
          };
        const parent = target.parentId
          ? graph.nodes[target.parentId]
          : undefined;
        parent?.childIds.splice(parent.childIds.indexOf(operation.nodeId), 1);
        removeSubtree(graph, operation.nodeId);
        continue;
      }
      if (operation.type === "set-text") {
        if (target.node.kind !== "text")
          throw {
            code: "invalid_node_kind",
            path: `/operations/${index}/nodeId`,
            message: "仅 text 节点可设置文本",
          };
        target.node.text = operation.text;
        continue;
      }
      if (operation.type === "patch-style") {
        Object.entries(operation.patches).forEach(([property, value]) => {
          if (value === null)
            delete target.node.style[
              property as keyof typeof target.node.style
            ];
          else Object.assign(target.node.style, { [property]: value });
        });
        continue;
      }
      if (operation.type === "patch-layout") {
        const layout = {
          ...(target.node.layout ?? { mode: "flex" }),
          ...target.node.layout,
        } as Record<string, unknown>;
        Object.entries(operation.patches).forEach(([property, value]) => {
          if (value === null) delete layout[property];
          else layout[property] = value;
        });
        target.node.layout = layout as unknown as DesignNode["layout"];
        continue;
      }
      if (operation.type === "patch-layout-item") {
        const layoutItem = { ...(target.node.layoutItem ?? {}) } as Record<
          string,
          unknown
        >;
        Object.entries(operation.patches).forEach(([property, value]) => {
          if (value === null) delete layoutItem[property];
          else layoutItem[property] = value;
        });
        if (Object.keys(layoutItem).length)
          target.node.layoutItem = layoutItem as DesignNode["layoutItem"];
        else delete target.node.layoutItem;
      }
    }
  } catch (error) {
    return fail(error as DesignValidationError);
  }
  const result = fromDesignGraph(document, graph);
  if (!result.ok) return result;
  delete result.value.resolvedLayouts;
  return result;
};

export type DesignDependency = {
  packageName: string;
  componentName: string;
  defaultModule: boolean;
};

export const collectDesignDependencies = (
  document: DesignDocument,
): V2Result<DesignDependency[]> => {
  const checked = validateDesignDocument(document);
  if (!checked.ok) return checked;
  const dependencies = new Map<string, DesignDependency>();
  const visit = (node: DesignNode): void => {
    if (node.kind === "component" && node.packageName) {
      const dependency = {
        packageName: node.packageName,
        componentName: node.tag,
        defaultModule: node.defaultModule === true,
      };
      dependencies.set(
        `${dependency.packageName}:${dependency.componentName}:${dependency.defaultModule}`,
        dependency,
      );
    }
    node.children.forEach(visit);
  };
  visit(checked.value.root);
  return ok(
    [...dependencies.values()].sort((left, right) =>
      `${left.packageName}:${left.componentName}`.localeCompare(
        `${right.packageName}:${right.componentName}`,
      ),
    ),
  );
};

export type V2RenderModel = {
  designSystem: DesignDocument["designSystem"];
  assets: DesignDocument["assets"];
  root: DesignNode;
};

export const deriveV2RenderModel = (
  document: DesignDocument,
): V2Result<V2RenderModel> => {
  const checked = validateDesignDocument(document);
  if (!checked.ok) return checked;
  return ok({
    designSystem: clone(checked.value.designSystem),
    assets: clone(checked.value.assets),
    root: clone(checked.value.root),
  });
};
