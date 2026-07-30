"use client"

import { Suspense, useState } from "react"
import type { LucideIcon } from "lucide-react"
import {
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
} from "lucide-react"
import { useSearchParams } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import styles from "./workspace.module.css"

const navItems: ReadonlyArray<{ label: string; icon: LucideIcon }> = [
  { label: "搜索", icon: SearchIcon },
  { label: "首页", icon: HomeIcon },
  { label: "项目", icon: PanelsTopLeftIcon },
  { label: "库", icon: LibraryIcon },
  { label: "设计系统", icon: ShapesIcon },
  { label: "模板", icon: LayoutTemplateIcon },
]

const modes = [
  { value: "预览", label: "预览", icon: PanelsTopLeftIcon },
  { value: "发送", label: "发送", icon: SendIcon },
  { value: "代码", label: "代码", icon: Code2Icon },
  { value: "数据", label: "数据", icon: DatabaseIcon },
] as const

type Mode = (typeof modes)[number]["value"]

const getProjectTitle = (prompt: string) =>
  prompt ? `${prompt.slice(0, 12)}${prompt.length > 12 ? "..." : ""}` : "新建项目"

const ProjectNavigation = ({ title }: { title: string }) => {
  return (
    <aside className={styles.navigation}>
      <header className={styles.header}>
        <span className={styles.brand}>
          <SparklesIcon />
        </span>
        <strong>我的项目</strong>
        <ChevronDownIcon className="text-muted-foreground" />
        <Button aria-label="收起侧边栏" size="icon" variant="ghost"><PanelLeftCloseIcon /></Button>
      </header>
      <Separator />

      <Button className="mt-1 w-full justify-between" size="lg" variant="outline">
        <span>新建聊天</span>
        <ChevronDownIcon data-icon="inline-end" />
      </Button>

      <nav className={styles.menu}>
        {navItems.map(({ icon: Icon, label }) => (
          <Button key={label} className="w-full justify-start" size="lg" variant="ghost">
            <Icon data-icon="inline-start" />
            {label}
          </Button>
        ))}
      </nav>

      <section className={styles.chatSections}>
        <Button className="w-full justify-between" variant="ghost">
          <span>收藏</span><ChevronRightIcon data-icon="inline-end" />
        </Button>
        <Button className="w-full justify-between" variant="ghost">
          <span>最近聊天</span><ChevronDownIcon data-icon="inline-end" />
        </Button>
        <Button className={styles.currentChat} variant="secondary">
          <CircleDashedIcon data-icon="inline-start" />
          <span>{title}</span>
          <MoreHorizontalIcon data-icon="inline-end" />
        </Button>
      </section>

      <div className={styles.account}>
        <CircleUserRoundIcon className="text-muted-foreground" />
        <strong>访客</strong>
        <Button variant="outline">登录</Button>
      </div>
    </aside>
  )
}

