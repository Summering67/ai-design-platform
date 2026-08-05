import type { ReactNode } from "react";
import { applyV2Operations, type DesignDocument, type DesignNode, type V2Operation } from "@repo/design-dsl";
import { Tree, type TreeDropIntent, type TreeNodeData, type TreeProps } from "../../components/tree";

export type DesignDocumentTreeProps = Omit<TreeProps<DesignNode>, "treeData" | "selectionMode" | "selectedKeys" | "onSelectedChange" | "draggable" | "onDrop"> & {
  document: DesignDocument;
  selectedNodeId?: string;
  onSelectedNodeIdChange?: (nodeId: string | undefined, node: DesignNode | undefined) => void;
  onDocumentChange?: (document: DesignDocument, operation: V2Operation) => void;
  onOperationError?: (message: string) => ReactNode;
};

const toTreeNode = (node: DesignNode): TreeNodeData<DesignNode> => ({
  key: node.id,
  label: `${node.name} (${node.tag})`,
  data: node,
  isLeaf: node.children.length === 0,
  children: node.children.map(toTreeNode),
});

type NodeLocation = { node: DesignNode; parent: DesignNode | null; index: number };

const findNode = (node: DesignNode, nodeId: string, parent: DesignNode | null = null, index = 0): NodeLocation | undefined => {
  if (node.id === nodeId) return { node, parent, index };
  for (const [childIndex, child] of node.children.entries()) {
    const result = findNode(child, nodeId, node, childIndex);
    if (result) return result;
  }
  return undefined;
};

const dropToOperation = (document: DesignDocument, intent: TreeDropIntent<DesignNode>): V2Operation | undefined => {
  const source = findNode(document.root, intent.dragKey);
  const target = findNode(document.root, intent.targetKey);
  if (!source?.parent || !target || source.node.id === document.root.id) return undefined;
  if (intent.position === "inside") return { type: "move-node", nodeId: source.node.id, parentId: target.node.id, index: target.node.children.length, expectedParentId: source.parent.id };
  if (!target.parent) return undefined;
  return {
    type: "move-node",
    nodeId: source.node.id,
    parentId: target.parent.id,
    index: target.index + (intent.position === "after" ? 1 : 0),
    expectedParentId: source.parent.id,
  };
};

export const DesignDocumentTree = ({
  document,
  selectedNodeId,
  onSelectedNodeIdChange,
  onDocumentChange,
  onOperationError,
  ...props
}: DesignDocumentTreeProps) => {
  const treeData = [toTreeNode(document.root)];
  const handleDrop = (intent: TreeDropIntent<DesignNode>) => {
    const operation = dropToOperation(document, intent);
    if (!operation) return;
    const result = applyV2Operations(document, [operation]);
    if (!result.ok) return onOperationError?.(result.errors[0]?.message ?? "无法更新设计节点");
    onDocumentChange?.(result.value, operation);
  };
  const handleSelect = (keys: string[], detail: { selected: boolean; node: TreeNodeData<DesignNode> }) => {
    const nodeId = detail.selected ? keys[0] : undefined;
    onSelectedNodeIdChange?.(nodeId, detail.node.data);
  };
  return (
    <Tree
      {...props}
      treeData={treeData}
      selectionMode="single"
      selectedKeys={selectedNodeId ? [selectedNodeId] : []}
      onSelectedChange={handleSelect}
      draggable={{ onDrop: handleDrop }}
      aria-label={props["aria-label"] ?? "设计节点树"}
    />
  );
};

export default DesignDocumentTree;
