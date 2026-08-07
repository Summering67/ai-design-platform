"use client";

import { forwardRef, useEffect, useRef, useState } from "react";
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
  Components,
  ItemProps,
  ListProps,
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
import styles from "./workspace.module.css";

type ChatRole = "user" | "assistant";
type ChatStatus = "idle" | "loading" | "error";
type ChatMessage = { id: string; role: ChatRole; content: string };
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
  status: ChatStatus;
  error: string | null;
  onSend: (content: string) => void;
  onRetry: (messageId: string) => void;
  onStop: () => void;
  onLogout: () => void;
  canvasNode?: CanvasNode | null;
  document?: DesignDocument | null;
};

const MessageList = forwardRef<HTMLDivElement, ListProps & { context: null }>(
  ({ context, ...props }, ref) => {
    void context;
    return (
      <div
        {...props}
        ref={ref}
        aria-label="对话消息"
        className={styles.messageList}
        role="list"
      />
    );
  },
);
MessageList.displayName = "MessageList";

const MessageItem = ({
  context,
  item,
  ...props
}: ItemProps<ChatMessage> & { context: null }) => {
  void context;
  void item;
  return <div {...props} role="listitem" />;
};

const messageComponents: Components<ChatMessage, null> = {
  List: MessageList,
  Item: MessageItem,
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
  onRetry,
  onSend,
  onStop,
  status,
}: Omit<WorkspaceProps, "projectTitle" | "accountEmail" | "onLogout">) => {
  const [draft, setDraft] = useState("");
  const [isAtBottom, setIsAtBottom] = useState(true);
  const listRef = useRef<VirtuosoHandle>(null);
  const isLoading = status === "loading";
  const retryMessageId = [...messages]
    .reverse()
    .find((message) => message.role === "user")?.id;
  const submit = () => {
    const content = draft.trim();
    if (!content || isLoading) return;
    onSend(content);
    setDraft("");
  };
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
        {messages.length ? (
          <Virtuoso
            ref={listRef}
            alignToBottom
            atBottomStateChange={setIsAtBottom}
            atBottomThreshold={48}
            className={styles.chatList}
            components={messageComponents}
            computeItemKey={(_index, message) => message.id}
            data={messages}
            followOutput={(atBottom) => atBottom && "auto"}
            increaseViewportBy={{ top: 320, bottom: 240 }}
            itemContent={(_index, message) => (
              <ChatMessageItem message={message} />
            )}
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
        {!isAtBottom && messages.length ? (
          <Button
            aria-label="回到最新消息"
            className={styles.jumpToLatest}
            size="sm"
            variant="secondary"
            onClick={() =>
              listRef.current?.scrollToIndex({
                index: messages.length - 1,
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
          data-disabled={isLoading || undefined}
        >
          <InputGroupTextarea
            aria-label="发送消息"
            disabled={isLoading}
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
              disabled={!draft.trim() || isLoading}
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
  onRetry,
  onSend,
  onStop,
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
          status={status}
          onRetry={onRetry}
          onSend={onSend}
          onStop={onStop}
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
  WorkspaceProps,
};
