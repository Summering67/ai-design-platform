export type NodeId = string;
export type Sizing =
  | { mode: "fixed"; value: number }
  | { mode: "fill" }
  | { mode: "hug" }
  | { mode: "minmax"; min: number; max?: number };
export type LayoutItem = {
  width?: Sizing;
  height?: Sizing;
  grow?: number;
  shrink?: number;
  position?: "flow" | "absolute";
  inset?: Partial<Record<"top" | "right" | "bottom" | "left", number>>;
};
export type FlexLayout = {
  mode: "flex";
  direction: "row" | "column";
  justify?: "start" | "center" | "end" | "between";
  align?: "start" | "center" | "end" | "stretch";
  gap?: number;
  padding?: Partial<Record<"top" | "right" | "bottom" | "left", number>>;
  wrap?: boolean;
};
export type AbsoluteLayout = { mode: "absolute" };
export type Layout = FlexLayout | AbsoluteLayout;
export type Style = {
  background?: string | { token: string };
  border?: Record<string, unknown>;
  radius?: number | { token: string };
  shadow?: Record<string, unknown> | { token: string };
  opacity?: number;
};
export type Base = {
  id: NodeId;
  name?: string;
  visible?: boolean;
  style?: Style;
  layoutItem?: LayoutItem;
  semantic?: Record<string, unknown>;
};
export type FrameNode = Base & {
  kind: "frame";
  layout?: Layout;
  children: TreeNode[];
};
export type TextNode = Base & {
  kind: "text";
  text: string;
  typography: Record<string, unknown>;
};
export type ImageNode = Base & { kind: "image"; assetId: string; alt?: string };
export type IconNode = Base & { kind: "icon"; name: string };
export type ComponentInstanceNode = Base & {
  kind: "component-instance";
  componentRef: string;
  variant?: Record<string, string>;
  overrides?: Record<string, unknown>;
};
export type TreeNode =
  | FrameNode
  | TextNode
  | ImageNode
  | IconNode
  | ComponentInstanceNode;
export type RootNode = {
  id: NodeId;
  kind: "root";
  parentId: null;
  childIds: NodeId[];
};
export type StoredFrameNode = Omit<FrameNode, "children"> & {
  parentId: NodeId;
  childIds: NodeId[];
};
export type StoredLeafNode = (
  | TextNode
  | ImageNode
  | IconNode
  | ComponentInstanceNode
) & { parentId: NodeId };
export type StoredNode = RootNode | StoredFrameNode | StoredLeafNode;
export type ComponentDefinition = {
  id: string;
  propsSchema: Record<string, unknown>;
  appearance: TreeNode;
};
export type ComponentBinding = {
  componentRef: string;
  target: "react-tailwind-antd";
  codeBinding: { importFrom: "antd"; exportName: string };
};
export type Meta = {
  version: "1.0.0";
  id: string;
  name: string;
  assets: Record<
    string,
    { id: string; hash: string; mimeType: string; source: string }
  >;
  tokens: Record<string, unknown>;
  componentDefinitions: Record<string, ComponentDefinition>;
  componentBindings: Record<string, ComponentBinding>;
};
export type TreeDocument = Meta & {
  pages: { id: string; name: string; rootId: NodeId; children: TreeNode[] }[];
};
export type Document = Meta & {
  pages: {
    id: string;
    name: string;
    rootId: NodeId;
    nodes: Record<NodeId, StoredNode>;
  }[];
};
export type Operation =
  | {
      type: "insert-subtree";
      pageId: string;
      parentId: NodeId;
      index: number;
      subtree: TreeNode;
    }
  | {
      type: "move-node";
      pageId: string;
      nodeId: NodeId;
      parentId: NodeId;
      index: number;
      expectedParentId?: NodeId;
    }
  | {
      type: "remove-node";
      pageId: string;
      nodeId: NodeId;
      expectedParentId?: NodeId;
    }
  | { type: "set-text"; pageId: string; nodeId: NodeId; text: string }
  | {
      type: "patch-style";
      pageId: string;
      nodeId: NodeId;
      patches:
        | {
            property: keyof Style;
            action: "set";
            value: NonNullable<Style[keyof Style]>;
          }[]
        | { property: keyof Style; action: "unset" }[];
    }
  | {
      type: "set-layout";
      pageId: string;
      nodeId: NodeId;
      layout: Layout | null;
    }
  | {
      type: "set-layout-item";
      pageId: string;
      nodeId: NodeId;
      layoutItem: LayoutItem | null;
    }
  | {
      type: "replace-component";
      pageId: string;
      nodeId: NodeId;
      componentRef: string;
    };
export type ContractError = { code: string; path: string; message: string };
export type Result<T> =
  | { ok: true; value: T; warnings: ContractError[] }
  | { ok: false; errors: ContractError[] };
