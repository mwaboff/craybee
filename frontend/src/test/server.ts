import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { RunCreate } from "@/types/run";

import { llmServerHandlers } from "./fixtures/llmServers";

const runHandlers = [
  http.post("/api/v1/runs", async ({ request }) => {
    const body = (await request.json()) as RunCreate;
    return HttpResponse.json(
      {
        id: "run-1",
        prompt: body.prompt,
        status: "pending",
        conversation_id: body.conversation_id ?? "conv-1",
      },
      { status: 201 },
    );
  }),

  // Default: empty transcript. Override per-test with server.use(...) for
  // canonical turns (e.g. after a run completes).
  http.get("/api/v1/conversations/:id", ({ params }) => {
    return HttpResponse.json({ id: params.id, turns: [], active_run_id: null });
  }),
];

export const server = setupServer(...llmServerHandlers, ...runHandlers);
