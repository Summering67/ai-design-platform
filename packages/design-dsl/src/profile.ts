import { applyOperations, normalize, validateDocument, validateTree } from "./core.js";
import type {
  ContractError,
  DesignGenerationContract,
  DesignSystemProfile,
  Document,
  ProfileReference,
  Result,
  TreeDocument,
  TreeNode,
  Operation,
} from "./types.js";

const fail = <T>(...errors: ContractError[]): Result<T> => ({
  ok: false,
  errors,
});

const ok = <T>(value: T): Result<T> => ({ ok: true, value, warnings: [] });

const profileError = (
  profile: DesignSystemProfile,
  path: string,
  message: string,
): ContractError => ({
  code: "profile_invalid",
  path,
  message: `${profile.id}@${profile.version}: ${message}`,
});

const profileRef = (profile: DesignSystemProfile): ProfileReference => ({
  id: profile.id,
  version: profile.version,
  digest: profile.digest,
});

const tokenRefs = (value: unknown, path: string): Array<[string, string]> => {
  if (!value || typeof value !== "object") return [];
  if (
    !Array.isArray(value) &&
    "token" in value &&
    typeof value.token === "string"
  )
    return [[value.token, path]];
  return Object.entries(value).flatMap(([key, item]) =>
    tokenRefs(item, `${path}/${key}`),
  );
};

const sizingModes = (node: TreeNode): string[] => {
  const item = node.layoutItem;
  return [item?.width?.mode, item?.height?.mode].filter(
    (mode): mode is NonNullable<typeof mode> => Boolean(mode),
  );
};

const validateNode = (
  node: TreeNode,
  assets: TreeDocument["assets"],
  profile: DesignSystemProfile,
  path: string,
  errors: ContractError[],
): void => {
  for (const [token, tokenPath] of [
    ...tokenRefs(node.style, `${path}/style`),
    ...tokenRefs(node.kind === "text" ? node.typography : undefined, `${path}/typography`),
  ])
    if (!(token in profile.tokens))
      errors.push(profileError(profile, tokenPath, `Token ${token} 不存在`));

  if (node.kind === "frame") {
    if (node.layout?.mode && !profile.layout.modes?.includes(node.layout.mode))
      errors.push(
        profileError(profile, `${path}/layout/mode`, "布局模式未被 Profile 允许"),
      );
    sizingModes(node).forEach((mode) => {
      if (!profile.layout.sizing?.includes(mode as never))
        errors.push(
          profileError(profile, `${path}/layoutItem`, `尺寸策略 ${mode} 未被允许`),
        );
    });
    node.children.forEach((child, index) =>
      validateNode(child, assets, profile, `${path}/children/${index}`, errors),
    );
    return;
  }

  if (node.kind === "image") {
    const asset = assets[node.assetId];
    const allowedMimeTypes = profile.assets?.mimeTypes;
    if (
      asset &&
      allowedMimeTypes?.length &&
      !allowedMimeTypes.includes("*") &&
      !allowedMimeTypes.includes(asset.mimeType)
    )
      errors.push(profileError(profile, `${path}/assetId`, "资源类型未被 Profile 允许"));
    if (asset && profile.assets?.sources?.length && !profile.assets.sources.some((source) => asset.source.startsWith(source)))
      errors.push(profileError(profile, `${path}/assetId`, "资源来源未被 Profile 允许"));
  }

  if (node.kind === "icon" && profile.icons && !(node.name in profile.icons))
    errors.push(profileError(profile, `${path}/name`, "图标未被 Profile 注册"));

  if (node.kind !== "component-instance") return;
  const contract = profile.components[node.componentRef];
  if (!contract) {
    errors.push(
      profileError(profile, `${path}/componentRef`, "组件未被 Profile 注册"),
    );
    return;
  }
  Object.entries(node.variant ?? {}).forEach(([axis, value]) => {
    const allowed = (contract.allowedVariants ?? contract.variants)?.[axis];
    if (allowed && !allowed.includes(value))
      errors.push(
        profileError(profile, `${path}/variant/${axis}`, "组件变体未被允许"),
      );
  });
  Object.keys(node.slots ?? {}).forEach((slot) => {
    if (!contract.slots?.[slot])
      errors.push(profileError(profile, `${path}/slots/${slot}`, "命名 slot 未被允许"));
  });
  Object.keys(node.overrides ?? {}).forEach((key) => {
    if (!contract.overrides || !(key in contract.overrides))
      errors.push(
        profileError(profile, `${path}/overrides/${key}`, "组件覆盖属性未被允许"),
      );
  });
};

export const profileReference = profileRef;

export const deriveGenerationContract = (
  profile: DesignSystemProfile,
): DesignGenerationContract => ({
  profile: profileRef(profile),
  nodeKinds: ["frame", "text", "image", "icon", "component-instance"],
  tokens: Object.keys(profile.tokens).sort(),
  components: structuredClone(profile.components),
  layout: structuredClone(profile.layout),
  icons: Object.keys(profile.icons ?? {}).sort(),
});

export const validateTreeWithProfile = (
  tree: TreeDocument,
  profile: DesignSystemProfile,
): Result<TreeDocument> => {
  const checked = validateTree(tree);
  if (!checked.ok) return checked;
  const errors: ContractError[] = [];
  if (
    tree.profile &&
    (tree.profile.id !== profile.id ||
      tree.profile.version !== profile.version ||
      tree.profile.digest !== profile.digest)
  )
    errors.push(profileError(profile, "/profile", "Profile 引用或摘要不匹配"));
  tree.pages.forEach((page, pageIndex) =>
    page.children.forEach((node, index) =>
      validateNode(node, tree.assets, profile, `/pages/${pageIndex}/children/${index}`, errors),
    ),
  );
  return errors.length ? fail(...errors) : ok(tree);
};

export const normalizeWithProfile = (
  tree: TreeDocument,
  profile: DesignSystemProfile,
): Result<Document> => {
  const checked = validateTreeWithProfile(tree, profile);
  if (!checked.ok) return checked;
  return normalize({ ...tree, profile: profileRef(profile) });
};

export const validateDocumentWithProfile = (
  document: Document,
  profile: DesignSystemProfile,
): Result<Document> => {
  const checked = validateDocument(document);
  if (!checked.ok) return checked;
  if (
    !document.profile ||
    document.profile.id !== profile.id ||
    document.profile.version !== profile.version ||
    document.profile.digest !== profile.digest
  )
    return fail(profileError(profile, "/profile", "Profile 引用或摘要不匹配"));
  return ok(document);
};

export const applyOperationsWithProfile = (
  document: Document,
  operations: Operation[],
  profile: DesignSystemProfile,
): Result<Document> => {
  const initial = validateDocumentWithProfile(document, profile);
  if (!initial.ok) return initial;
  const result = applyOperations(document, operations);
  if (result.ok) {
    const checked = validateDocumentWithProfile(result.value, profile);
    if (checked.ok) return checked;
    return fail(
      ...checked.errors.map((item) => ({
        ...item,
        path: `/operations/${operations.length}${item.path}`,
      })),
    );
  }
  return fail(
    ...result.errors.map((item) => ({
      ...item,
      path: `/operations/${Math.max(operations.length - 1, 0)}${item.path}`,
      message: `${profile.id}@${profile.version}: ${item.message}`,
    })),
  );
};
