type ChatMessage = {
  id: string;
  client_message_id?: string | null;
  role: "user" | "assistant";
  content: string;
};
type Project = { id: string; title: string };
type InputQuestionOption = { label: string; description: string };
type InputQuestion = {
  id: string;
  header?: string;
  question?: string;
  isOther?: boolean;
  options?: InputQuestionOption[];
  text?: string;
};
type PendingInputRequest = {
  id: string;
  generation_id: string;
  source_stage: string;
  source_task_id: string;
  round: number;
  questions: InputQuestion[];
  status: "pending" | "answered";
};
type Event = { event: string; data: Record<string, unknown> };

class RequestError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}
const api = "/backend/api";
const parseError = async (response: Response) => {
  const body = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  return new RequestError(
    body?.error?.code || "internal_error",
    body?.error?.message || "请求失败",
    response.status,
  );
};
const loadProject = async (projectId: string) => {
  const response = await fetch(`${api}/projects/${projectId}`);
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<{
    project: Project;
    messages: ChatMessage[];
    pending_input_request?: PendingInputRequest;
  }>;
};
const login = async (email: string, password: string) => {
  const response = await fetch(`${api}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<{ email: string }>;
};
const currentUser = async () => {
  const response = await fetch(`${api}/auth/me`);
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<{ email: string }>;
};
const logout = async () => {
  const response = await fetch(`${api}/auth/logout`, { method: "POST" });
  if (!response.ok) throw await parseError(response);
};
const stopGeneration = async (projectId: string, generationId: string) => {
  const response = await fetch(
    `${api}/projects/${projectId}/generations/${generationId}/stop`,
    { method: "POST" },
  );
  if (!response.ok) throw await parseError(response);
};
const answerInput = async (
  projectId: string,
  generationId: string,
  requestId: string,
  body: { response_id: string; answers: { question_id: string; content: string }[] },
  signal: AbortSignal,
  onEvent: (event: Event) => void,
) => generate(
  `/projects/${projectId}/generations/${generationId}/input-requests/${requestId}/answers`,
  body,
  signal,
  onEvent,
);
const readEvents = async (
  response: Response,
  onEvent: (event: Event) => void,
) => {
  if (!response.body) throw new Error("生成响应不可读取");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const event = chunk.match(/^event: (.+)$/m)?.[1];
      const data = chunk.match(/^data: (.+)$/m)?.[1];
      if (event && data)
        onEvent({ event, data: JSON.parse(data) as Record<string, unknown> });
    }
    if (done) return;
  }
};
const generate = async (
  path: string,
  body: object | undefined,
  signal: AbortSignal,
  onEvent: (event: Event) => void,
) => {
  const response = await fetch(`${api}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!response.ok) throw await parseError(response);
  await readEvents(response, onEvent);
};

export {
  RequestError,
  answerInput,
  currentUser,
  generate,
  loadProject,
  login,
  logout,
  stopGeneration,
};
export type { ChatMessage, InputQuestion, InputQuestionOption, PendingInputRequest, Project };
