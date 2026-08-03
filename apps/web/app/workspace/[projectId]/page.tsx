"use client";

import { use } from "react";
import { WorkspaceChat } from "../workspace-chat";

const ProjectWorkspacePage = ({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) => {
  const projectId = use(params).projectId;
  return <WorkspaceChat projectId={projectId} />;
};

export default ProjectWorkspacePage;
