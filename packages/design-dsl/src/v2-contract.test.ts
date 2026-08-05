import duplicateId from "@repo/design-contract/fixtures/v2/invalid/duplicate-id.document.json" with { type: "json" };
import unknownAsset from "@repo/design-contract/fixtures/v2/invalid/unknown-asset.document.json" with { type: "json" };
import runtimeField from "@repo/design-contract/fixtures/v2/invalid/runtime-field.document.json" with { type: "json" };
import cssText from "@repo/design-contract/fixtures/v2/invalid/css-text.document.json" with { type: "json" };
import hiddenNode from "@repo/design-contract/fixtures/v2/invalid/hidden-node-in-props.document.json" with { type: "json" };
import { validateDesignDocument } from "./v2.js";

const assert = (condition: unknown, message: string): void => {
  if (!condition) throw new Error(message);
};

const cases = [
  [duplicateId, "duplicate_id"],
  [unknownAsset, "unknown_asset"],
  [runtimeField, "schema_validation"],
  [cssText, "schema_validation"],
  [hiddenNode, "nested_design_node"],
] as const;

cases.forEach(([input, code]) => {
  const result = validateDesignDocument(input);
  assert(!result.ok, `${code} fixture 必须被拒绝`);
  if (!result.ok)
    assert(result.errors.some((error) => error.code === code), `${code} 错误码必须稳定`);
});
