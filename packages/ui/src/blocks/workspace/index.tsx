"use client";

import { forwardRef, useRef, useState, useSyncExternalStore } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleDashedIcon,
  CircleUserRoundIcon,
  Code2Icon,
  DatabaseIcon,
  FilePlus2Icon,
  FilesIcon,
  FolderPlusIcon,
  FolderTreeIcon,
  Globe2Icon,
  HomeIcon,
  LayoutTemplateIcon,
  LibraryIcon,
  MoreHorizontalIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PanelsTopLeftIcon,
  RefreshCwIcon,
  SearchIcon,
  SendIcon,
  ShapesIcon,
  SparklesIcon,
  StarIcon,
  UploadIcon,
} from "lucide-react";
import { Virtuoso } from "react-virtuoso";
import type {
  Components,
  ItemProps,
  ListProps,
  VirtuosoHandle,
} from "react-virtuoso";

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "../../components/empty";
import { Button } from "../../components/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "../../components/input-group";
import { Separator } from "../../components/separator";
import { Spinner } from "../../components/spinner";
import { ToggleGroup, ToggleGroupItem } from "../../components/toggle-group";
import styles from "./workspace.module.css";

const navItems: ReadonlyArray<{ label: string; icon: LucideIcon }> = [
  { label: "搜索", icon: SearchIcon },
  { label: "首页", icon: HomeIcon },
  { label: "项目", icon: PanelsTopLeftIcon },
  { label: "库", icon: LibraryIcon },
  { label: "设计系统", icon: ShapesIcon },
  { label: "模板", icon: LayoutTemplateIcon },
];

const modes = [
  { value: "预览", label: "预览", icon: PanelsTopLeftIcon },
  { value: "发送", label: "发送", icon: SendIcon },
  { value: "代码", label: "代码", icon: Code2Icon },
  { value: "数据", label: "数据", icon: DatabaseIcon },
] as const;

type Mode = (typeof modes)[number]["value"];

type ChatRole = "user" | "assistant";
type ChatStatus = "idle" | "loading" | "error";
type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
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
};

const compactNavigationQuery = "(max-width: 90.625rem)";
const subscribeCompactNavigation = (onStoreChange: () => void) => {
  const mediaQuery = window.matchMedia(compactNavigationQuery);
  mediaQuery.addEventListener("change", onStoreChange);
  return () => mediaQuery.removeEventListener("change", onStoreChange);
};
const getCompactNavigationSnapshot = () =>
  window.matchMedia(compactNavigationQuery).matches;
const getServerCompactNavigationSnapshot = () => false;

const ProjectNavigation = ({
  accountEmail,
  onCollapse,
  onLogout,
  title,
}: {
  accountEmail: string;
  onCollapse: () => void;
  onLogout: () => void;
  title: string;
}) => {
  return (
    <aside id="project-navigation" className={styles.navigation}>
      <header className={styles.header}>
        <span className={styles.brand}>
          <SparklesIcon />
        </span>
        <strong>我的项目</strong>
        <ChevronDownIcon className="text-muted-foreground" />
        <Button
          aria-controls="project-navigation"
          aria-expanded
          aria-label="收起侧边栏"
          size="icon"
          variant="ghost"
          onClick={onCollapse}
        >
          <PanelLeftCloseIcon />
        </Button>
      </header>
      <Separator />

      <Button
        className="mt-1 w-full justify-between"
        size="lg"
        variant="outline"
      >
        <span>新建聊天</span>
        <ChevronDownIcon data-icon="inline-end" />
      </Button>

      <nav className={styles.menu}>
        {navItems.map(({ icon: Icon, label }) => (
          <Button
            key={label}
            className="w-full justify-start"
            size="lg"
            variant="ghost"
          >
            <Icon data-icon="inline-start" />
            {label}
          </Button>
        ))}
      </nav>

      <section className={styles.chatSections}>
        <Button className="w-full justify-between" variant="ghost">
          <span>收藏</span>
          <ChevronRightIcon data-icon="inline-end" />
        </Button>
        <Button className="w-full justify-between" variant="ghost">
          <span>最近聊天</span>
          <ChevronDownIcon data-icon="inline-end" />
        </Button>
        <Button className={styles.currentChat} variant="secondary">
          <CircleDashedIcon data-icon="inline-start" />
          <span>{title}</span>
          <MoreHorizontalIcon data-icon="inline-end" />
        </Button>
      </section>

      <div className={styles.account}>
        <CircleUserRoundIcon className="text-muted-foreground" />
        <strong>{accountEmail || "开发者"}</strong>
        <Button variant="outline" onClick={onLogout}>
          退出
        </Button>
      </div>
    </aside>
  );
};

