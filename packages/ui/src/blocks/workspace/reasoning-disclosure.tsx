"use client";

import { useState } from "react";
import { ChevronDownIcon } from "lucide-react";
import styles from "./workspace.module.css";

type ReasoningPresentationItem = {
  id: string;
  stage: string;
  taskId: string;
  attempt: number;
  content: string;
  status: "reasoning" | "completed" | "truncated";
};

const reasoningSummary = (
  content: string,
  status: ReasoningPresentationItem["status"],
) => {
  const lines = content
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  return status === "reasoning"
    ? lines.at(-1) || "正在分析…"
    : lines[0] || "思考过程";
};

const ReasoningDisclosure = ({ item }: { item: ReasoningPresentationItem }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className={styles.reasoningMessage} data-status={item.status}>
      <details className={styles.reasoningDisclosure} open={expanded}>
        <summary
          aria-expanded={expanded}
          className={styles.reasoningSummary}
          onClick={(event) => {
            event.preventDefault();
            setExpanded((value) => !value);
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            setExpanded((value) => !value);
          }}
        >
          <span aria-hidden className={styles.reasoningIndicator} />
          <span
            aria-live="polite"
            aria-atomic="true"
            className={styles.reasoningTitle}
            role="status"
          >
            {item.status === "reasoning" ? "正在思考" : "思考过程"}
          </span>
          <span className={styles.reasoningPreview}>
            {reasoningSummary(item.content, item.status)}
          </span>
          <ChevronDownIcon aria-hidden className={styles.reasoningChevron} />
        </summary>
        <div className={styles.reasoningBody}>
          <p className={styles.messageContent}>{item.content}</p>
          {item.status === "truncated" ? (
            <p className={styles.reasoningNotice}>思考内容已达到展示上限</p>
          ) : null}
        </div>
      </details>
    </article>
  );
};

export { ReasoningDisclosure };
export type { ReasoningPresentationItem };
