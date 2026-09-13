import { ArrowDown } from "lucide-react";
import { useRef } from "react";

import { IconButton } from "@/components/ui/IconButton";
import { MessageBubble } from "@/features/chat/components/MessageBubble";
import type { Turn } from "@/features/chat/types";
import { useStickToBottom } from "@/hooks/useStickToBottom";

import styles from "./Transcript.module.css";

export type LiveExchange = {
  prompt: string;
  text: string;
  streaming: boolean;
};

type TranscriptProps = {
  turns: Turn[];
  live: LiveExchange | null;
};

export function Transcript({ turns, live }: TranscriptProps) {
  const scrollerRef = useRef<HTMLDivElement>(null);
  const { isAtBottom, scrollToBottom } = useStickToBottom(scrollerRef);

  return (
    <div className={styles.container}>
      <div className={styles.scroller} ref={scrollerRef}>
        <div className={styles.content}>
          {turns.map((turn, index) => (
            <MessageBubble
              key={index}
              role={turn.role}
              content={turn.content}
              partial={turn.partial}
              usage={turn.usage}
            />
          ))}
          {live && (
            <>
              <MessageBubble role="user" content={live.prompt} />
              <MessageBubble role="assistant" content={live.text} streaming={live.streaming} />
            </>
          )}
        </div>
      </div>
      {!isAtBottom && (
        <IconButton
          variant="default"
          aria-label="Jump to latest"
          className={styles.jumpToLatest}
          onClick={scrollToBottom}
        >
          <ArrowDown size={16} aria-hidden="true" />
        </IconButton>
      )}
    </div>
  );
}
