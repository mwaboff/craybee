import { api } from "@/api/client";
import type { RunSummary } from "@/types/run";

export const runsApi = {
  create: (prompt: string) =>
    api<RunSummary>("/runs", { method: "POST", body: JSON.stringify({ prompt }) }),
  list: () => api<RunSummary[]>("/runs"),
  cancel: (id: string) => api<RunSummary>(`/runs/${id}/cancel`, { method: "POST" }),
};
