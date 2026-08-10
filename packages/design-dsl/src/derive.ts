import { validateDocument } from "./core.js";
import { validateDocumentWithProfile } from "./profile.js";
import type {
  DesignRenderNode,
  DesignSystemProfile,
  Document,
  ProfileComponentContract,
  Result,
  StoredNode,
  ValidatedDesignRenderModel,
} from "./types.js";

export type PreviewNode = {
  id: string;
  kind: StoredNode["kind"];
  visible: boolean;
  style: Record<string, unknown>;
  children: PreviewNode[];
};
export const deriveDomPreview = (document: Document): Result<PreviewNode[]> => {
  const checked = validateDocument(document);
  if (!checked.ok) return checked;
  const render = (page: Document["pages"][number], id: string): PreviewNode => {
    const node = page.nodes[id]!;
    if (node.kind === "root") throw new Error("Root 不可直接渲染");
    const childIds = "childIds" in node ? node.childIds : [];
    return {
      id,
      kind: node.kind,
      visible: node.visible !== false,
      style: {
        ...(node.style ?? {}),
        ...(node.kind === "frame"
          ? { layout: node.layout, layoutItem: node.layoutItem }
          : { layoutItem: node.layoutItem }),
      },
      children: childIds.map((child) => render(page, child)),
    };
  };
  return {
    ok: true,
    value: document.pages.flatMap((page) => {
      const root = page.nodes[page.rootId];
      return root?.kind === "root"
        ? root.childIds.map((id) => render(page, id))
        : [];
    }),
    warnings: [],
  };
};

const legacyProfile = (document: Document): DesignSystemProfile => ({
  id: document.profile?.id ?? "legacy-document-profile",
  version: document.profile?.version ?? document.version,
  digest: document.profile?.digest ?? "legacy-document-digest",
  name: document.name,
  tokens: document.tokens ?? {},
  components: Object.fromEntries(
    Object.entries(document.componentDefinitions ?? {}).map(([id, definition]) => [
      id,
      { id, propsSchema: definition.propsSchema },
    ]),
  ),
  layout: {
    modes: ["flex", "absolute"],
    sizing: ["fixed", "fill", "hug"],
  },
  icons: {},
});

const componentContract = (
  document: Document,
  profile: DesignSystemProfile,
  componentRef: string,
): ProfileComponentContract =>
  profile.components[componentRef] ?? {
    id: componentRef,
    propsSchema: document.componentDefinitions?.[componentRef]?.propsSchema ?? {},
  };

