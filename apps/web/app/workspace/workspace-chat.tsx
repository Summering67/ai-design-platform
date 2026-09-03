"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Workspace } from "@repo/ui/blocks/workspace";
import {
  validateDesignDocument,
  type DesignDocument,
} from "@repo/design-dsl";
import ecommerceHomepage from "./ecommerce-homepage.document.json";
import {
  RequestError,
  answerInput,
  currentUser,
  generate,
  loadProject,
  logout,
  stopGeneration,
} from "./chat-api";
import type { ChatMessage, PendingInputRequest, Project } from "./chat-api";
import { applyReasoningEvent } from "./reasoning";
import type { ReasoningItem } from "./reasoning";
import { createFrameBuffer } from "./stream-buffer";
import { settleGenerationStatus } from "./workspace-status";
import type { WorkspaceStatus } from "./workspace-status";

const initialDocumentResult = validateDesignDocument(ecommerceHomepage);
const initialDocument = initialDocumentResult.ok
  ? initialDocumentResult.value
  : null;

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
  const reasoningBuffer = useRef<ReturnType<typeof createFrameBuffer<Record<string, unknown>>> | null>(null);
  const streamBuffer = useRef<ReturnType<typeof createFrameBuffer<string>> | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<WorkspaceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [inputRequest, setInputRequest] = useState<PendingInputRequest | null>(null);
  const [stream, setStream] = useState("");
  const [reasoning, setReasoning] = useState<ReasoningItem[]>([]);
  const [document, setDocument] = useState<DesignDocument | null>(initialDocument);
  const [email, setEmail] = useState("");
  if (reasoningBuffer.current === null)
    reasoningBuffer.current = createFrameBuffer((values) => {
      setReasoning((items) => values.reduce(applyReasoningEvent, items));
    });
  if (streamBuffer.current === null)
    streamBuffer.current = createFrameBuffer((values) => {
      setStream((value) => value + values.join(""));
    });
  const queueReasoning = (data: Record<string, unknown>) => reasoningBuffer.current?.enqueue(data);
  const queueStream = (content: string) => streamBuffer.current?.enqueue(content);
  const clearReasoning = () => {
    reasoningBuffer.current?.discard();
    setReasoning([]);
  };
  const clearStream = () => {
    streamBuffer.current?.discard();
    setStream("");
  };
  const appendAgentMessage = (data: Record<string, unknown>) => {
    const payload = data.payload;
    const payloadStatus = payload && typeof payload === "object"
      ? (payload as Record<string, unknown>).status
      : undefined;
    if (
      data.event === "progress" &&
      (payloadStatus === "reasoning" ||
        payloadStatus === "reasoning_truncated" ||
        payloadStatus === "reasoning_completed" ||
        payloadStatus === "completed")
    )
      queueReasoning(data);
  };
  const handleGenerationEvent = (event: { event: string; data: Record<string, unknown> }) => {
    if (event.event === "generation") {
      const nextProjectId = event.data.project_id;
      const nextGenerationId = event.data.generation_id;
      if (typeof nextProjectId === "string" && !project)
        setProject({ id: nextProjectId, title: "新建项目" });
      if (typeof nextGenerationId === "string") setGenerationId(nextGenerationId);
    }
    if (event.event === "agent") appendAgentMessage(event.data);
    if (event.event === "input_required") {
      clearReasoning();
      clearStream();
      setInputRequest(event.data as unknown as PendingInputRequest);
      if (typeof event.data.generation_id === "string") setGenerationId(event.data.generation_id);
      setStatus("awaiting_input");
    }
    if (event.event === "completed") {
      reasoningBuffer.current?.flush();
      streamBuffer.current?.discard();
      const nextMessage = event.data.message as ChatMessage;
      if (nextMessage?.id) setMessages((items) => [...items, nextMessage]);
      if (event.data.document) setDocument(event.data.document as DesignDocument);
      setInputRequest(null);
      setGenerationId(null);
    }
    if (event.event === "failed" || event.event === "interrupted") {
      clearReasoning();
      clearStream();
      setInputRequest(null);
      setGenerationId(null);
      setError(event.event === "interrupted" ? "生成已停止，可重新生成。" : "生成失败，可重新生成。");
      setStatus("error");
    }
  };
  useEffect(() => () => {
    reasoningBuffer.current?.dispose();
    streamBuffer.current?.dispose();
  }, []);
  useEffect(() => {
    void currentUser()
      .then((user) => setEmail(user.email))
      .catch(() => router.replace("/login"));
  }, [router]);
  useEffect(() => {
    if (!projectId) return;
    void loadProject(projectId)
      .then(({ project: nextProject, messages: nextMessages, pending_input_request }) => {
        setProject(nextProject);
        setMessages(nextMessages);
        if (pending_input_request) {
          setInputRequest(pending_input_request);
          setGenerationId(pending_input_request.generation_id);
          setStatus("awaiting_input");
        }
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
    if (status === "loading" || status === "awaiting_input") return;
    const messageId = crypto.randomUUID();
    const userMessage = { id: messageId, role: "user" as const, content };
    setMessages((items) => [...items, userMessage]);
    setStatus("loading");
    setError(null);
    clearStream();
    setInputRequest(null);
    clearReasoning();
    const request = new AbortController();
    controller.current = request;
    try {
      await generate(
        project ? `/projects/${project.id}/generations` : "/projects",
        { message_id: messageId, content },
        request.signal,
        (event) => {
          handleGenerationEvent(event);
          if (event.event === "delta" && typeof event.data.content === "string")
            queueStream(event.data.content);
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
      clearStream();
      setStatus(settleGenerationStatus);
      // 首次生成后保留当前工作台，避免路由切换中断 SSE。
    }
  };
  const answer = (answers: { questionId: string; content: string }[]) => {
    if (!project || !generationId || !inputRequest || status === "loading") return;
    const request = new AbortController();
    controller.current = request;
    setStatus("loading");
    setError(null);
    clearReasoning();
    clearStream();
    void answerInput(
      project.id,
      generationId,
      inputRequest.id,
      {
        response_id: crypto.randomUUID(),
        answers: answers.map(({ questionId, content }) => ({ question_id: questionId, content })),
      },
      request.signal,
      (event) => {
        handleGenerationEvent(event);
        if (event.event === "delta" && typeof event.data.content === "string")
          queueStream(event.data.content);
      },
    ).catch(() => setError("提交回答失败，可重试。"))
      .finally(() => {
        controller.current = null;
        clearStream();
        setStatus(settleGenerationStatus);
      });
  };
  sendRef.current = (content) => void send(content);
  const retry = async (messageId: string) => {
    const currentProject = project;
    if (!currentProject || status === "loading" || status === "awaiting_input") return;
    const request = new AbortController();
    controller.current = request;
    setStatus("loading");
    setError(null);
    clearStream();
    setInputRequest(null);
    clearReasoning();
    const restorePendingInput = async () => {
      const { pending_input_request } = await loadProject(currentProject.id);
      if (!pending_input_request) return false;
      setInputRequest(pending_input_request);
      setGenerationId(pending_input_request.generation_id);
      setError(null);
      setStatus("awaiting_input");
      return true;
    };
    try {
      if (await restorePendingInput()) return;
      await generate(
        `/projects/${currentProject.id}/messages/${messageId}/generations`,
        undefined,
        request.signal,
        (event) => {
          handleGenerationEvent(event);
          if (event.event === "delta" && typeof event.data.content === "string")
            queueStream(event.data.content);
        },
      );
    } catch (reason: unknown) {
      try {
        if (reason instanceof RequestError && reason.status === 409) {
          if (await restorePendingInput()) return;
        }
      } catch {
        // 统一进入下方错误状态。
      }
      setError("重新生成失败");
      setStatus("error");
    } finally {
      controller.current = null;
      clearStream();
      setStatus(settleGenerationStatus);
    }
  };
  const stop = () => {
    if (project && generationId) void stopGeneration(project.id, generationId);
    controller.current?.abort();
    clearStream();
    clearReasoning();
    setInputRequest(null);
    setGenerationId(null);
    setStatus("idle");
  };
  return (
      <Workspace
      accountEmail={email}
      document={document}
      error={error}
      messages={messages}
      streamingMessage={stream ? { id: "streaming-assistant", content: stream } : null}
      reasoning={reasoning}
      inputRequest={inputRequest ? {
        id: inputRequest.id,
        generationId: inputRequest.generation_id,
        round: inputRequest.round,
        questions: inputRequest.questions,
      } : null}
      projectTitle={project?.title || "新建项目"}
      status={status}
      onSend={(content) => void send(content)}
      onRetry={retry}
      onStop={stop}
      onAnswer={answer}
      onLogout={() => void logout().then(() => router.replace("/login"))}
    />
  );
};
export { WorkspaceChat };
