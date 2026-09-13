import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { HexLoader } from "@/components/ui/HexLoader";
import type { Role, Usage } from "@/features/chat/types";

import styles from "./MessageBubble.module.css";

type MessageBubbleProps = {
  role: Role;
  content: string;
  partial?: boolean;
  usage?: Usage | null;
  /** True while an assistant reply is still streaming in. */
  streaming?: boolean;
};

function totalTokens(usage: Usage): number {
  return usage.input_tokens + usage.output_tokens + usage.cache_read_tokens + usage.cache_write_tokens;
}

export function MessageBubble({ role, content, partial, usage, streaming }: MessageBubbleProps) {
  const isUser = role === "user";
  const showLoader = streaming && content.length === 0;

  return (
    <article
      aria-label={isUser ? "You" : "Assistant"}
      className={[styles.bubble, isUser ? styles.user : styles.assistant].join(" ")}
    >
      {showLoader ? (
        <HexLoader size="1.1em" />
      ) : isUser ? (
        <p className={styles.plain}>{content}</p>
      ) : (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
      {(partial || usage) && (
        <footer className={styles.footer}>
          {partial ? "Interrupted" : usage ? `${totalTokens(usage)} tokens` : null}
        </footer>
      )}
    </article>
  );
}
