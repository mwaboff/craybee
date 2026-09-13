import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/Alert";
import { runsApi } from "@/features/chat/api";
import { Transcript } from "@/features/chat/components/Transcript";
import { conversationKeys, useConversation } from "@/features/chat/hooks/useConversation";
import { useRunStream } from "@/features/chat/hooks/useRunStream";
import type { RunStatus } from "@/types/run";

import styles from "./ChatPanel.module.css";

const LIVE_STATUSES = new Set<RunStatus>(["pending", "running"]);

type ActiveRun = { runId: string; prompt: string };

export function ChatPanel() {
  const [prompt, setPrompt] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const conversation = useConversation(conversationId);
  const { events, text, status } = useRunStream(activeRun?.runId ?? null);

  const isLive = activeRun !== null && (status === null || LIVE_STATUSES.has(status));

  const startRun = useMutation({
    mutationFn: runsApi.create,
    onSuccess: (run) => {
      setConversationId(run.conversation_id);
      setActiveRun({ runId: run.id, prompt: run.prompt });
      setPrompt("");
      setRunError(null);
    },
  });

  const cancelRun = useMutation({ mutationFn: runsApi.cancel });

  // Once the run reaches a terminal status, surface any error, then refetch
  // the conversation and only drop the live bubble once that lands -- so the
  // transcript swaps straight from the streamed text to the canonical turn
  // with no gap, and the run's websocket closes as a side effect of runId
  // going back to null.
  useEffect(() => {
    if (!activeRun || status === null || LIVE_STATUSES.has(status)) return;

    if (status === "failed") {
      const errorEvent = events.find((event) => event.type === "error");
      const message = (errorEvent?.data.message as string | undefined) ?? "The run failed.";
      setRunError(message);
    }

    const id = conversationId;
    if (!id) {
      setActiveRun(null);
      return;
    }
    queryClient.invalidateQueries({ queryKey: conversationKeys.detail(id) }).then(() => {
      setActiveRun(null);
    });
    // Only the terminal transition matters here; activeRun/conversationId/events
    // are read fresh each run because a new run always means a fresh runId.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  const turns = conversation.data?.turns ?? [];
  const live = activeRun ? { prompt: activeRun.prompt, text, streaming: isLive } : null;
  const alertMessage = runError ?? startRun.error?.message;

  return (
    <section className={styles.chat}>
      <Transcript turns={turns} live={live} />

      {alertMessage && <Alert tone="error">{alertMessage}</Alert>}

      <div className={styles.inputContainer}>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (!prompt.trim() || isLive) return;
            startRun.mutate({ prompt, conversation_id: conversationId ?? undefined });
          }}
        >
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            rows={1}
            placeholder="What's on your mind?"
            aria-label="Prompt"
          />
          <button type="submit" disabled={isLive}>
            Send
          </button>
          {isLive && activeRun && (
            <button type="button" onClick={() => cancelRun.mutate(activeRun.runId)}>
              Cancel
            </button>
          )}
        </form>
      </div>
    </section>
  );
}
