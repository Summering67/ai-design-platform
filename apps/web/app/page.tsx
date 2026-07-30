"use client"

import { type FormEvent, useState } from "react"
import {
  ActivityIcon,
  ArrowUpIcon,
  ChevronDownIcon,
  Gamepad2Icon,
  ImageIcon,
  MailIcon,
  MicIcon,
  RefreshCwIcon,
  SparklesIcon,
} from "lucide-react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group"
import styles from "./page.module.css"

const suggestions = [
  { label: "联系表单", prompt: "创建一个简洁专业的联系表单", icon: MailIcon },
  { label: "图片编辑器", prompt: "创建一个现代化的在线图片编辑器", icon: ImageIcon },
  { label: "迷你游戏", prompt: "创建一个有趣的网页迷你游戏", icon: Gamepad2Icon },
  { label: "财务计算器", prompt: "创建一个清晰易用的财务计算器", icon: ActivityIcon },
] as const

const Home = () => {
  const router = useRouter()
  const [prompt, setPrompt] = useState("")

  const openWorkspace = (value: string) => {
    const nextPrompt = value.trim()
    if (!nextPrompt) return
    router.push(`/workspace?prompt=${encodeURIComponent(nextPrompt)}`)
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    openWorkspace(prompt)
  }

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heading}>
          <span className={styles.eyebrow}>
            <SparklesIcon />
            AI DESIGN STUDIO
          </span>
          <h1 className={styles.title}>您想创建什么？</h1>
          <p className={styles.description}>描述你的想法，我们会帮你把它变成可用的产品。</p>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          <InputGroup className={styles.composer}>
            <InputGroupTextarea
              aria-label="描述你想创建的内容"
              autoFocus
              className={styles.composerInput}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" || event.shiftKey) return
                event.preventDefault()
                openWorkspace(prompt)
              }}
              placeholder="让 AI 为你构建..."
            />
            <InputGroupAddon align="block-end" className={styles.composerActions}>
              <InputGroupButton size="sm">
                <SparklesIcon data-icon="inline-start" />
                Design Max
                <ChevronDownIcon data-icon="inline-end" />
              </InputGroupButton>
              <InputGroupButton
                aria-label={prompt.trim() ? "开始创建" : "语音输入"}
                size="icon-sm"
                type="submit"
                variant="default"
              >
                {prompt.trim() ? <ArrowUpIcon /> : <MicIcon />}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </form>

        <div className={styles.suggestions}>
          {suggestions.map(({ icon: Icon, label, prompt: value }) => (
            <Button key={label} className={styles.suggestionButton} variant="outline" onClick={() => openWorkspace(value)}>
              <Icon data-icon="inline-start" />
              {label}
            </Button>
          ))}
          <Button aria-label="清空输入" className={styles.suggestionButton} size="icon" variant="outline" onClick={() => setPrompt("")}>
            <RefreshCwIcon />
          </Button>
        </div>
      </section>
    </main>
  )
}

export default Home
