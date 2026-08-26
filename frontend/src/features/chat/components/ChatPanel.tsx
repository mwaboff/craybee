import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { runsApi } from "@/features/chat/api";
import { useRunStream } from "@/features/chat/hooks/useRunStream";

const LIVE_STATUSES = new Set(["pending", "running"]);

export function ChatPanel() {
  const [prompt, setPrompt] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const { text, status, connected } = useRunStream(runId);

  const startRun = useMutation({
    mutationFn: runsApi.create,
    onSuccess: (run) => setRunId(run.id),
  });

  const cancelRun = useMutation({ mutationFn: runsApi.cancel });
  const isLive = status !== null && LIVE_STATUSES.has(status);

  return (
    <section className="chat">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (prompt.trim()) startRun.mutate(prompt);
        }}
      >
        <input
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask the harness to do something..."
          aria-label="Prompt"
        />
        <button type="submit" disabled={startRun.isPending}>
          Run
        </button>
        {isLive && runId && (
          <button type="button" onClick={() => cancelRun.mutate(runId)}>
            Cancel
          </button>
        )}
      </form>

      <AnimatePresence>
        {runId && (
          <motion.output
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="transcript"
          >
            <span className="status">
              {status ?? "connecting"}
              {!connected && isLive && " - reconnecting"}
            </span>
            <p>{text}</p>
          </motion.output>
        )}
      </AnimatePresence>
    </section>
  );
}
