"use client"

import { createContext, useContext, useEffect, useState } from "react"
import type { ReactNode } from "react"
import { useStore } from "zustand"

import { Workspace } from "@repo/ui/blocks/workspace"

import { createChatStore } from "./chat-store"
import type { ChatState, ChatStore } from "./chat-store"

const ChatStoreContext = createContext<ChatStore | null>(null)

const useChatStore = <Selection,>(selector: (state: ChatState) => Selection) => {
  const store = useContext(ChatStoreContext)
  if (!store) throw new Error("对话 store 必须在 ChatStoreProvider 内使用")
  return useStore(store, selector)
}

const ChatStoreProvider = ({ children }: { children: ReactNode }) => {
  const [store] = useState(createChatStore)
  return <ChatStoreContext.Provider value={store}>{children}</ChatStoreContext.Provider>
}

const getProjectTitle = (prompt: string) =>
  prompt ? `${prompt.slice(0, 12)}${prompt.length > 12 ? "..." : ""}` : "新建项目"

const WorkspaceChatContent = ({ prompt }: { prompt: string }) => {
  const messages = useChatStore((state) => state.messages)
  const status = useChatStore((state) => state.status)
  const error = useChatStore((state) => state.error)
  const initializePrompt = useChatStore((state) => state.initializePrompt)
  const send = useChatStore((state) => state.send)
  const retry = useChatStore((state) => state.retry)
  const cancel = useChatStore((state) => state.cancel)

  useEffect(() => initializePrompt(prompt), [initializePrompt, prompt])
  useEffect(() => () => cancel(), [cancel])

  return (
    <Workspace
      error={error}
      messages={messages}
      projectTitle={getProjectTitle(prompt)}
      status={status}
      onRetry={() => void retry()}
      onSend={(content) => void send(content)}
    />
  )
}

const WorkspaceChat = ({ prompt }: { prompt: string }) => (
  <ChatStoreProvider>
    <WorkspaceChatContent prompt={prompt} />
  </ChatStoreProvider>
)

export { WorkspaceChat }
