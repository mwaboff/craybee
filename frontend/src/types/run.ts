export type RunStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface RunSummary {
  id: string;
  prompt: string;
  status: RunStatus;
  conversation_id: string;
}

export interface RunCreate {
  prompt: string;
  conversation_id?: string;
}

export interface RunEvent {
  type: "status" | "token" | "node" | "log" | "error" | "usage";
  run_id: string;
  at: string;
  data: Record<string, unknown>;
}
