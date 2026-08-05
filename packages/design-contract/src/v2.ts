import schema from "../schema/v2/design-document.schema.json" with {
  type: "json",
};
import type {
  Asset,
  DesignDocumentV2,
  DesignSystem,
  JsonValue,
  Node,
} from "./generated-v2.js";

export type DesignDocument = DesignDocumentV2;
export type DesignSystemSnapshot = DesignSystem;
export type DesignAsset = Asset;
export type DesignNode = Node;
export type DesignJsonValue = JsonValue;
export { schema as designDocumentSchemaV2 };
