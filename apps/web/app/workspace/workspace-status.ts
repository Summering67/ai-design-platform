type WorkspaceStatus = "idle" | "loading" | "awaiting_input" | "error";

const settleGenerationStatus = (status: WorkspaceStatus): WorkspaceStatus =>
  status === "loading" ? "idle" : status;

export { settleGenerationStatus };
export type { WorkspaceStatus };
