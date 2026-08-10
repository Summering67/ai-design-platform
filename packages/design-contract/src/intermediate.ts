import designDocumentSchema from "../schema/v2/design-document.schema.json" with { type: "json" };
import initialUiDocumentSchemaSource from "../schema/v2/initial-ui-document.schema.json" with { type: "json" };
import layoutPlanSchema from "../schema/v2/layout-plan.schema.json" with { type: "json" };
import type { JsonValue } from "./generated-v2.js";

const initialUiDocumentSchema = {
  ...initialUiDocumentSchemaSource,
  $defs: {
    ...initialUiDocumentSchemaSource.$defs,
    style: designDocumentSchema.$defs.visualStyle,
    styleValue: designDocumentSchema.$defs.styleValue,
  },
};

export type InitialUIDocument = {
  version: "1.0.0";
  id: string;
  name: string;
  assets: Record<string, { id: string; type: "image" | "icon" | "font" | "file"; src: string; mimeType: string; alt?: string }>;
  root: InitialUINode;
};
export type InitialUINode = {
  id: string;
  kind: "element" | "text" | "image" | "component";
  name: string;
  tag: string;
  packageName?: string;
  defaultModule?: boolean;
  style: Record<string, number | string | boolean>;
  props: Record<string, JsonValue>;
  tokens?: string[];
  layoutIntent?: {
    role: "page" | "section" | "navigation" | "toolbar" | "sidebar" | "content" | "list" | "grid" | "form" | "field-group" | "actions" | "overlay";
    grouping?: "single" | "collection" | "paired" | "cluster";
    adaptivity?: "preserve" | "reflow" | "condense";
    density?: "compact" | "comfortable" | "spacious";
  };
  children: InitialUINode[];
  text?: string;
  assetId?: string;
  alt?: string;
};
export type LayoutPlan = {
  version: "1.0.0";
  viewport: { width: number; height: number };
  operations: Array<{ nodeId: string; layout?: Record<string, JsonValue>; layoutItem?: Record<string, JsonValue>; responsive?: Record<string, Record<string, JsonValue>> }>;
};

export { initialUiDocumentSchema, layoutPlanSchema };
