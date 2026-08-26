export type RunStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface RunSummary {
  id: string;
  prompt: string;
  status: RunStatus;
}

export interface RunEvent {
  type: "status" | "token" | "node" | "log" | "error";
  run_id: string;
  at: string;
  data: Record<string, unknown>;
}
