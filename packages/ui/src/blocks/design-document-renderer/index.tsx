import {
  createElement,
  type CSSProperties,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  deriveV2RenderModel,
  type DesignDocument,
  type DesignNode,
} from "@repo/design-dsl";
import { renderAntDesignComponent } from "./ant-design-components";

export const DEFAULT_VIEWPORT = {
  id: "desktop",
  width: 1440,
  height: 900,
} as const;

export type DesignDocumentRendererProps = {
  document: DesignDocument;
  selectedNodeId?: string;
  onSelectedNodeIdChange?: (
    nodeId: string | undefined,
    node: DesignNode | undefined,
  ) => void;
  onError?: (message: string) => ReactNode;
};

type Direction = "row" | "row-reverse" | "column" | "column-reverse";
type Sizing = NonNullable<NonNullable<DesignNode["layoutItem"]>["width"]>;

const safeElementTags = new Set([
  "div",
  "main",
  "section",
  "header",
  "footer",
  "nav",
  "article",
  "aside",
  "form",
  "ul",
  "li",
]);
const safeTextTags = new Set(["span", "p", "h1", "h2", "h3", "h4", "label"]);

const elementTagFor = (node: DesignNode) => {
  if (node.kind === "text")
    return safeTextTags.has(node.tag) ? node.tag : "span";
  if (node.kind === "element")
    return safeElementTags.has(node.tag) ? node.tag : "div";
  return node.tag;
};

const primitivePropsFor = (props: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(props).filter(
      ([key]) =>
        key === "id" ||
        key === "role" ||
        key === "title" ||
        key === "tabIndex" ||
        key.startsWith("aria-") ||
        key.startsWith("data-"),
    ),
  );

type Insets = Partial<Record<"top" | "right" | "bottom" | "left", number>>;

const edgeInsets = (value?: Insets): CSSProperties =>
  value
    ? {
        paddingTop: value.top,
        paddingRight: value.right,
        paddingBottom: value.bottom,
        paddingLeft: value.left,
      }
    : {};

const marginInsets = (value?: Insets): CSSProperties =>
  value
    ? {
        marginTop: value.top,
        marginRight: value.right,
        marginBottom: value.bottom,
        marginLeft: value.left,
      }
    : {};

const sizeValue = (sizing: Sizing | undefined) =>
  sizing?.mode === "fixed"
    ? sizing.value
    : sizing?.mode === "hug"
      ? "fit-content"
      : undefined;

const mainAxis = (direction: Direction | undefined) =>
  direction?.startsWith("row") ? "width" : "height";

const layoutStyleFor = (
  node: DesignNode,
  parentDirection?: Direction,
  isRoot = false,
): CSSProperties => {
  const layout = node.layout;
  const item = node.layoutItem;
  const style: CSSProperties = {
    ...(node.style as CSSProperties),
    boxSizing: "border-box",
    ...(isRoot ? { width: "100%", minHeight: "100%" } : {}),
  };
  if (layout?.mode === "flex") {
    Object.assign(style, {
      display: "flex",
      flexDirection: layout.direction,
      flexWrap: layout.wrap,
      justifyContent: layout.justifyContent,
      alignItems: layout.alignItems,
      gap: layout.gap,
      rowGap: layout.rowGap,
      columnGap: layout.columnGap,
      ...edgeInsets(layout.padding),
    });
  } else if (layout?.mode === "absolute") {
    style.position = "relative";
  }
  if (item) {
    const axis = mainAxis(parentDirection);
    if (item.width) {
      if (item.width.mode === "fill" && axis === "width")
        Object.assign(style, { flexGrow: 1, flexBasis: 0 });
      else style.width = sizeValue(item.width) ?? "100%";
    }
    if (item.height) {
      if (item.height.mode === "fill" && axis === "height")
        Object.assign(style, { flexGrow: 1, flexBasis: 0 });
      else style.height = sizeValue(item.height) ?? "100%";
    }
    if (item.flexGrow !== undefined) style.flexGrow = item.flexGrow;
    if (item.flexShrink !== undefined) style.flexShrink = item.flexShrink;
    if (item.flexBasis !== undefined)
      style.flexBasis = item.flexBasis as CSSProperties["flexBasis"];
    if (item.alignSelf) style.alignSelf = item.alignSelf;
    Object.assign(style, marginInsets(item.margin));
    if (item.position === "absolute") {
      style.position = "absolute";
      style.top = item.inset?.top;
      style.right = item.inset?.right;
      style.bottom = item.inset?.bottom;
      style.left = item.inset?.left;
    } else if (item.offset) {
      style.position = "relative";
      style.left = item.offset.x;
      style.top = item.offset.y;
    }
  }
  return style;
};

