"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Workspace } from "@repo/ui/blocks/workspace";
import type { DesignDocument } from "@repo/design-dsl";
import {
  RequestError,
  currentUser,
  generate,
  loadProject,
  logout,
  stopGeneration,
} from "./chat-api";
import type { ChatMessage, Project } from "./chat-api";

const WorkspaceChat = ({
  projectId,
  prompt,
}: {
  projectId?: string;
  prompt?: string;
}) => {
  const router = useRouter();
  const controller = useRef<AbortController | null>(null);
  const sendRef = useRef<(content: string) => void>(() => undefined);
  const [project, setProject] = useState<Project | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [stream, setStream] = useState("");
  const [document, setDocument] = useState<DesignDocument | null>(null);
  const [email, setEmail] = useState("");
  const appendAgentMessage = (data: Record<string, unknown>) => {
    const stage = typeof data.stage === "string" ? data.stage : "root";
    const event = typeof data.event === "string" ? data.event : "progress";
    setMessages((items) => [
      ...items,
      {
        id: crypto.randomUUID(),
        role: "assistant" as const,
        content: `【Agent · ${stage} · ${event}】\n${JSON.stringify(data.payload ?? {}, null, 2)}`,
      },
    ]);
  };
  useEffect(() => {
    void currentUser()
      .then((user) => setEmail(user.email))
      .catch(() => router.replace("/login"));
  }, [router]);
  useEffect(() => {
    if (!projectId) return;
    void loadProject(projectId)
      .then(({ project: nextProject, messages: nextMessages }) => {
        setProject(nextProject);
        setMessages(nextMessages);
      })
      .catch((reason: unknown) => {
        if (reason instanceof RequestError && reason.status === 401)
          router.replace(
            `/login?next=${encodeURIComponent(`/workspace/${projectId}`)}`,
          );
        else setError("读取项目失败");
      });
  }, [projectId, router]);
  useEffect(() => {
    if (
      !prompt ||
      projectId ||
      sessionStorage.getItem("aidp-prompt-sent") === prompt
    )
      return;
    sessionStorage.setItem("aidp-prompt-sent", prompt);
    sendRef.current(prompt);
  }, [prompt, projectId]);
  const send = async (content: string) => {
    if (status === "loading") return;
    const messageId = crypto.randomUUID();
    const userMessage = { id: messageId, role: "user" as const, content };
    setMessages((items) => [...items, userMessage]);
    setStatus("loading");
    setError(null);
    setStream("");
    const request = new AbortController();
    controller.current = request;
    try {
      await generate(
        project ? `/projects/${project.id}/generations` : "/projects",
        { message_id: messageId, content },
        request.signal,
        (event) => {
          if (event.event === "generation") {
            const nextProjectId = event.data.project_id;
            const nextGenerationId = event.data.generation_id;
            if (typeof nextProjectId === "string" && !project)
              router.replace(`/workspace/${nextProjectId}`);
            if (typeof nextGenerationId === "string")
              setGenerationId(nextGenerationId);
          }
          if (event.event === "delta" && typeof event.data.content === "string")
            setStream((value) => value + event.data.content);
          if (event.event === "agent") appendAgentMessage(event.data);
          if (event.event === "completed") {
            const nextMessage = event.data.message as ChatMessage;
            if (nextMessage?.id)
              setMessages((items) => [...items, nextMessage]);
            if (event.data.document)
              setDocument(event.data.document as DesignDocument);
          }
          if (event.event === "failed" || event.event === "interrupted")
            setError(
              event.event === "interrupted"
                ? "生成已停止，可重新生成。"
                : "生成失败，可重新生成。",
            );
        },
      );
    } catch (reason) {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) {
        if (reason instanceof RequestError && reason.status === 401)
          router.replace("/login");
        else setError("生成失败，可重新生成。");
      }
    } finally {
      controller.current = null;
      setGenerationId(null);
      setStream("");
      setStatus((value) => (value === "loading" ? "idle" : value));
    }
  };
  sendRef.current = (content) => void send(content);
  const retry = (messageId: string) => {
    if (!project || status === "loading") return;
    const request = new AbortController();
    controller.current = request;
    setStatus("loading");
    setError(null);
    setStream("");
    void generate(
      `/projects/${project.id}/messages/${messageId}/generations`,
      undefined,
      request.signal,
      (event) => {
        if (
          event.event === "generation" &&
          typeof event.data.generation_id === "string"
        )
          setGenerationId(event.data.generation_id);
        if (event.event === "delta" && typeof event.data.content === "string")
          setStream((value) => value + event.data.content);
        if (event.event === "agent") appendAgentMessage(event.data);
        if (event.event === "completed") {
          const nextMessage = event.data.message as ChatMessage;
          if (nextMessage?.id) setMessages((items) => [...items, nextMessage]);
          if (event.data.document) setDocument(event.data.document as DesignDocument);
        }
        if (event.event === "failed" || event.event === "interrupted")
          setError("生成未完成，可重新生成。");
      },
    )
      .catch(() => setError("重新生成失败"))
      .finally(() => {
        controller.current = null;
        setGenerationId(null);
        setStream("");
        setStatus("idle");
      });
  };
  const stop = () => {
    if (project && generationId) void stopGeneration(project.id, generationId);
    controller.current?.abort();
    setStream("");
    setStatus("idle");
  };
  const visibleMessages = stream
    ? [
        ...messages,
        { id: "streaming", role: "assistant" as const, content: stream },
      ]
    : messages;
  return (
    <Workspace
      accountEmail={email}
      document={document}
      error={error}
      messages={visibleMessages}
      projectTitle={project?.title || "新建项目"}
      status={status}
      onSend={(content) => void send(content)}
      onRetry={retry}
      onStop={stop}
      onLogout={() => void logout().then(() => router.replace("/login"))}
    />
  );
};
export { WorkspaceChat };
