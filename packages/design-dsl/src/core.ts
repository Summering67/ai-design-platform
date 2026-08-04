import type {
  ContractError,
  Document,
  Layout,
  Operation,
  Result,
  RootNode,
  StoredNode,
  TreeDocument,
  TreeNode,
} from "./types.js";

const fail = <T>(...errors: ContractError[]): Result<T> => ({
  ok: false,
  errors,
});
const ok = <T>(value: T): Result<T> => ({ ok: true, value, warnings: [] });
const error = (code: string, path: string, message: string): ContractError => ({
  code,
  path,
  message,
});
const pageFor = (document: Document, pageId: string) =>
  document.pages.find((page) => page.id === pageId);
const clone = <T>(value: T): T => structuredClone(value);
const childrenOf = (node: StoredNode): string[] =>
  "childIds" in node ? node.childIds : [];
const isFrame = (
  node: StoredNode,
): node is Extract<StoredNode, { kind: "frame" }> => node.kind === "frame";

export const validateTree = (tree: TreeDocument): Result<TreeDocument> => {
  if (tree.version !== "1.0.0" || !tree.id || !tree.pages.length)
    return fail(error("invalid_document", "/", "文档版本、ID 或页面无效"));
  const errors: ContractError[] = [];
  for (const [pageIndex, page] of tree.pages.entries()) {
    const ids = new Set<string>([page.rootId]);
    const visit = (
      node: TreeNode,
      path: string,
      parentLayout?: Layout,
    ): void => {
      if (!node.id || ids.has(node.id))
        errors.push(
          error("duplicate_id", `${path}/id`, "节点 ID 必须在页面内唯一"),
        );
      ids.add(node.id);
      if (node.kind === "image" && !tree.assets[node.assetId])
        errors.push(error("unknown_asset", `${path}/assetId`, "资源不存在"));
      if (
        node.kind === "component-instance" &&
        (!tree.componentDefinitions?.[node.componentRef] ||
          !tree.componentBindings?.[node.componentRef])
      )
        errors.push(
          error(
            "unknown_component",
            `${path}/componentRef`,
            "组件定义或绑定不存在",
          ),
        );
      if (
        parentLayout?.mode === "absolute" &&
        (node.layoutItem?.position !== "absolute" ||
          !node.layoutItem.inset ||
          !Object.keys(node.layoutItem.inset).length)
      )
        errors.push(
          error(
            "invalid_absolute_item",
            path,
            "absolute 容器子节点必须具有 absolute 定位和 inset",
          ),
        );
      if (node.kind !== "frame") return;
      node.children.forEach((child, index) =>
        visit(child, `${path}/children/${index}`, node.layout),
      );
    };
    page.children.forEach((node, index) =>
      visit(node, `/pages/${pageIndex}/children/${index}`),
    );
  }
  return errors.length ? fail(...errors) : ok(tree);
};

export const normalize = (tree: TreeDocument): Result<Document> => {
  const checked = validateTree(tree);
  if (!checked.ok) return checked;
  const pages = tree.pages.map((page) => {
    const nodes: Record<string, StoredNode> = {};
    const root: RootNode = {
      id: page.rootId,
      kind: "root",
      parentId: null,
      childIds: page.children.map((node) => node.id),
    };
    nodes[root.id] = root;
    const insert = (node: TreeNode, parentId: string): void => {
      if (node.kind === "frame") {
        const { children, ...frame } = node;
        nodes[node.id] = {
          ...frame,
          parentId,
          childIds: children.map((child) => child.id),
        };
        children.forEach((child) => insert(child, node.id));
        return;
      }
      nodes[node.id] = { ...node, parentId };
    };
    page.children.forEach((node) => insert(node, root.id));
    return { id: page.id, name: page.name, rootId: page.rootId, nodes };
  });
  const document: Document = { ...tree, pages };
  const graph = validateDocument(document);
  return graph.ok ? ok(document) : graph;
};

