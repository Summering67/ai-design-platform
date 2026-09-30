"use client";

import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  SparklesIcon,
} from "lucide-react";
import { Virtuoso } from "react-virtuoso";
import {
  applyV2Operations,
  type DesignDocument,
  type DesignNode,
  type V2Operation,
} from "@repo/design-dsl";
import type { VirtuosoHandle } from "react-virtuoso";

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
import {
  ReasoningDisclosure,
  type ReasoningPresentationItem,
} from "./reasoning-disclosure";
import styles from "./workspace.module.css";

const DesignDocumentRenderer = lazy(() =>
  import("../design-document-renderer").then((module) => ({
    default: module.DesignDocumentRenderer,
  })),
);

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
type WorkspaceReasoning = ReasoningPresentationItem;
type WorkspaceStreamingMessage = { id: string; content: string };
type WorkspaceProps = {
  accountEmail: string;
  projectTitle: string;
  messages: ReadonlyArray<ChatMessage>;
  streamingMessage?: WorkspaceStreamingMessage | null;
  reasoning: ReadonlyArray<WorkspaceReasoning>;
  status: ChatStatus;
  error: string | null;
  onSend: (content: string) => void;
  onRetry: (messageId: string) => void;
  onStop: () => void;
  onAnswer?: (answers: { questionId: string; content: string }[]) => void;
  onLogout: () => void;
  inputRequest?: WorkspaceInputRequest | null;
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

const getScrollBehavior = (): "auto" | "smooth" =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ? "auto"
    : "smooth";

const ChatPanel = ({
  error,
  messages,
  streamingMessage,
  reasoning,
  onRetry,
  onSend,
  onStop,
  onAnswer,
  inputRequest,
  status,
}: Omit<WorkspaceProps, "projectTitle" | "accountEmail" | "onLogout">) => {
  const [draft, setDraft] = useState("");
  const [answers, setAnswers] = useState<Record<string, WorkspaceInputAnswer>>(
    {},
  );
  const [isAtBottom, setIsAtBottom] = useState(true);
  const listRef = useRef<VirtuosoHandle>(null);
  const isLoading = status === "loading";
  const isAwaitingInput = status === "awaiting_input" && Boolean(inputRequest);
  useEffect(() => setAnswers({}), [inputRequest?.id]);
  const retryMessageId = [...messages]
    .reverse()
    .find((message) => message.role === "user")?.id;
  const reasoningItems = reasoning
    .filter((item) => item.content.trim())
    .map((item) => ({ kind: "reasoning" as const, reasoning: item }));
  const conversation = [
    ...messages.map((message) => ({ kind: "message" as const, message })),
    ...reasoningItems,
    ...(streamingMessage
      ? [{
          kind: "message" as const,
          message: { ...streamingMessage, role: "assistant" as const },
        }]
      : []),
  ];
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
      const content =
        answer?.selected === "__other__" || !question.options?.length
          ? answer?.custom?.trim() || ""
          : answer?.selected?.trim() || "";
      return { questionId: question.id, content };
    });
    if (values.some(({ content }) => !content)) return;
    onAnswer?.(values);
  };
  const unanswered =
    inputRequest?.questions.some((question) => {
      const answer = answers[question.id];
      if (!question.options?.length || answer?.selected === "__other__")
        return !answer?.custom?.trim();
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
            computeItemKey={(_index, item) =>
              item.kind === "message"
                ? item.message.id
                : `reasoning:${item.reasoning.id}`
            }
            data={conversation}
            followOutput={(atBottom) => atBottom && "auto"}
            increaseViewportBy={{ top: 320, bottom: 240 }}
            itemContent={(_index, item) =>
              item.kind === "message" ? (
                <ChatMessageItem message={item.message} />
              ) : (
                <ReasoningDisclosure item={item.reasoning} />
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
          <section
            className={styles.inputRequestPanel}
            aria-labelledby="input-request-title"
          >
            <div className={styles.inputRequestHeading}>
              <strong id="input-request-title">需要你的确认</strong>
              <span>第 {inputRequest.round} 轮 · 回答后继续生成</span>
            </div>
            <div
              aria-label="追问列表"
              className={styles.inputRequestQuestions}
              role="group"
            >
              {inputRequest.questions.map((question) => {
                const answer = answers[question.id];
                const options = question.options || [];
                const questionText =
                  question.question || question.text || "请选择一个选项";
                return (
                  <fieldset
                    className={styles.inputRequestQuestion}
                    key={question.id}
                  >
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
                            <span className={styles.inputRequestOptionIndex}>
                              {optionIndex + 1}
                            </span>
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
                            <span className={styles.inputRequestOptionIndex}>
                              {options.length + 1}
                            </span>
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
                        onChange={(event) =>
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: {
                              ...current[question.id],
                              custom: event.target.value,
                            },
                          }))
                        }
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

const Canvas = ({
  document,
  selectedNodeId,
  onSelectedNodeIdChange,
}: {
  document: DesignDocument | null;
  selectedNodeId?: string;
  onSelectedNodeIdChange: (
    nodeId: string | undefined,
    node: DesignNode | undefined,
  ) => void;
}) => (
  <section className={styles.canvas}>
    <div className={styles.canvasMeta}>
      <span>画布</span>
      <span>{document?.name ?? "等待设计数据"}</span>
    </div>
    <div className={styles.canvasSurface}>
      {document ? (
        <Suspense
          fallback={
            <div className={styles.canvasLoading} role="status">
              <Spinner />
              正在加载画布…
            </div>
          }
        >
          <DesignDocumentRenderer
            document={document}
            selectedNodeId={selectedNodeId}
            onSelectedNodeIdChange={onSelectedNodeIdChange}
            onError={(message) => <p>{message}</p>}
          />
        </Suspense>
      ) : (
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

const PositionField = ({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
}) => {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => {
    if (draft === null) return;
    const next = Number(draft);
    if (
      draft.trim() !== "" &&
      Number.isFinite(next) &&
      (min === undefined || next >= min) &&
      (max === undefined || next <= max)
    )
      onChange(next);
    setDraft(null);
  };
  return (
    <label className={styles.numberField}>
      <span>{label}</span>
      <input
        inputMode="decimal"
        type="text"
        value={draft ?? String(value)}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) =>
          event.key === "Enter" && event.currentTarget.blur()
        }
      />
    </label>
  );
};

const SelectField = ({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: ReadonlyArray<{ label: string; value: string }>;
  onChange: (value: string) => void;
}) => (
  <label className={styles.numberField}>
    <span>{label}</span>
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  </label>
);

const findNode = (
  node: DesignNode | undefined,
  nodeId: string | undefined,
): DesignNode | undefined => {
  if (!node || !nodeId) return undefined;
  if (node.id === nodeId) return node;
  return node.children
    .map((child) => findNode(child, nodeId))
    .find((child): child is DesignNode => Boolean(child));
};

const Inspector = ({
  node,
  isRoot,
  operationError,
  onOperation,
}: {
  node: DesignNode | null;
  isRoot: boolean;
  operationError: string | null;
  onOperation: (operation: V2Operation) => void;
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
  const style = node.style as Record<string, unknown>;
  const background =
    typeof style.backgroundColor === "string" &&
    /^#[0-9a-f]{3,8}$/i.test(style.backgroundColor)
      ? style.backgroundColor
      : "#ffffff";
  const layout = node.layout?.mode === "flex" ? node.layout : undefined;
  const layoutItem = node.layoutItem ?? {};
  const patchStyle = (patches: Record<string, unknown | null>) =>
    onOperation({ type: "patch-style", nodeId: node.id, patches });
  const patchLayout = (patches: Record<string, unknown | null>) =>
    onOperation({ type: "patch-layout", nodeId: node.id, patches });
  const patchLayoutItem = (patches: Record<string, unknown | null>) =>
    onOperation({ type: "patch-layout-item", nodeId: node.id, patches });
  const isAbsolute = layoutItem.position === "absolute";
  const horizontalAnchor =
    layoutItem.inset?.left !== undefined ||
    layoutItem.inset?.right === undefined
      ? "left"
      : "right";
  const verticalAnchor =
    layoutItem.inset?.top !== undefined ||
    layoutItem.inset?.bottom === undefined
      ? "top"
      : "bottom";
  const opposite = {
    left: "right",
    right: "left",
    top: "bottom",
    bottom: "top",
  } as const;
  const maxInsetPosition = (side: "left" | "right" | "top" | "bottom") => {
    const other = layoutItem.inset?.[opposite[side]];
    return other === undefined
      ? undefined
      : (layoutItem.inset?.[side] ?? 0) + other;
  };
  const patchPosition = (
    side: "left" | "right" | "top" | "bottom",
    value: number,
  ) => {
    if (!isAbsolute) {
      patchLayoutItem({
        offset: { ...layoutItem.offset, [side === "left" ? "x" : "y"]: value },
      });
      return;
    }
    const inset = { ...layoutItem.inset, [side]: value };
    const other = opposite[side];
    if (layoutItem.inset?.[other] !== undefined)
      inset[other] =
        layoutItem.inset[other] + (layoutItem.inset[side] ?? 0) - value;
    patchLayoutItem({ inset });
  };
  const sizingMode = (axis: "width" | "height") =>
    layoutItem[axis]?.mode ?? "hug";
  const sizingValue = (axis: "width" | "height") =>
    layoutItem[axis]?.mode === "fixed" ? layoutItem[axis].value : 0;
  const updateSizing = (axis: "width" | "height", mode: string) => {
    if (mode === "fixed")
      patchLayoutItem({ [axis]: { mode: "fixed", value: 160 } });
    if (mode === "fill" || mode === "hug")
      patchLayoutItem({ [axis]: { mode } });
  };
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
        {operationError ? (
          <p className={styles.inspectorError} role="alert">
            {operationError}
          </p>
        ) : null}
        {node.kind === "text" ? (
          <section className={styles.propertyGroup}>
            <div className={styles.propertyHeading}>
              <span>文本</span>
              <span>CONTENT</span>
            </div>
            <textarea
              aria-label="文本内容"
              value={node.text}
              onChange={(event) =>
                onOperation({
                  type: "set-text",
                  nodeId: node.id,
                  text: event.target.value,
                })
              }
            />
          </section>
        ) : null}
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>填充颜色</span>
            <span>100%</span>
          </div>
          <label className={styles.colorField}>
            <input
              aria-label="填充颜色"
              type="color"
              value={background}
              onChange={(event) =>
                patchStyle({ backgroundColor: event.target.value })
              }
            />
            <input
              aria-label="填充颜色值"
              value={background.toUpperCase()}
              onChange={(event) =>
                patchStyle({ backgroundColor: event.target.value })
              }
            />
          </label>
        </section>
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>尺寸</span>
            <span>PX</span>
          </div>
          <div className={styles.fieldGrid}>
            {(["width", "height"] as const).map((axis) => (
              <div key={axis}>
                <SelectField
                  label={axis === "width" ? "宽度模式" : "高度模式"}
                  value={sizingMode(axis)}
                  options={[
                    { label: "自适应", value: "hug" },
                    { label: "填充", value: "fill" },
                    { label: "固定", value: "fixed" },
                  ]}
                  onChange={(value) => updateSizing(axis, value)}
                />
                {sizingMode(axis) === "fixed" ? (
                  <NumberField
                    label="固定值"
                    value={sizingValue(axis)}
                    onChange={(value) =>
                      patchLayoutItem({ [axis]: { mode: "fixed", value } })
                    }
                  />
                ) : null}
              </div>
            ))}
          </div>
        </section>
        {!isRoot ? (
          <section className={styles.propertyGroup}>
            <div className={styles.propertyHeading}>
              <span>{isAbsolute ? "绝对位置" : "位置偏移"}</span>
              <span>PX</span>
            </div>
            <div className={styles.fieldGrid}>
              <PositionField
                key={`${node.id}:x`}
                label={
                  isAbsolute
                    ? horizontalAnchor === "left"
                      ? "左侧距离"
                      : "右侧距离"
                    : "X"
                }
                value={
                  isAbsolute
                    ? (layoutItem.inset?.[horizontalAnchor] ?? 0)
                    : (layoutItem.offset?.x ?? 0)
                }
                min={isAbsolute ? 0 : undefined}
                max={
                  isAbsolute ? maxInsetPosition(horizontalAnchor) : undefined
                }
                onChange={(value) => patchPosition(horizontalAnchor, value)}
              />
              <PositionField
                key={`${node.id}:y`}
                label={
                  isAbsolute
                    ? verticalAnchor === "top"
                      ? "顶部距离"
                      : "底部距离"
                    : "Y"
                }
                value={
                  isAbsolute
                    ? (layoutItem.inset?.[verticalAnchor] ?? 0)
                    : (layoutItem.offset?.y ?? 0)
                }
                min={isAbsolute ? 0 : undefined}
                max={isAbsolute ? maxInsetPosition(verticalAnchor) : undefined}
                onChange={(value) => patchPosition(verticalAnchor, value)}
              />
            </div>
          </section>
        ) : null}
        <section className={styles.propertyGroup}>
          <div className={styles.propertyHeading}>
            <span>圆角与文字</span>
            <span>PX</span>
          </div>
          <div className={styles.fieldGrid}>
            <NumberField
              label="圆角"
              value={
                typeof style.borderRadius === "number" ? style.borderRadius : 0
              }
              onChange={(value) => patchStyle({ borderRadius: value })}
            />
            {node.kind === "text" ? (
              <NumberField
                label="字号"
                value={typeof style.fontSize === "number" ? style.fontSize : 16}
                onChange={(value) => patchStyle({ fontSize: value })}
              />
            ) : null}
          </div>
        </section>
        {layout ? (
          <section className={styles.propertyGroup}>
            <div className={styles.propertyHeading}>
              <span>Flex 布局</span>
              <span>LAYOUT</span>
            </div>
            <div className={styles.fieldGrid}>
              <SelectField
                label="方向"
                value={layout.direction ?? "column"}
                options={[
                  { label: "横向", value: "row" },
                  { label: "纵向", value: "column" },
                ]}
                onChange={(value) => patchLayout({ direction: value })}
              />
              <SelectField
                label="换行"
                value={layout.wrap ?? "nowrap"}
                options={[
                  { label: "不换行", value: "nowrap" },
                  { label: "换行", value: "wrap" },
                ]}
                onChange={(value) => patchLayout({ wrap: value })}
              />
            </div>
            <div className={styles.fieldGrid}>
              <NumberField
                label="间距"
                value={layout.gap ?? 0}
                onChange={(value) => patchLayout({ gap: value })}
              />
              <NumberField
                label="内边距"
                value={layout.padding?.top ?? 0}
                onChange={(value) =>
                  patchLayout({
                    padding: {
                      top: value,
                      right: value,
                      bottom: value,
                      left: value,
                    },
                  })
                }
              />
            </div>
          </section>
        ) : null}
      </div>
    </aside>
  );
};

const Workspace = ({
  document,
  error,
  messages,
  streamingMessage,
  reasoning,
  onRetry,
  onSend,
  onStop,
  onAnswer,
  inputRequest,
  status,
}: WorkspaceProps) => {
  const [editableDocument, setEditableDocument] =
    useState<DesignDocument | null>(document ?? null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [operationError, setOperationError] = useState<string | null>(null);
  useEffect(() => {
    setEditableDocument(document ?? null);
    setSelectedNodeId(undefined);
    setOperationError(null);
  }, [document]);
  const selectedNode = findNode(editableDocument?.root, selectedNodeId);
  const applyOperation = (operation: V2Operation) => {
    if (!editableDocument) return;
    const result = applyV2Operations(editableDocument, [operation]);
    if (!result.ok) {
      setOperationError(
        `配置更新失败：${result.errors.map((item) => item.message).join("；") || "未知原因"}`,
      );
      return;
    }
    setEditableDocument(result.value);
    setOperationError(null);
  };
  return (
    <main className={styles.workspace}>
      <div className={styles.workspaceBody}>
        <ChatPanel
          error={error}
          messages={messages}
          streamingMessage={streamingMessage}
          reasoning={reasoning}
          status={status}
          onRetry={onRetry}
          onSend={onSend}
          onStop={onStop}
          onAnswer={onAnswer}
          inputRequest={inputRequest}
        />
        <Canvas
          document={editableDocument}
          selectedNodeId={selectedNodeId}
          onSelectedNodeIdChange={(nodeId) => {
            setSelectedNodeId(nodeId);
            setOperationError(null);
          }}
        />
        <Inspector
          node={selectedNode ?? null}
          isRoot={selectedNodeId === editableDocument?.root.id}
          operationError={operationError}
          onOperation={applyOperation}
        />
      </div>
    </main>
  );
};

const WorkspaceFallback = () => <main className={styles.fallback} />;

export { Workspace, WorkspaceFallback };
export type {
  ChatMessage,
  ChatRole,
  ChatStatus,
  WorkspaceStreamingMessage,
  WorkspaceReasoning,
  WorkspaceProps,
  WorkspaceInputQuestion,
  WorkspaceInputQuestionOption,
  WorkspaceInputRequest,
};
