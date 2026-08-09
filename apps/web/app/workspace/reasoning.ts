type ReasoningStatus = "reasoning" | "completed" | "truncated";

type ReasoningItem = {
  id: string;
  stage: string;
  taskId: string;
  attempt: number;
  content: string;
  status: ReasoningStatus;
};

const stringValue = (value: unknown) => (typeof value === "string" ? value : "");
const numberValue = (value: unknown) => (typeof value === "number" && value > 0 ? value : 1);

const reasoningId = (data: Record<string, unknown>) =>
  `${stringValue(data.runId) || "run"}:${stringValue(data.taskId) || "task"}:${numberValue(data.attempt)}`;

const applyReasoningEvent = (
  items: readonly ReasoningItem[],
  data: Record<string, unknown>,
): ReasoningItem[] => {
  if (data.event !== "progress") return [...items];
  const payload = data.payload;
  if (!payload || typeof payload !== "object") return [...items];
  const values = payload as Record<string, unknown>;
  const status = values.status;
  const id = reasoningId(data);
  const index = items.findIndex((item) => item.id === id);
  const current = index >= 0 ? items[index] : undefined;
  if (status === "reasoning" || status === "reasoning_truncated") {
    const next: ReasoningItem = {
      id,
      stage: stringValue(data.stage) || "root",
      taskId: stringValue(data.taskId) || "task",
      attempt: numberValue(data.attempt),
      content: `${current?.content || ""}${status === "reasoning" ? stringValue(values.delta) : ""}`,
      status: status === "reasoning_truncated" ? "truncated" : "reasoning",
    };
    return index >= 0
      ? items.map((item, itemIndex) => (itemIndex === index ? next : item))
      : [...items, next];
  }
  if ((status !== "completed" && status !== "reasoning_completed") || !current)
    return [...items];
  return items.map((item, itemIndex) =>
    itemIndex === index ? { ...item, status: "completed" } : item,
  );
};

export { applyReasoningEvent };
export type { ReasoningItem, ReasoningStatus };