export const deriveDesignRenderModel = (
  document: Document,
  suppliedProfile?: DesignSystemProfile,
): Result<ValidatedDesignRenderModel> => {
  const profile = suppliedProfile ?? legacyProfile(document);
  const checked = suppliedProfile
    ? validateDocumentWithProfile(document, profile)
    : validateDocumentWithProfile(
        { ...document, profile: document.profile ?? { id: profile.id, version: profile.version, digest: profile.digest } },
        profile,
      );
  if (!checked.ok) return checked;
  const render = (
    page: Document["pages"][number],
    id: string,
  ): DesignRenderNode => {
    const node = page.nodes[id]!;
    if (node.kind === "root") throw new Error("Root 不可渲染");
    const common = {
      id,
      ...(node.name ? { name: node.name } : {}),
      visible: node.visible !== false,
      ...(node.style ? { style: structuredClone(node.style) } : {}),
      ...(node.layoutItem ? { layoutItem: structuredClone(node.layoutItem) } : {}),
      ...(node.semantic ? { semantic: structuredClone(node.semantic) } : {}),
    };
    if (node.kind === "frame")
      return {
        ...common,
        kind: "frame",
        ...(node.layout ? { layout: structuredClone(node.layout) } : {}),
        children: node.childIds.map((child) => render(page, child)),
      };
    if (node.kind === "text")
      return {
        ...common,
        kind: "text",
        text: node.text,
        typography: structuredClone(node.typography),
        children: [],
      };
    if (node.kind === "image")
      return {
        ...common,
        kind: "image",
        assetId: node.assetId,
        asset: structuredClone(document.assets[node.assetId]!),
        ...(node.alt ? { alt: node.alt } : {}),
        children: [],
      };
    if (node.kind === "icon")
      return { ...common, kind: "icon", name: node.name, children: [] };
    return {
      ...common,
      kind: "component-instance",
      componentRef: node.componentRef,
      ...(node.variant ? { variant: structuredClone(node.variant) } : {}),
      ...(node.slots ? { slots: structuredClone(node.slots) } : {}),
      ...(node.overrides ? { overrides: structuredClone(node.overrides) } : {}),
      contract: structuredClone(
        componentContract(document, profile, node.componentRef),
      ),
      children: [],
    };
  };
  return {
    ok: true,
    value: {
      profile: { id: profile.id, version: profile.version, digest: profile.digest },
      tokens: structuredClone(profile.tokens),
      assets: structuredClone(document.assets),
      pages: document.pages.map((page) => {
        const root = page.nodes[page.rootId];
        return {
          id: page.id,
          name: page.name,
          nodes:
            root?.kind === "root"
              ? root.childIds.map((id) => render(page, id))
              : [],
        };
      }),
      credentials: { validated: true, digest: profile.digest },
    },
    warnings: [],
  };
};
const failure = (path: string, message: string): Result<never> => ({
  ok: false,
  errors: [{ code: "generation_error", path, message }],
});
const componentNames: Record<string, string> = {
  "ui.button": "Button",
  "ui.input": "Input",
  "ui.card": "Card",
  "ui.form": "Form",
  "ui.menu": "Menu",
};
export const generateReactTailwindAntd = (
  document: Document,
): Result<{ code: string; imports: string[] }> => {
  const checked = validateDocument(document);
  if (!checked.ok) return checked;
  const imports = new Set<string>();
  const render = (
    page: Document["pages"][number],
    id: string,
  ): string | Result<never> => {
    const node = page.nodes[id]!;
    if (node.kind === "root")
      return failure(`/nodes/${id}`, "Root 不可直接生成");
    if (node.visible === false) return "";
    if (node.kind === "text") return `<span>${node.text}</span>`;
    if (node.kind === "image")
      return `<img src={assets[${JSON.stringify(node.assetId)}]} alt=${JSON.stringify(node.alt ?? "")} />`;
    if (node.kind === "icon")
      return `<span aria-hidden="true">${node.name}</span>`;
    if (node.kind === "component-instance") {
      const binding = document.componentBindings?.[node.componentRef];
      const name = componentNames[node.componentRef];
      if (
        !binding ||
        !name ||
        binding.codeBinding.exportName !== name ||
        binding.codeBinding.importFrom !== "antd"
      )
        return failure(`/nodes/${id}`, "组件绑定不受支持");
      imports.add(name);
      const content =
        typeof node.overrides?.children === "string"
          ? node.overrides.children
          : "";
      return `<${name}>${content}</${name}>`;
    }
    const rendered = node.childIds.map((child: string) => render(page, child));
    const invalid = rendered.find(
      (item): item is Result<never> => typeof item !== "string",
    );
    if (invalid) return invalid;
    return `<div className="flex ${node.layout?.mode === "flex" && node.layout.direction === "row" ? "flex-row" : "flex-col"}">${rendered.join("")}</div>`;
  };
  const body = document.pages.flatMap((page) => {
    const root = page.nodes[page.rootId];
    return root?.kind === "root"
      ? root.childIds.map((id) => render(page, id))
      : [];
  });
  const invalid = body.find(
    (item): item is Result<never> => typeof item !== "string",
  );
  if (invalid) return invalid;
  const tokenLines = Object.entries(document.tokens ?? {})
    .map(([key, value]) => `  "${key}": ${JSON.stringify(value)},`)
    .join("\n");
  const names = [...imports].sort();
  const importLine = names.length
    ? `import { ${names.join(", ")} } from "antd";\n`
    : "";
  return {
    ok: true,
    value: {
      imports: names,
      code: `${importLine}const tokens = {\n${tokenLines}\n};\n\nexport const GeneratedDesign = () => <main>${body.join("")}</main>;\n`,
    },
    warnings: [],
  };
};
