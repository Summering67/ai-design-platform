"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  SparklesIcon,
} from "lucide-react";
import { Virtuoso } from "react-virtuoso";
import { DesignDocumentRenderer } from "../design-document-renderer";
import type { DesignDocument } from "@repo/design-dsl";
import type {
  VirtuosoHandle,
} from "react-virtuoso";

import { Button } from "../../components/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "../../components/empty";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "../../components/input-group";
import { Spinner } from "../../components/spinner";
import { ToggleGroup, ToggleGroupItem } from "../../components/toggle-group";
import styles from "./workspace.module.css";

type ChatRole = "user" | "assistant";
type ChatStatus = "idle" | "loading" | "awaiting_input" | "error";
type ChatMessage = { id: string; role: ChatRole; content: string };
type WorkspaceInputQuestionOption = { label: string; description: string };
type WorkspaceInputQuestion = {
  id: string;
  header?: string;
  question?: string;
  isOther?: boolean;
  options?: ReadonlyArray<WorkspaceInputQuestionOption>;
  text?: string;
};
type WorkspaceInputAnswer = { selected?: string; custom?: string };
type WorkspaceInputRequest = {
  id: string;
  generationId: string;
  round: number;
  questions: ReadonlyArray<WorkspaceInputQuestion>;
};
type WorkspaceReasoning = {
  id: string;
  stage: string;
  taskId: string;
  attempt: number;
  content: string;
  status: "reasoning" | "completed" | "truncated";
};
type CanvasSettings = {
  background: string;
  width: number;
  height: number;
  x: number;
  y: number;
  radius: number;
};
type CanvasNode = {
  id: string;
  name: string;
  settings: CanvasSettings;
};
type WorkspaceProps = {
  accountEmail: string;
  projectTitle: string;
  messages: ReadonlyArray<ChatMessage>;
  reasoning: ReadonlyArray<WorkspaceReasoning>;
  status: ChatStatus;
  error: string | null;
  onSend: (content: string) => void;
  onRetry: (messageId: string) => void;
  onStop: () => void;
  onAnswer?: (answers: { questionId: string; content: string }[]) => void;
  onLogout: () => void;
  inputRequest?: WorkspaceInputRequest | null;
  canvasNode?: CanvasNode | null;
  document?: DesignDocument | null;
};

const ChatMessageItem = ({ message }: { message: ChatMessage }) => (
  <article className={styles.message} data-role={message.role}>
    {message.role === "assistant" ? (
      <div className={styles.assistantLabel}>
        <SparklesIcon />
        <span>设计助手</span>
      </div>
    ) : null}
    <p className={styles.messageContent}>{message.content}</p>
  </article>
);

const ReasoningMessageItem = ({ item }: { item: WorkspaceReasoning }) => (
  <article className={`${styles.message} ${styles.reasoningMessage}`} data-role="assistant">
    <div className={styles.assistantLabel}>
      <SparklesIcon />
      <span>设计助手 · 模型思考（无需回复）</span>
    </div>
    <details>
      <p className={styles.messageContent}>{item.content}</p>
    </details>
  </article>
);

const getScrollBehavior = (): "auto" | "smooth" =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ? "auto"
    : "smooth";

