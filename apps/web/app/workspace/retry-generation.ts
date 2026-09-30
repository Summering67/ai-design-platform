import type { ChatMessage } from "./chat-api";

const retryGenerationPath = (projectId: string, messages: ChatMessage[], messageId: string) => {
  const message = messages.find(
    (item) =>
      item.role === "user" && (item.id === messageId || item.client_message_id === messageId),
  );
  return message ? `/projects/${projectId}/messages/${message.id}/generations` : null;
};

export { retryGenerationPath };