const renderNode = (
  node: DesignNode,
  document: DesignDocument,
  selectedNodeId: string | undefined,
  parentDirection: Direction | undefined,
  onSelectedNodeIdChange: DesignDocumentRendererProps["onSelectedNodeIdChange"],
  isRoot = false,
): ReactNode => {
  const layout = node.layout?.mode === "flex" ? node.layout : undefined;
  const style = layoutStyleFor(node, parentDirection, isRoot);
  const selectionProps = {
    key: node.id,
    "data-design-node-id": node.id,
    "data-design-selected": selectedNodeId === node.id ? "true" : undefined,
    onPointerDown: (event: React.PointerEvent) => {
      event.stopPropagation();
      onSelectedNodeIdChange?.(node.id, node);
    },
    style: {
      ...style,
      ...(selectedNodeId === node.id
        ? { outline: "2px solid #1677ff", outlineOffset: 2 }
        : {}),
    },
  };
  const children = node.children.map((child) =>
    renderNode(
      child,
      document,
      selectedNodeId,
      layout?.direction,
      onSelectedNodeIdChange,
    ),
  );
  if (node.kind === "text")
    return createElement(
      elementTagFor(node),
      { ...selectionProps, ...primitivePropsFor(node.props) },
      node.text,
    );
  if (node.kind === "image") {
    const asset = document.assets[node.assetId ?? ""];
    return asset
      ? createElement("img", {
          ...selectionProps,
          ...primitivePropsFor(node.props),
          src: asset.src,
          alt: node.alt ?? asset.alt ?? node.name,
        })
      : createElement(
          "div",
          { ...selectionProps, ...primitivePropsFor(node.props) },
          node.name,
        );
  }
  if (node.kind === "component") {
    return (
      renderAntDesignComponent(
        node.tag,
        { ...node.props, ...selectionProps, "data-design-component": node.tag },
        children,
      ) ??
      createElement(
        "div",
        { ...selectionProps, "data-design-component": node.tag, role: "group" },
        [
          createElement("span", { key: `${node.id}:label` }, node.name),
          ...children,
        ],
      )
    );
  }
  return createElement(elementTagFor(node), selectionProps, children);
};

const Viewport = ({ children }: { children: ReactNode }) => {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface) return;
    const update = () => {
      const width = surface.clientWidth;
      const height = surface.clientHeight;
      if (!width || !height) return;
      setScale(
        Math.min(
          1,
          width / DEFAULT_VIEWPORT.width,
          height / DEFAULT_VIEWPORT.height,
        ),
      );
    };
    update();
    const observer =
      typeof ResizeObserver === "undefined"
        ? undefined
        : new ResizeObserver(update);
    observer?.observe(surface);
    return () => observer?.disconnect();
  }, []);
  return (
    <div
      ref={surfaceRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: 0,
        overflow: "auto",
        display: "grid",
        placeItems: "center",
      }}
    >
      <div
        style={{
          width: DEFAULT_VIEWPORT.width * scale,
          height: DEFAULT_VIEWPORT.height * scale,
          flex: "none",
        }}
      >
        <div
          style={{
            width: DEFAULT_VIEWPORT.width,
            height: DEFAULT_VIEWPORT.height,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
            overflow: "auto",
            background: "#fff",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

export const DesignDocumentRenderer = ({
  document,
  selectedNodeId,
  onSelectedNodeIdChange,
  onError,
}: DesignDocumentRendererProps) => {
  const result = deriveV2RenderModel(document);
  if (!result.ok)
    return onError?.(result.errors[0]?.message ?? "设计文档无效") ?? null;
  return (
    <Viewport>
      {renderNode(
        result.value.root,
        document,
        selectedNodeId,
        undefined,
        onSelectedNodeIdChange,
        true,
      )}
    </Viewport>
  );
};

export default DesignDocumentRenderer;
