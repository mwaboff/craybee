import { useEffect, useMemo, useRef, useState } from "react";

import { wsUrl } from "@/api/client";
import type { RunEvent, RunStatus } from "@/types/run";

const TERMINAL: readonly RunStatus[] = ["succeeded", "failed", "cancelled"];
const RUN_NOT_FOUND = 4404;
const MAX_RETRY_MS = 5_000;

export interface RunStream {
  events: RunEvent[];
  text: string;
  status: RunStatus | null;
  /** False while disconnected; the UI can show a reconnecting hint. */
  connected: boolean;
}

/**
 * Subscribe to a run's event stream.
 *
 * Reconnects with backoff, which is the one thing a WebSocket does not give
 * you for free (EventSource does). It is cheap here because the server replays
 * a run's whole event log on connect: recovery is just "reconnect and rebuild"
 * rather than "track where we left off and ask for the delta".
 */
export function useRunStream(runId: string | null): RunStream {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);

  // onclose needs the current status, but must not be re-created when it
  // changes -- a ref keeps the socket lifecycle out of the effect's deps.
  const isTerminal = useRef(false);

  useEffect(() => {
    setEvents([]);
    isTerminal.current = false;
    if (!runId) return;

    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(wsUrl(`/ws/runs/${runId}`));

      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
        // The replay is the full log, so reset rather than append -- otherwise
        // a reconnect renders every prior token a second time.
        setEvents([]);
      };

      socket.onmessage = (message) => {
        const event = JSON.parse(message.data) as RunEvent;
        if (event.type === "status" && TERMINAL.includes(event.data.status as RunStatus)) {
          isTerminal.current = true;
        }
        setEvents((prior) => [...prior, event]);
      };

      socket.onclose = (close) => {
        setConnected(false);
        // Don't retry a finished run, a run the server says doesn't exist, or
        // an unmounted component -- each would reconnect forever.
        if (disposed || isTerminal.current || close.code === RUN_NOT_FOUND) return;

        const delay = Math.min(2 ** attempt++ * 250, MAX_RETRY_MS);
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      disposed = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, [runId]);

  return useMemo(() => {
    const text = events
      .filter((event) => event.type === "token")
      .map((event) => event.data.text as string)
      .join("");

    const status =
      ([...events].reverse().find((event) => event.type === "status")?.data.status as
        | RunStatus
        | undefined) ?? null;

    return { events, text, status, connected };
  }, [events, connected]);
}
