"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { WorkspaceFallback } from "@repo/ui/blocks/workspace";

import { WorkspaceChat } from "./workspace-chat";

const WorkspaceContent = () => {
  const searchParams = useSearchParams();
  const prompt = searchParams.get("prompt")?.trim() || "";

  return <WorkspaceChat prompt={prompt} />;
};

const WorkspacePage = () => {
  return (
    <Suspense fallback={<WorkspaceFallback />}>
      <WorkspaceContent />
    </Suspense>
  );
};

export default WorkspacePage;
