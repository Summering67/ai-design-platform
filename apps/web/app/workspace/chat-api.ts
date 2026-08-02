import type { ChatMessage } from "@repo/ui/blocks/workspace"

type ChatReply = Pick<ChatMessage, "role" | "content">

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null

const parseReply = (value: unknown): ChatReply | null => {
  if (!isRecord(value) || !isRecord(value.message)) return null
  const { content, role } = value.message
  if (role !== "assistant" || typeof content !== "string" || !content.trim()) return null
  return { role, content: content.trim() }
}

const getErrorMessage = (value: unknown) => {
  if (!isRecord(value) || !isRecord(value.error) || typeof value.error.code !== "string") {
    return "暂时无法连接 AI 服务，请重试。"
  }
  const messages: Record<string, string> = {
    ai_timeout: "AI 响应超时，请重试。",
    invalid_request: "当前对话内容无法发送，请精简后重试。",
  }
  return messages[value.error.code] || "暂时无法连接 AI 服务，请重试。"
}

const readJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.json()
  } catch {
    return null
  }
}

const requestChat = async (
  messages: ReadonlyArray<ChatMessage>,
  signal: AbortSignal,
): Promise<ChatReply> => {
  const response = await fetch("/backend/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(({ content, role }) => ({ content, role })),
    }),
    signal,
  })
  const body = await readJson(response)
  if (!response.ok) throw new Error(getErrorMessage(body))
  const reply = parseReply(body)
  if (!reply) throw new Error("AI 返回了无法识别的内容，请重试。")
  return reply
}

export { requestChat }
export type { ChatReply }
