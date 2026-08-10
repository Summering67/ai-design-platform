import { createElement, type CSSProperties, type ReactNode } from "react";
import { deriveV2RenderModel, type DesignDocument, type DesignNode } from "@repo/design-dsl";
import { renderAntDesignComponent } from "./ant-design-components";

export type DesignDocumentRendererProps = {
  document: DesignDocument;
  viewportId: string;
  onError?: (message: string) => ReactNode;
};

const renderNode = (node: DesignNode, document: DesignDocument, viewportId: string): ReactNode => {
  const geometry = document.resolvedLayouts?.[viewportId]?.nodes[node.id];
  if (!geometry) return null;
  const props = {
    ...node.props,
    style: {
      ...(node.style as CSSProperties),
      position: "absolute",
      left: geometry.x,
      top: geometry.y,
      width: geometry.width,
      height: geometry.height,
      boxSizing: "border-box",
    } as CSSProperties,
    "data-design-node-id": node.id,
  };
  if (node.kind === "text") return createElement(node.tag, props, node.text);
  if (node.kind === "image") {
    const asset = document.assets[node.assetId!];
    return asset
      ? createElement("img", { ...props, src: asset.src, alt: node.alt ?? asset.alt ?? node.name })
      : null;
  }
  if (node.kind === "component") {
    const component = renderAntDesignComponent(
      node.tag,
      { ...props, "data-design-component": node.tag },
      node.children.map((child) => renderNode(child, document, viewportId)),
    );
    return (
      component ??
      createElement(
        "span",
        { ...props, "data-design-component": node.tag },
        node.children.map((child) => renderNode(child, document, viewportId)),
      )
    );
  }
  return createElement(node.tag, props, node.children.map((child) => renderNode(child, document, viewportId)));
};

const hasGeometryForTree = (node: DesignNode, document: DesignDocument, viewportId: string): boolean => {
  if (!document.resolvedLayouts?.[viewportId]?.nodes[node.id]) return false;
  return node.children.every((child) => hasGeometryForTree(child, document, viewportId));
};

export const DesignDocumentRenderer = ({ document, viewportId, onError }: DesignDocumentRendererProps) => {
  if (!document.resolvedLayouts?.[viewportId])
    return onError?.(`缺少 viewport ${viewportId} 的 Geometry`) ?? null;
  const result = deriveV2RenderModel(document);
  if (!result.ok) return onError?.(result.errors[0]?.message ?? "设计文档无效") ?? null;
  if (!hasGeometryForTree(result.value.root, document, viewportId))
    return onError?.(`viewport ${viewportId} 的 Geometry 未覆盖全部节点`) ?? null;
  return renderNode(result.value.root, document, viewportId);
};

export default DesignDocumentRenderer;
