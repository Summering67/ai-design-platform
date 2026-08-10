export type NodeId = string;
export type ProfileReference = {
  id: string;
  version: string;
  digest: string;
};

export type Asset = {
  id: string;
  hash: string;
  mimeType: string;
  intrinsicSize?: { width: number; height: number };
  source: string;
};

export type ComponentSlotContract = {
  type: "string" | "text" | "node" | "nodes";
  required?: boolean;
};

export type ProfileComponentContract = {
  id: string;
  variants?: Record<string, string[]>;
  allowedVariants?: Record<string, string[]>;
  slots?: Record<string, ComponentSlotContract>;
  overrides?: Record<string, unknown>;
  propsSchema?: Record<string, unknown>;
  semantic?: Record<string, unknown>;
};

export type DesignSystemProfile = {
  id: string;
  version: string;
  digest: string;
  name: string;
  tokens: Record<string, unknown>;
  typography?: Record<string, unknown>;
  components: Record<string, ProfileComponentContract>;
  layout: {
    modes?: Array<"flex" | "absolute">;
    sizing?: Array<"fixed" | "fill" | "hug">;
  };
  icons?: Record<string, unknown>;
  assets?: { mimeTypes?: string[]; sources?: string[] };
};

export type DesignGenerationContract = {
  profile: ProfileReference;
  nodeKinds: Array<"frame" | "text" | "image" | "icon" | "component-instance">;
  tokens: string[];
  components: Record<string, ProfileComponentContract>;
  layout: DesignSystemProfile["layout"];
  icons: string[];
};
export type Sizing =
  | { mode: "fixed"; value: number; min?: number; max?: number }
  | { mode: "fill"; min?: number; max?: number }
  | { mode: "hug"; min?: number; max?: number };
export type LayoutItem = {
  width?: Sizing;
  height?: Sizing;
  grow?: number;
  shrink?: number;
  position?: "auto" | "flow" | "absolute";
  offset?: Partial<Record<"x" | "y", number>>;
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
  slots?: Record<string, string | string[]>;
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
  assets: Record<string, Asset>;
  profile?: ProfileReference;
  /** @deprecated 团队 Token 与组件契约由 Profile 所有，仅用于旧文档兼容。 */
  tokens?: Record<string, unknown>;
  /** @deprecated 目标组件绑定由渲染适配器所有。 */
  componentDefinitions?: Record<string, ComponentDefinition>;
  /** @deprecated 目标组件绑定由渲染适配器所有。 */
  componentBindings?: Record<string, ComponentBinding>;
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

export type DesignRenderNodeBase = {
  id: NodeId;
  name?: string;
  visible: boolean;
  style?: Style;
  layoutItem?: LayoutItem;
  semantic?: Record<string, unknown>;
};

export type DesignRenderFrameNode = DesignRenderNodeBase & {
  kind: "frame";
  layout?: Layout;
  children: DesignRenderNode[];
};

export type DesignRenderTextNode = DesignRenderNodeBase & {
  kind: "text";
  text: string;
  typography: Record<string, unknown>;
  children: [];
};

export type DesignRenderImageNode = DesignRenderNodeBase & {
  kind: "image";
  assetId: string;
  asset: Asset;
  alt?: string;
  children: [];
};

export type DesignRenderIconNode = DesignRenderNodeBase & {
  kind: "icon";
  name: string;
  children: [];
};

export type DesignRenderComponentNode = DesignRenderNodeBase & {
  kind: "component-instance";
  componentRef: string;
  variant?: Record<string, string>;
  slots?: Record<string, string | string[]>;
  overrides?: Record<string, unknown>;
  contract: ProfileComponentContract;
  children: [];
};

export type DesignRenderNode =
  | DesignRenderFrameNode
  | DesignRenderTextNode
  | DesignRenderImageNode
  | DesignRenderIconNode
  | DesignRenderComponentNode;

export type ValidatedDesignRenderModel = {
  profile: ProfileReference;
  tokens: Record<string, unknown>;
  assets: Record<string, Asset>;
  pages: Array<{ id: string; name: string; nodes: DesignRenderNode[] }>;
  credentials: { validated: true; digest: string };
};

export type DesignRenderModel = ValidatedDesignRenderModel;
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