export const validateDocument = (document: Document): Result<Document> => {
  if (document.version !== "1.0.0" || !document.pages.length)
    return fail(error("invalid_document", "/", "文档版本或页面无效"));
  const errors: ContractError[] = [];
  document.pages.forEach((page, index) => {
    const root = page.nodes[page.rootId];
    if (!root || root.kind !== "root" || root.parentId !== null)
      errors.push(
        error("invalid_root", `/pages/${index}/rootId`, "页面必须有唯一 Root"),
      );
    const visited = new Set<string>();
    const visit = (id: string, parentId: string | null): void => {
      const node = page.nodes[id];
      if (!node) {
        errors.push(
          error("missing_node", `/pages/${index}/nodes/${id}`, "节点不存在"),
        );
        return;
      }
      if (visited.has(id)) {
        errors.push(
          error(
            "cycle",
            `/pages/${index}/nodes/${id}`,
            "节点出现循环或重复引用",
          ),
        );
        return;
      }
      visited.add(id);
      if (node.parentId !== parentId)
        errors.push(
          error(
            "parent_mismatch",
            `/pages/${index}/nodes/${id}/parentId`,
            "父子关系不一致",
          ),
        );
      const ids = childrenOf(node);
      if (new Set(ids).size !== ids.length)
        errors.push(
          error(
            "duplicate_child",
            `/pages/${index}/nodes/${id}/childIds`,
            "子节点不可重复",
          ),
        );
      ids.forEach((child) => visit(child, id));
      if (node.kind === "image" && !document.assets[node.assetId])
        errors.push(
          error(
            "unknown_asset",
            `/pages/${index}/nodes/${id}/assetId`,
            "资源不存在",
          ),
        );
      if (
        node.kind === "component-instance" &&
        (!document.componentDefinitions?.[node.componentRef] ||
          !document.componentBindings?.[node.componentRef])
      )
        errors.push(
          error(
            "unknown_component",
            `/pages/${index}/nodes/${id}/componentRef`,
            "组件定义或绑定不存在",
          ),
        );
    };
    if (root?.kind === "root") visit(root.id, null);
    Object.keys(page.nodes)
      .filter((id) => !visited.has(id))
      .forEach((id) =>
        errors.push(
          error(
            "orphan_node",
            `/pages/${index}/nodes/${id}`,
            "节点不可从 Root 到达",
          ),
        ),
      );
  });
  return errors.length ? fail(...errors) : ok(document);
};

export const denormalize = (document: Document): Result<TreeDocument> => {
  const checked = validateDocument(document);
  if (!checked.ok) return checked;
  const pages = document.pages.map((page) => {
    const convert = (id: string): TreeNode => {
      const node = page.nodes[id];
      if (!node || node.kind === "root") throw new Error("损坏的节点图");
      if (isFrame(node)) {
        const { parentId, childIds, ...frame } = node;
        void parentId;
        return { ...frame, children: childIds.map(convert) };
      }
      const { parentId, ...leaf } = node;
      void parentId;
      return leaf;
    };
    const root = page.nodes[page.rootId] as RootNode;
    return {
      id: page.id,
      name: page.name,
      rootId: page.rootId,
      children: root.childIds.map(convert),
    };
  });
  const meta = {
    version: document.version,
    id: document.id,
    name: document.name,
    assets: document.assets,
    ...(document.tokens ? { tokens: document.tokens } : {}),
    ...(document.componentDefinitions ? { componentDefinitions: document.componentDefinitions } : {}),
    ...(document.componentBindings ? { componentBindings: document.componentBindings } : {}),
  };
  return ok({ ...meta, pages });
};

const subtreeIds = (
  node: StoredNode,
  nodes: Record<string, StoredNode>,
): string[] => [
  node.id,
  ...childrenOf(node).flatMap((id) => subtreeIds(nodes[id]!, nodes)),
];
const detach = (nodes: Record<string, StoredNode>, node: StoredNode): void => {
  const parent = nodes[node.parentId!];
  if (!parent || (!isFrame(parent) && parent.kind !== "root"))
    throw new Error("父节点无效");
  parent.childIds = parent.childIds.filter((id) => id !== node.id);
};
const insertAt = (parent: StoredNode, id: string, index: number): void => {
  if (
    (parent.kind !== "root" && !isFrame(parent)) ||
    index < 0 ||
    index > parent.childIds.length
  )
    throw new Error("父节点或索引无效");
  parent.childIds.splice(index, 0, id);
};

