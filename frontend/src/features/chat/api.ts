import { api } from "@/api/client";
import type { ConversationDetail } from "@/features/chat/types";
import type { RunCreate, RunSummary } from "@/types/run";

export const runsApi = {
  create: (body: RunCreate) =>
    api<RunSummary>("/runs", { method: "POST", body: JSON.stringify(body) }),
  list: () => api<RunSummary[]>("/runs"),
  cancel: (id: string) => api<RunSummary>(`/runs/${id}/cancel`, { method: "POST" }),
};

export const conversationsApi = {
  get: (id: string) => api<ConversationDetail>(`/conversations/${id}`),
};
