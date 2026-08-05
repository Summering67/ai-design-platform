import { createElement, type CSSProperties, type ReactNode } from "react";
import {
  deriveV2RenderModel,
  type DesignDocument,
  type DesignNode,
  type V2RenderModel,
} from "@repo/design-dsl";

export type DesignDocumentRendererProps = {
  document: DesignDocument;
  onError?: (message: string) => ReactNode;
};

const renderNode = (node: DesignNode, model: V2RenderModel): ReactNode => {
  const props = {
    ...node.props,
    style: node.style as CSSProperties,
    "data-design-node-id": node.id,
  };
  if (node.kind === "text") return createElement(node.tag, props, node.text);
  if (node.kind === "image") {
    const asset = model.assets[node.assetId!];
    return asset
      ? createElement("img", { ...props, src: asset.src, alt: node.alt ?? asset.alt ?? node.name })
      : null;
  }
  if (node.kind === "component")
    return createElement("span", { ...props, "data-design-component": node.tag }, node.children.map((child) => renderNode(child, model)));
  return createElement(node.tag, props, node.children.map((child) => renderNode(child, model)));
};

export const DesignDocumentRenderer = ({ document, onError }: DesignDocumentRendererProps) => {
  const result = deriveV2RenderModel(document);
  if (!result.ok) return onError?.(result.errors[0]?.message ?? "设计文档无效") ?? null;
  return renderNode(result.value.root, result.value);
};

export default DesignDocumentRenderer;