export const applyOperations = (
  document: Document,
  operations: Operation[],
): Result<Document> => {
  const copy = clone(document);
  try {
    for (const operation of operations) {
      const page = pageFor(copy, operation.pageId);
      if (!page) throw error("unknown_page", "/pageId", "页面不存在");
      const node =
        "nodeId" in operation ? page.nodes[operation.nodeId] : undefined;
      if ("nodeId" in operation && (!node || node.kind === "root"))
        throw error("invalid_node", "/nodeId", "节点不存在或不可编辑");
      if (operation.type === "insert-subtree") {
        const parent = page.nodes[operation.parentId];
        if (!parent || (!isFrame(parent) && parent.kind !== "root"))
          throw error("invalid_parent", "/parentId", "父节点无效");
        const tree: TreeDocument = {
          ...copy,
          pages: [
            {
              id: page.id,
              name: page.name,
              rootId: "temp-root",
              children: [operation.subtree],
            },
          ],
        };
        const normalized = normalize(tree);
        if (!normalized.ok) throw normalized.errors[0];
        const added = normalized.value.pages[0]!.nodes;
        if (
          Object.keys(added).some((id) => id !== "temp-root" && page.nodes[id])
        )
          throw error("duplicate_id", "/subtree", "节点 ID 冲突");
        Object.entries(added)
          .filter(([id]) => id !== "temp-root")
          .forEach(([id, value]) => {
            page.nodes[id] = value;
          });
        const rootChild = added[operation.subtree.id]!;
        rootChild.parentId = parent.id;
        insertAt(parent, rootChild.id, operation.index);
        continue;
      }
      if (!node) continue;
      if (operation.type === "move-node") {
        if (
          operation.expectedParentId &&
          node.parentId !== operation.expectedParentId
        )
          throw error(
            "parent_conflict",
            "/expectedParentId",
            "期望父节点不匹配",
          );
        const parent = page.nodes[operation.parentId];
        if (!parent || (!isFrame(parent) && parent.kind !== "root"))
          throw error("invalid_parent", "/parentId", "父节点无效");
        const descendants = new Set(subtreeIds(node, page.nodes));
        if (descendants.has(parent.id))
          throw error("cycle", "/parentId", "不能移动到自身子节点");
        detach(page.nodes, node);
        node.parentId = parent.id;
        insertAt(parent, node.id, operation.index);
        continue;
      }
      if (operation.type === "remove-node") {
        if (
          operation.expectedParentId &&
          node.parentId !== operation.expectedParentId
        )
          throw error(
            "parent_conflict",
            "/expectedParentId",
            "期望父节点不匹配",
          );
        detach(page.nodes, node);
        subtreeIds(node, page.nodes).forEach((id) => delete page.nodes[id]);
        continue;
      }
      if (operation.type === "set-text") {
        if (node.kind !== "text")
          throw error("invalid_node_kind", "/nodeId", "仅文本节点可设置文本");
        node.text = operation.text;
        continue;
      }
      if (node.kind === "root")
        throw error("invalid_node", "/nodeId", "Root 不可编辑");
      if (operation.type === "patch-style") {
        node.style ??= {};
        operation.patches.forEach((patch) => {
          if (patch.action === "unset") delete node.style?.[patch.property];
          else Object.assign(node.style!, { [patch.property]: patch.value });
        });
        continue;
      }
      if (operation.type === "set-layout") {
        if (!isFrame(node))
          throw error("invalid_node_kind", "/nodeId", "仅 Frame 可设置布局");
        if (operation.layout === null) delete node.layout;
        else node.layout = operation.layout;
        continue;
      }
      if (operation.type === "set-layout-item") {
        if (operation.layoutItem === null) delete node.layoutItem;
        else node.layoutItem = operation.layoutItem;
        continue;
      }
      if (operation.type === "replace-component") {
        if (
          node.kind !== "component-instance" ||
          !copy.componentDefinitions?.[operation.componentRef] ||
          !copy.componentBindings?.[operation.componentRef]
        )
          throw error(
            "unknown_component",
            "/componentRef",
            "组件不存在或节点类型无效",
          );
        node.componentRef = operation.componentRef;
      }
    }
  } catch (caught) {
    return fail(
      typeof caught === "object" && caught && "code" in caught
        ? (caught as ContractError)
        : error("invalid_operation", "/", "操作无效"),
    );
  }
  const checked = validateDocument(copy);
  return checked.ok ? ok(copy) : checked;
};
