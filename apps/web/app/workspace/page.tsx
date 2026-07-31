"use client"

import { Suspense } from "react"
import { useSearchParams } from "next/navigation"

import { Workspace, WorkspaceFallback } from "@repo/ui/blocks/workspace"

const WorkspaceContent = () => {
  const searchParams = useSearchParams()
  const prompt = searchParams.get("prompt")?.trim() || ""

  return <Workspace prompt={prompt} />
}

const WorkspacePage = () => {
  return (
    <Suspense fallback={<WorkspaceFallback />}>
      <WorkspaceContent />
    </Suspense>
  )
}

export default WorkspacePage
