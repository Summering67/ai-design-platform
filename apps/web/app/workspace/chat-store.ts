import { createStore } from "zustand/vanilla"
import type { StoreApi } from "zustand/vanilla"

import type { ChatMessage, ChatStatus } from "@repo/ui/blocks/workspace"

import { requestChat } from "./chat-api"
import type { ChatReply } from "./chat-api"

type ChatRequest = (
  messages: ReadonlyArray<ChatMessage>,
  signal: AbortSignal,
) => Promise<ChatReply>

type ChatState = {
  messages: ChatMessage[]
  status: ChatStatus
  error: string | null
  failedMessages: ChatMessage[] | null
  initializedPrompt: string | null
  initializePrompt: (prompt: string) => void
  send: (content: string) => Promise<void>
  retry: () => Promise<void>
  reset: () => void
  cancel: () => void
}

type ChatStore = StoreApi<ChatState>

const createMessage = (role: ChatMessage["role"], content: string): ChatMessage => ({
  id: crypto.randomUUID(),
  role,
  content,
})

const createChatStore = (complete: ChatRequest = requestChat): ChatStore => {
  let activeRequest: AbortController | null = null

  return createStore<ChatState>()((set, get) => {
    const completeMessages = async (messages: ChatMessage[]) => {
      const controller = new AbortController()
      activeRequest = controller
      set({ status: "loading", error: null, failedMessages: null })
      try {
        const reply = await complete(messages, controller.signal)
        if (activeRequest !== controller) return
        set((state) => ({
          messages: [...state.messages, createMessage(reply.role, reply.content)],
          status: "idle",
        }))
      } catch (error) {
        if (activeRequest !== controller) return
        set({
          status: "error",
          error: error instanceof Error ? error.message : "暂时无法连接 AI 服务，请重试。",
          failedMessages: messages,
        })
      } finally {
        if (activeRequest === controller) activeRequest = null
      }
    }

    return {
      messages: [],
      status: "idle",
      error: null,
      failedMessages: null,
      initializedPrompt: null,
      initializePrompt: (prompt) => {
        const content = prompt.trim()
        const state = get()
        if (state.initializedPrompt === null) {
          set({ initializedPrompt: content })
          if (content) void get().send(content)
          return
        }
        if (
          state.initializedPrompt !== content ||
          !content ||
          state.status !== "idle" ||
          state.messages.at(-1)?.role !== "user"
        ) return
        void completeMessages(state.messages)
      },
      send: async (content) => {
        const normalizedContent = content.trim()
        if (!normalizedContent || get().status === "loading") return
        const messages = [...get().messages, createMessage("user", normalizedContent)]
        set({ messages })
        await completeMessages(messages)
      },
      retry: async () => {
        const { failedMessages, status } = get()
        if (!failedMessages || status === "loading") return
        await completeMessages(failedMessages)
      },
      reset: () => {
        activeRequest?.abort()
        activeRequest = null
        set({
          messages: [],
          status: "idle",
          error: null,
          failedMessages: null,
          initializedPrompt: null,
        })
      },
      cancel: () => {
        activeRequest?.abort()
        activeRequest = null
        if (get().status === "loading") set({ status: "idle" })
      },
    }
  })
}

export { createChatStore }
export type { ChatState, ChatStore }