const ChatPanel = ({
  error,
  messages,
  reasoning,
  onRetry,
  onSend,
  onStop,
  onAnswer,
  inputRequest,
  status,
}: Omit<WorkspaceProps, "projectTitle" | "accountEmail" | "onLogout">) => {
  const [draft, setDraft] = useState("");
  const [answers, setAnswers] = useState<Record<string, WorkspaceInputAnswer>>({});
  const [isAtBottom, setIsAtBottom] = useState(true);
  const listRef = useRef<VirtuosoHandle>(null);
  const isLoading = status === "loading";
  const isAwaitingInput = status === "awaiting_input" && Boolean(inputRequest);
  useEffect(() => setAnswers({}), [inputRequest?.id]);
  const retryMessageId = [...messages]
    .reverse()
    .find((message) => message.role === "user")?.id;
  const reasoningItems = reasoning
    .filter((item) => item.status === "completed")
    .map((item) => ({ kind: "reasoning" as const, reasoning: item }));
  const conversation = messages.flatMap((message) =>
    message.id === "streaming"
      ? [...reasoningItems, { kind: "message" as const, message }]
      : [{ kind: "message" as const, message }],
  );
  if (!messages.some((message) => message.id === "streaming"))
    conversation.push(...reasoningItems);
  const submit = () => {
    const content = draft.trim();
    if (!content || isLoading) return;
    onSend(content);
    setDraft("");
  };
  const submitAnswers = () => {
    if (!inputRequest) return;
    const values = inputRequest.questions.map((question) => {
      const answer = answers[question.id];
      const content = answer?.selected === "__other__" || !question.options?.length
        ? answer?.custom?.trim() || ""
        : answer?.selected?.trim() || "";
      return { questionId: question.id, content };
    });
    if (values.some(({ content }) => !content)) return;
    onAnswer?.(values);
  };
  const unanswered = inputRequest?.questions.some((question) => {
    const answer = answers[question.id];
    if (!question.options?.length || answer?.selected === "__other__") return !answer?.custom?.trim();
    return !answer?.selected;
  }) ?? true;
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submit();
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key !== "Enter" ||
      event.shiftKey ||
      event.nativeEvent.isComposing
    )
      return;
    event.preventDefault();
    submit();
  };

  return (
    <aside className={styles.chatPanel}>
      <header className={styles.panelHeader}>
        <span className={styles.brandMark}>
          <SparklesIcon />
        </span>
        <div>
          <strong>AI 设计助手</strong>
        </div>
      </header>
      <div className={styles.conversation}>
        {conversation.length ? (
          <Virtuoso
            ref={listRef}
            alignToBottom
            atBottomStateChange={setIsAtBottom}
            atBottomThreshold={48}
            className={styles.chatList}
            computeItemKey={(_index, item) => item.kind === "message" ? item.message.id : `reasoning:${item.reasoning.id}`}
            data={conversation}
            followOutput={(atBottom) => atBottom && "auto"}
            increaseViewportBy={{ top: 320, bottom: 240 }}
            itemContent={(_index, item) =>
              item.kind === "message" ? (
                <ChatMessageItem message={item.message} />
              ) : (
                <ReasoningMessageItem item={item.reasoning} />
              )
            }
          />
        ) : (
          <Empty className={styles.emptyFill}>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <SparklesIcon />
              </EmptyMedia>
              <EmptyTitle>从一句描述开始</EmptyTitle>
              <EmptyDescription>
                告诉我你想创作的界面，我会协助你将想法放到画布上。
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        {!isAtBottom && conversation.length ? (
          <Button
            aria-label="回到最新消息"
            className={styles.jumpToLatest}
            size="sm"
            variant="secondary"
            onClick={() =>
              listRef.current?.scrollToIndex({
                index: conversation.length - 1,
                align: "end",
                behavior: getScrollBehavior(),
              })
            }
          >
            <ArrowDownIcon data-icon="inline-start" />
            最新消息
          </Button>
        ) : null}
      </div>
      <div aria-atomic="true" aria-live="polite" className={styles.chatStatus}>
        {isLoading ? (
          <p className={styles.loadingStatus}>
            <Spinner className={styles.statusSpinner} />
            AI 正在整理设计方案
            <Button size="sm" variant="outline" onClick={onStop}>
              停止
            </Button>
          </p>
        ) : null}
        {isAwaitingInput && inputRequest ? (
          <section className={styles.inputRequestPanel} aria-labelledby="input-request-title">
            <div className={styles.inputRequestHeading}>
              <strong id="input-request-title">需要你的确认</strong>
              <span>第 {inputRequest.round} 轮 · 回答后继续生成</span>
            </div>
            <div aria-label="追问列表" className={styles.inputRequestQuestions} role="group">
              {inputRequest.questions.map((question) => {
                const answer = answers[question.id];
                const options = question.options || [];
                const questionText = question.question || question.text || "请选择一个选项";
                return (
                  <fieldset className={styles.inputRequestQuestion} key={question.id}>
                    <legend>{question.header || "需要确认"}</legend>
                    <p>{questionText}</p>
                    {options.length ? (
                      <ToggleGroup
                        aria-label={questionText}
                        className={styles.inputRequestOptions}
                        disabled={status !== "awaiting_input"}
                        onValueChange={(values) => {
                          const selected = values[0];
                          if (!selected) return;
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: { selected },
                          }));
                        }}
                        orientation="vertical"
                        value={answer?.selected ? [answer.selected] : []}
                        variant="outline"
                      >
                        {options.map((option, optionIndex) => (
                          <ToggleGroupItem
                            className={styles.inputRequestOption}
                            key={option.label}
                            value={option.label}
                          >
                            <span className={styles.inputRequestOptionIndex}>{optionIndex + 1}</span>
                            <span className={styles.inputRequestOptionContent}>
                              <strong>{option.label}</strong>
                              <small>{option.description}</small>
                            </span>
                          </ToggleGroupItem>
                        ))}
                        {question.isOther ? (
                          <ToggleGroupItem
                            className={styles.inputRequestOption}
                            value="__other__"
                          >
                            <span className={styles.inputRequestOptionIndex}>{options.length + 1}</span>
                            <span className={styles.inputRequestOptionContent}>
                              <strong>其他</strong>
                              <small>输入更符合你的答案</small>
                            </span>
                          </ToggleGroupItem>
                        ) : null}
                      </ToggleGroup>
                    ) : null}
                    {!options.length || answer?.selected === "__other__" ? (
                      <textarea
                        aria-label={`${questionText}的自定义回答`}
                        disabled={status !== "awaiting_input"}
                        placeholder="请输入你的回答"
                        value={answer?.custom || ""}
                        onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: { ...current[question.id], custom: event.target.value } }))}
                      />
                    ) : null}
                  </fieldset>
                );
              })}
            </div>
            <Button
              className={styles.inputRequestSubmit}
              disabled={unanswered}
              onClick={submitAnswers}
              size="sm"
              type="button"
            >
              提交回答并继续
            </Button>
          </section>
        ) : null}
        {status === "error" && error ? (
          <div className={styles.errorStatus} role="alert">
            <p>{error}</p>
            {retryMessageId ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onRetry(retryMessageId)}
              >
                重新生成
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
      <form className={styles.composer} onSubmit={handleSubmit}>
        <InputGroup
          className={styles.composerGroup}
          data-disabled={isLoading || isAwaitingInput || undefined}
        >
          <InputGroupTextarea
            aria-label="发送消息"
            disabled={isLoading || isAwaitingInput}
            placeholder={
              isLoading ? "等待 AI 回复..." : "例如：把卡片移动到页面底部"
            }
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <InputGroupAddon align="block-end" className={styles.composerActions}>
            <span className={styles.composerHint}>Enter 发送</span>
            <InputGroupButton
              aria-label="发送消息"
              disabled={!draft.trim() || isLoading || isAwaitingInput}
              size="icon-sm"
              type="submit"
              variant="default"
            >
              <ArrowUpIcon />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </form>
    </aside>
  );
};