const ModePicker = ({ mode, setMode }: { mode: Mode; setMode: (mode: Mode) => void }) => {
  return (
    <ToggleGroup
      aria-label="工作台模式"
      className={styles.modePicker}
      spacing={0}
      value={[mode]}
      variant="outline"
      onValueChange={(values) => {
        const nextMode = values[0] as Mode | undefined
        if (!nextMode) return
        setMode(nextMode)
      }}
    >
      {modes.map(({ icon: Icon, label, value }) => (
        <ToggleGroupItem key={value} aria-label={label} value={value}><Icon /></ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

const WorkspaceHeader = ({
  isChatVisible,
  mode,
  onChatVisibilityChange,
  projectTitle,
  setMode,
}: {
  isChatVisible: boolean
  mode: Mode
  onChatVisibilityChange: () => void
  projectTitle: string
  setMode: (mode: Mode) => void
}) => {
  return (
    <header className={styles.workspaceHeader}>
      <div className={styles.chatHeader}>
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
        <Button aria-label="更多操作" size="icon" variant="outline"><MoreHorizontalIcon /></Button>
        <Button aria-label="分享" size="icon" variant="outline"><UploadIcon /></Button>
        <Button>
          <Globe2Icon data-icon="inline-start" />
          发布
        </Button>
      </div>
    </header>
  )
}

const ChatPanel = ({ prompt }: { prompt: string }) => {
  return (
    <section id="workspace-chat-panel" className={styles.chatPanel}>
      <div className={styles.chatScroll}>
        {prompt ? (
          <div className={styles.chatFlow}>
            <div className={styles.userMessage}>
              {prompt}
            </div>
            <Empty className={styles.generationState}>
              <EmptyHeader>
                <EmptyMedia><Spinner className={styles.generationSpinner} /></EmptyMedia>
                <EmptyTitle>正在准备工作区</EmptyTitle>
                <EmptyDescription>分析需求并创建项目结构...</EmptyDescription>
              </EmptyHeader>
            </Empty>
          </div>
        ) : (
          <Empty className={styles.emptyFill}>
            <EmptyHeader>
              <EmptyMedia variant="icon"><SparklesIcon /></EmptyMedia>
              <EmptyTitle>开始一个新项目</EmptyTitle>
              <EmptyDescription>从首页描述你想创建的内容。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
      </div>
    </section>
  )
}

const FileExplorer = ({ projectTitle }: { projectTitle: string }) => {
  return (
    <section className={styles.fileExplorer}>
      <div className={styles.fileTabs}>
        <Button aria-label="文件" size="icon" variant="ghost"><FilesIcon /></Button>
        <Button aria-label="搜索文件" size="icon" variant="ghost"><SearchIcon /></Button>
        <Button aria-label="资源" size="icon" variant="ghost"><ShapesIcon /></Button>
      </div>
      <div className={styles.fileToolbar}>
        <span className={styles.fileTitle}>{projectTitle}</span>
        <div className={styles.fileActions}>
          <Button aria-label="新建文件" size="icon-xs" variant="ghost"><FilePlus2Icon /></Button>
          <Button aria-label="新建文件夹" size="icon-xs" variant="ghost"><FolderPlusIcon /></Button>
          <Button aria-label="刷新" size="icon-xs" variant="ghost"><RefreshCwIcon /></Button>
          <Button aria-label="更多操作" size="icon-xs" variant="ghost"><MoreHorizontalIcon /></Button>
        </div>
      </div>
      <Empty className={styles.fileEmpty}>
        <EmptyHeader>
          <EmptyMedia variant="icon"><FolderTreeIcon /></EmptyMedia>
          <EmptyTitle>暂无项目文件</EmptyTitle>
          <EmptyDescription>生成后将在此显示文件。</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </section>
  )
}

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
                  {keys.map((key) => <kbd key={key} className={styles.shortcutKey}>{key}</kbd>)}
                </div>
              ))}
            </div>
          </>
        ) : null}
        {mode === "预览" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><PanelsTopLeftIcon /></EmptyMedia>
              <EmptyTitle>预览尚未生成</EmptyTitle>
              <EmptyDescription>项目生成后将在这里显示。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
        {mode === "发送" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><SendIcon /></EmptyMedia>
              <EmptyTitle>等待生成结果</EmptyTitle>
              <EmptyDescription>生成完成后可在这里继续对话。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
        {mode === "数据" ? (
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><DatabaseIcon /></EmptyMedia>
              <EmptyTitle>暂无数据源</EmptyTitle>
              <EmptyDescription>连接数据库后将在此管理数据。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
      </div>
    </section>
  )
}

const WorkspaceContent = () => {
  const searchParams = useSearchParams()
  const prompt = searchParams.get("prompt")?.trim() || ""
  const projectTitle = getProjectTitle(prompt)
  const [mode, setMode] = useState<Mode>("代码")
  const [isChatVisible, setIsChatVisible] = useState(true)

  return (
    <main className={styles.shell}>
      <ProjectNavigation title={projectTitle} />
      <section className={styles.workbench} data-chat-hidden={!isChatVisible}>
        <WorkspaceHeader
          isChatVisible={isChatVisible}
          mode={mode}
          projectTitle={projectTitle}
          setMode={setMode}
          onChatVisibilityChange={() => setIsChatVisible((isVisible) => !isVisible)}
        />
        <div className={styles.workspaceBody}>
          <ChatPanel prompt={prompt} />
          <FileExplorer projectTitle={projectTitle} />
          <Canvas mode={mode} />
        </div>
      </section>
    </main>
  )
}

const WorkspacePage = () => {
  return (
    <Suspense fallback={<main className={styles.fallback} />}>
      <WorkspaceContent />
    </Suspense>
  )
}

export default WorkspacePage
