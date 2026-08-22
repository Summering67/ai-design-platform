import requestSchema from "../schema/v2/codegen-request.schema.json" with { type: "json" };
import resultSchema from "../schema/v2/codegen-result.schema.json" with { type: "json" };
import type { DesignDocumentV2, JsonValue } from "./generated-v2.js";

export type CodegenImageSource = { kind: "base64"; data: string } | { kind: "ref"; id: string };

export interface CodegenCanvasImage {
  viewportId: string;
  width: number;
  height: number;
  mimeType: "image/png" | "image/jpeg" | "image/webp";
  image: CodegenImageSource;
}

export interface CodegenCanvasContext {
  viewportIds: string[];
  canvasId?: string;
}

export interface CodegenOptions {
  componentName?: string;
  fileBaseName?: string;
}

export interface CodegenRequest {
  document: DesignDocumentV2;
  /** 服务端根据上下文自动捕获，调用方不上传图片。 */
  canvas: CodegenCanvasContext;
  options?: CodegenOptions;
}

export interface CodegenPlan {
  viewportIds: string[];
  componentMappings: Array<{ nodeId: string; renderAs: string; reason?: string }>;
  layoutStrategy: string;
  styleStrategy: string;
  antdImports?: string[];
  assets: Array<{ assetId: string; usage: string }>;
  risks: string[];
  summary?: string;
}

export type CodegenErrorCode =
  | "codegen_input_invalid"
  | "codegen_input_mismatch"
  | "codegen_model_unavailable"
  | "codegen_plan_invalid"
  | "codegen_generation_failed"
  | "codegen_verification_failed"
  | "codegen_visual_mismatch"
  | "codegen_timeout"
  | "codegen_cancelled"
  | "codegen_limit_exceeded";

export type CodegenFileMediaType = "text/tsx" | "text/css";

export interface CodegenFile {
  path: string;
  mediaType: CodegenFileMediaType;
  content: string;
}

export type CodegenCheckName = "format" | "typescript" | "eslint" | "visual";
export type CodegenCheckStatus = "passed" | "skipped" | "failed";

export interface CodegenCheck {
  name: CodegenCheckName;
  status: CodegenCheckStatus;
  attempts: number;
}

export interface CodegenVerification {
  checks: CodegenCheck[];
  repairAttempts: number;
  risks?: string[];
}

export interface CodegenResult {
  version: "2.0.0";
  documentId: string;
  componentName: string;
  fileBaseName: string;
  files: [CodegenFile, CodegenFile];
  planSummary: string;
  verification: CodegenVerification;
}

export type CodegenJsonValue = JsonValue;

export const codegenRequestSchema = requestSchema;
export const codegenResultSchema = resultSchema;