const Canvas = ({ document, node }: { document?: DesignDocument | null; node: CanvasNode | null }) => (
  <section className={styles.canvas}>
    <div className={styles.canvasMeta}>
      <span>画布</span>
      <span>{node ? node.name : "等待设计数据"}</span>
    </div>
    <div className={styles.canvasSurface}>
      {document ? (
        <DesignDocumentRenderer document={document} onError={(message) => <p>{message}</p>} />
      ) : !node ? (
        <Empty className={styles.canvasEmpty}>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SparklesIcon />
            </EmptyMedia>
            <EmptyTitle>画布等待生成</EmptyTitle>
            <EmptyDescription>
              发送需求后，生成的设计节点会显示在这里。
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div
          className={styles.canvasNode}
          aria-label={node.name}
          style={{
            backgroundColor: node.settings.background,
            width: `${node.settings.width}px`,
            height: `${node.settings.height}px`,
            transform: `translate(${node.settings.x}px, ${node.settings.y}px)`,
            borderRadius: `${node.settings.radius}px`,
          }}
        />
      )}
    </div>
  </section>
);

const NumberField = ({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) => (
  <label className={styles.numberField}>
    <span>{label}</span>
    <input
      inputMode="numeric"
      min="0"
      type="number"
      value={value}
      onChange={(event) => onChange(Number(event.target.value) || 0)}
    />
  </label>
);

const Inspector = ({
  node,
  setNode,
}: {
  node: CanvasNode | null;
  setNode: (node: CanvasNode) => void;
}) => {
  if (!node)
    return (
      <aside className={styles.inspector}>
        <header className={styles.panelHeader}>
          <div>
            <strong>配置</strong>
            <span>未选择图层</span>
          </div>
        </header>
        <Empty className={styles.inspectorEmpty}>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SparklesIcon />
            </EmptyMedia>
            <EmptyTitle>暂无可配置对象</EmptyTitle>
            <EmptyDescription>
              画布生成后，选择图层即可调整属性。
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </aside>
    );
  const { settings } = node;
  const update = <Key extends keyof CanvasSettings>(
    key: Key,
    value: CanvasSettings[Key],
  ) => setNode({ ...node, settings: { ...settings, [key]: value } });
  return (
    <aside className={styles.inspector}>
      <header className={styles.panelHeader}>
        <div>
          <strong>配置</strong>
          <span>已选中 · {node.name}</span>
        </div>
        <ChevronDownIcon />
      </header>
      <div className={styles.inspectorContent}>
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>填充颜色</span>
            <span>100%</span>
          </div>
          <label className={styles.colorField}>
            <input
              aria-label="填充颜色"
              type="color"
              value={settings.background}
              onChange={(event) => update("background", event.target.value)}
            />
            <input
              aria-label="填充颜色值"
              value={settings.background.toUpperCase()}
              onChange={(event) => update("background", event.target.value)}
            />
          </label>
        </section>
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>尺寸</span>
            <span>PX</span>
          </div>
          <div className={styles.fieldGrid}>
            <NumberField
              label="宽度"
              value={settings.width}
              onChange={(value) => update("width", value)}
            />
            <NumberField
              label="高度"
              value={settings.height}
              onChange={(value) => update("height", value)}
            />
          </div>
        </section>
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>位置</span>
            <span>PX</span>
          </div>
          <div className={styles.fieldGrid}>
            <NumberField
              label="X"
              value={settings.x}
              onChange={(value) => update("x", value)}
            />
            <NumberField
              label="Y"
              value={settings.y}
              onChange={(value) => update("y", value)}
            />
          </div>
        </section>
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>圆角</span>
            <span>PX</span>
          </div>
          <NumberField
            label="半径"
            value={settings.radius}
            onChange={(value) => update("radius", value)}
          />
        </section>
      </div>
    </aside>
  );
};

const Workspace = ({
  canvasNode,
  document,
  error,
  messages,
  reasoning,
  onRetry,
  onSend,
  onStop,
  onAnswer,
  inputRequest,
  status,
}: WorkspaceProps) => {
  const [selectedNode, setSelectedNode] = useState<CanvasNode | null>(
    canvasNode ?? null,
  );
  useEffect(() => setSelectedNode(canvasNode ?? null), [canvasNode]);
  return (
    <main className={styles.workspace}>
      <div className={styles.workspaceBody}>
        <ChatPanel
          error={error}
          messages={messages}
          reasoning={reasoning}
          status={status}
          onRetry={onRetry}
          onSend={onSend}
          onStop={onStop}
          onAnswer={onAnswer}
          inputRequest={inputRequest}
        />
        <Canvas document={document} node={selectedNode} />
        <Inspector node={selectedNode} setNode={setSelectedNode} />
      </div>
    </main>
  );
};

const WorkspaceFallback = () => <main className={styles.fallback} />;

export { Workspace, WorkspaceFallback };
export type {
  CanvasNode,
  CanvasSettings,
  ChatMessage,
  ChatRole,
  ChatStatus,
  WorkspaceReasoning,
  WorkspaceProps,
  WorkspaceInputQuestion,
  WorkspaceInputQuestionOption,
  WorkspaceInputRequest,
};
