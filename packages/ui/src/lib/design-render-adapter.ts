import type {
  DesignRenderNode,
  DesignSystemProfile,
  ProfileComponentContract,
  ValidatedDesignRenderModel,
} from "@repo/design-dsl/legacy";
import { createElement, type CSSProperties, type ReactNode } from "react";
import { Button, Card, Form, Input, Menu } from "antd";

export type AdapterError = { code: "adapter_incompatible" | "adapter_unsupported"; message: string };
export type AdapterResult<T> = { ok: true; value: T } | { ok: false; error: AdapterError };

export type ThemeResolver = {
  resolveStyle: (node: DesignRenderNode, model: ValidatedDesignRenderModel) => AdapterResult<CSSProperties>;
  resolveTypography: (node: Extract<DesignRenderNode, { kind: "text" }>, model: ValidatedDesignRenderModel) => AdapterResult<CSSProperties>;
};
export type LayoutMapper = {
  map: (node: Extract<DesignRenderNode, { kind: "frame" }>) => AdapterResult<CSSProperties>;
};
export type ComponentRegistry = {
  render: (node: Extract<DesignRenderNode, { kind: "component-instance" }>, children: ReactNode) => AdapterResult<ReactNode>;
};
export type IconRegistry = { render: (name: string) => AdapterResult<ReactNode> };
export type AssetResolver = { resolve: (assetId: string, model: ValidatedDesignRenderModel) => AdapterResult<string> };
export type DesignRenderAdapter = {
  targetId: string;
  profile: Pick<DesignSystemProfile, "id" | "version" | "digest">;
  capabilities: string[];
  theme: ThemeResolver;
  layout: LayoutMapper;
  components: ComponentRegistry;
  icons: IconRegistry;
  assets: AssetResolver;
};

const success = <T>(value: T): AdapterResult<T> => ({ ok: true, value });
const failure = (message: string): AdapterResult<never> => ({ ok: false, error: { code: "adapter_unsupported", message } });

const resolveToken = (value: unknown, tokens: Record<string, unknown>): unknown =>
  value && typeof value === "object" && "token" in value && typeof value.token === "string"
    ? tokens[value.token]
    : value;

const defaultTheme: ThemeResolver = {
  resolveStyle: (node, model) => {
    const style = node.style ?? {};
    return success({
      background: resolveToken(style.background, model.tokens) as CSSProperties["background"],
      borderRadius: resolveToken(style.radius, model.tokens) as CSSProperties["borderRadius"],
      opacity: style.opacity,
    });
  },
  resolveTypography: (node, model) => success({
    ...(resolveToken(node.typography, model.tokens) as CSSProperties),
  }),
};

const defaultLayout: LayoutMapper = {
  map: (node) => {
    if (!node.layout) return success({});
    if (node.layout.mode === "absolute") return success({ position: "absolute" });
    return success({ display: "flex", flexDirection: node.layout.direction, gap: node.layout.gap, flexWrap: node.layout.wrap ? "wrap" : undefined });
  },
};

type ComponentNode = Extract<DesignRenderNode, { kind: "component-instance" }>;
const componentMap: Record<string, (node: ComponentNode, children: ReactNode) => ReactNode> = {
  "ui.button": (node, children) => createElement(Button, { type: node.variant?.type === "primary" ? "primary" : "default" }, children),
  "ui.input": (node) => createElement(Input, { placeholder: typeof node.overrides?.placeholder === "string" ? node.overrides.placeholder : undefined }),
  "ui.card": (_node, children) => createElement(Card, null, children),
  "ui.form": (_node, children) => createElement(Form, null, children),
  "ui.menu": (node) => createElement(Menu, { items: Array.isArray(node.overrides?.items) ? node.overrides.items as { key: string; label: ReactNode }[] : [] }),
};
export const createComponentRegistry = (renderers: typeof componentMap = componentMap): ComponentRegistry => ({
  render: (node, children) => {
    const renderer = renderers[node.componentRef];
    return renderer
      ? success(renderer(node, children))
      : failure(`未注册组件 ${node.componentRef}`);
  },
});

export const createDefaultDesignRenderAdapter = (profile: DesignSystemProfile): DesignRenderAdapter => ({
  targetId: "antd",
  profile,
  capabilities: ["flex", "absolute", "text", "image", "icon", "component"],
  theme: defaultTheme,
  layout: defaultLayout,
  components: createComponentRegistry(componentMap),
  icons: { render: (name) => ({ check: success(createElement("span", null, "✓")), close: success(createElement("span", null, "×")) }[name] ?? failure(`未注册图标 ${name}`)) },
  assets: { resolve: (assetId, model) => model.assets[assetId] ? success(model.assets[assetId].source) : failure(`未找到资源 ${assetId}`) },
});

export type { ProfileComponentContract };
