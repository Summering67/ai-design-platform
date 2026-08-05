import { createElement, type CSSProperties, type ReactNode } from "react";
import type { DesignRenderNode, ValidatedDesignRenderModel } from "@repo/design-dsl/legacy";
import { createDefaultDesignRenderAdapter, type DesignRenderAdapter } from "../../lib/design-render-adapter";

export type DesignRendererProps = {
  model: ValidatedDesignRenderModel;
  adapter?: DesignRenderAdapter;
  onError?: (message: string) => ReactNode;
};

const compatible = (model: ValidatedDesignRenderModel, adapter: DesignRenderAdapter): boolean =>
  model.profile.id === adapter.profile.id && model.profile.version === adapter.profile.version && model.profile.digest === adapter.profile.digest;

const renderNode = (node: DesignRenderNode, model: ValidatedDesignRenderModel, adapter: DesignRenderAdapter): ReactNode => {
  if (!node.visible) return null;
  const styleResult = adapter.theme.resolveStyle(node, model);
  if (!styleResult.ok) return null;
  const children =
    node.kind === "frame"
      ? node.children.map((child) => renderNode(child, model, adapter))
      : node.kind === "component-instance" && typeof node.overrides?.children === "string"
        ? node.overrides.children
        : null;
  const frameStyle = node.kind === "frame" ? adapter.layout.map(node) : { ok: true as const, value: {} };
  if (!frameStyle.ok) return null;
  const style = { ...styleResult.value, ...frameStyle.value } as CSSProperties;
  const props = { key: node.id, style, "data-design-node-id": node.id };
  if (node.kind === "frame") return createElement("div", props, children);
  if (node.kind === "text") {
    const typography = adapter.theme.resolveTypography(node, model);
    return createElement("span", { ...props, style: { ...style, ...(typography.ok ? typography.value : {}) } }, node.text);
  }
  if (node.kind === "image") {
    const source = adapter.assets.resolve(node.assetId, model);
    return source.ok ? createElement("img", { ...props, src: source.value, alt: node.alt ?? node.name ?? "" }) : null;
  }
  if (node.kind === "icon") {
    const icon = adapter.icons.render(node.name);
    return icon.ok ? createElement("span", props, icon.value) : null;
  }
  const component = adapter.components.render(node, children);
  return component.ok ? createElement("span", props, component.value) : null;
};

export const DesignRenderer = ({ model, adapter = createDefaultDesignRenderAdapter({ id: model.profile.id, version: model.profile.version, digest: model.profile.digest, name: "validated", tokens: model.tokens, components: {}, layout: {} }), onError }: DesignRendererProps) => {
  if (!compatible(model, adapter)) return onError?.("adapter_incompatible") ?? null;
  return createElement("div", { "data-design-profile": `${model.profile.id}@${model.profile.version}` }, model.pages.map((page) => createElement("section", { key: page.id, "data-design-page-id": page.id }, page.nodes.map((node) => renderNode(node, model, adapter)))));
};

export default DesignRenderer;