const ModePicker = ({
  mode,
  setMode,
}: {
  mode: Mode;
  setMode: (mode: Mode) => void;
}) => {
  return (
    <ToggleGroup
      aria-label="工作台模式"
      className={styles.modePicker}
      spacing={0}
      value={[mode]}
      variant="outline"
      onValueChange={(values) => {
        const nextMode = values[0] as Mode | undefined;
        if (!nextMode) return;
        setMode(nextMode);
      }}
    >
      {modes.map(({ icon: Icon, label, value }) => (
        <ToggleGroupItem key={value} aria-label={label} value={value}>
          <Icon />
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
};

const WorkspaceHeader = ({
  isChatVisible,
  isNavigationVisible,
  mode,
  onChatVisibilityChange,
  onNavigationVisibilityChange,
  projectTitle,
  setMode,
}: {
  isChatVisible: boolean;
  isNavigationVisible: boolean;
  mode: Mode;
  onChatVisibilityChange: () => void;
  onNavigationVisibilityChange: () => void;
  projectTitle: string;
  setMode: (mode: Mode) => void;
}) => {
  return (
    <header className={styles.workspaceHeader}>
      <div className={styles.chatHeader}>
        {!isNavigationVisible ? (
          <Button
            aria-controls="project-navigation"
            aria-expanded={false}
            aria-label="展开侧边栏"
            size="icon"
            variant="ghost"
            onClick={onNavigationVisibilityChange}
          >
            <PanelLeftOpenIcon />
          </Button>
        ) : null}
        <StarIcon className={styles.mutedIcon} />
        <strong className={styles.chatTitle}>{projectTitle}</strong>
        <ChevronDownIcon className={styles.mutedIcon} />
      </div>
      <div className={styles.modeHeader}>
        <Button
          aria-controls="workspace-chat-panel"
          aria-expanded={isChatVisible}
          aria-label={isChatVisible ? "隐藏对话内容栏" : "显示对话内容栏"}
          size="icon"
          variant="ghost"
          onClick={onChatVisibilityChange}
        >
          {isChatVisible ? <PanelLeftCloseIcon /> : <PanelLeftOpenIcon />}
        </Button>
        <ModePicker mode={mode} setMode={setMode} />
      </div>
      <div className={styles.canvasHeader}>
        <Button aria-label="更多操作" size="icon" variant="outline">
          <MoreHorizontalIcon />
        </Button>
        <Button aria-label="分享" size="icon" variant="outline">
          <UploadIcon />
        </Button>
        <Button>
          <Globe2Icon data-icon="inline-start" />
          发布
        </Button>
      </div>
    </header>
  );
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
        <span>AI</span>
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
  const canSend = Boolean(draft.trim()) && !isLoading;
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
    <section id="workspace-chat-panel" className={styles.chatPanel}>
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
                说说你想设计什么，AI 会在这里和你一起梳理。
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
            AI 正在整理思路
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
              isLoading ? "等待 AI 回复..." : "描述下一步，或补充你的设计想法"
            }
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <InputGroupAddon align="block-end" className={styles.composerActions}>
            <span className={styles.composerHint}>
              Enter 发送 · Shift+Enter 换行
            </span>
            <InputGroupButton
              aria-label="发送消息"
              disabled={!canSend}
              size="icon-sm"
              type="submit"
              variant="default"
            >
              <ArrowUpIcon data-icon="inline-start" />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </form>
    </section>
  );
};

const FileExplorer = ({ projectTitle }: { projectTitle: string }) => {
  return (
    <section className={styles.fileExplorer}>
      <div className={styles.fileTabs}>
        <Button aria-label="文件" size="icon" variant="ghost">
          <FilesIcon />
        </Button>
        <Button aria-label="搜索文件" size="icon" variant="ghost">
          <SearchIcon />
        </Button>
        <Button aria-label="资源" size="icon" variant="ghost">
          <ShapesIcon />
        </Button>
      </div>
      <div className={styles.fileToolbar}>
        <span className={styles.fileTitle}>{projectTitle}</span>
        <div className={styles.fileActions}>
          <Button aria-label="新建文件" size="icon-xs" variant="ghost">
            <FilePlus2Icon />
          </Button>
          <Button aria-label="新建文件夹" size="icon-xs" variant="ghost">
            <FolderPlusIcon />
          </Button>
          <Button aria-label="刷新" size="icon-xs" variant="ghost">
            <RefreshCwIcon />
          </Button>
          <Button aria-label="更多操作" size="icon-xs" variant="ghost">
            <MoreHorizontalIcon />
          </Button>
        </div>
      </div>
      <Empty className={styles.fileEmpty}>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <FolderTreeIcon />
          </EmptyMedia>
          <EmptyTitle>暂无项目文件</EmptyTitle>
          <EmptyDescription>生成后将在此显示文件。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </section>
  );
};

const Canvas = ({ mode }: { mode: Mode }) => {
  return (
    <section className={styles.canvas}>
      <div className={styles.canvasBody}>
        {mode === "代码" ? (
          <>
            <span className={styles.canvasBrand}>v0</span>
            <div className={styles.shortcuts}>
              <Separator className={styles.shortcutsSeparator} />
              {[
                ["Go to File", "⌘", "P"],
                ["Find in Files", "⇧", "⌘ F"],
                ["Command Palette", "⇧", "⌘ P"],
                ["Terminal", "⌃", "`"],
              ].map(([label, ...keys]) => (
                <div key={label} className={styles.shortcutRow}>
                  <span className={styles.shortcutLabel}>{label}</span>
                  {keys.map((key) => (
                    <kbd key={key} className={styles.shortcutKey}>
                      {key}
                    </kbd>
                  ))}
                </div>
              ))}
            </div>
          </>
        ) : null}
        {mode === "预览" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <PanelsTopLeftIcon />
              </EmptyMedia>
              <EmptyTitle>预览尚未生成</EmptyTitle>
              <EmptyDescription>项目生成后将在这里显示。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
        {mode === "发送" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <SendIcon />
              </EmptyMedia>
              <EmptyTitle>等待生成结果</EmptyTitle>
              <EmptyDescription>生成完成后可在这里继续对话。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
        {mode === "数据" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <DatabaseIcon />
              </EmptyMedia>
              <EmptyTitle>暂无数据源</EmptyTitle>
              <EmptyDescription>连接数据库后将在此管理数据。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
      </div>
    </section>
  );
};

const Workspace = ({
  accountEmail,
  error,
  messages,
  onLogout,
  onRetry,
  onSend,
  onStop,
  projectTitle,
  status,
}: WorkspaceProps) => {
  const isCompactNavigation = useSyncExternalStore(
    subscribeCompactNavigation,
    getCompactNavigationSnapshot,
    getServerCompactNavigationSnapshot,
  );
  const [mode, setMode] = useState<Mode>("代码");
  const [isChatVisible, setIsChatVisible] = useState(true);
  const [isDesktopNavigationVisible, setIsDesktopNavigationVisible] =
    useState(true);
  const [isCompactNavigationVisible, setIsCompactNavigationVisible] =
    useState(false);
  const isNavigationVisible = isCompactNavigation
    ? isCompactNavigationVisible
    : isDesktopNavigationVisible;
  const collapseNavigation = () => {
    if (isCompactNavigation) return setIsCompactNavigationVisible(false);
    setIsDesktopNavigationVisible(false);
  };
  const toggleNavigation = () => {
    if (isCompactNavigation)
      return setIsCompactNavigationVisible((isVisible) => !isVisible);
    setIsDesktopNavigationVisible((isVisible) => !isVisible);
  };

  return (
    <main
      className={styles.workspace}
      data-navigation-hidden={!isNavigationVisible}
    >
      <ProjectNavigation
        accountEmail={accountEmail}
        title={projectTitle}
        onCollapse={collapseNavigation}
        onLogout={onLogout}
      />
      <section className={styles.workbench} data-chat-hidden={!isChatVisible}>
        <WorkspaceHeader
          isChatVisible={isChatVisible}
          isNavigationVisible={isNavigationVisible}
          mode={mode}
          projectTitle={projectTitle}
          setMode={setMode}
          onChatVisibilityChange={() =>
            setIsChatVisible((isVisible) => !isVisible)
          }
          onNavigationVisibilityChange={toggleNavigation}
        />
        <div className={styles.workspaceBody}>
          <ChatPanel
            error={error}
            messages={messages}
            status={status}
            onRetry={onRetry}
            onSend={onSend}
            onStop={onStop}
          />
          <FileExplorer projectTitle={projectTitle} />
          <Canvas mode={mode} />
        </div>
      </section>
    </main>
  );
};

const WorkspaceFallback = () => <main className={styles.fallback} />;

export { Workspace, WorkspaceFallback };
export type { ChatMessage, ChatRole, ChatStatus, WorkspaceProps };
