/**
 * Pure contract mirror of backend/services/llm/conversation.py.
 * No behavior here -- keep this file free of imports/logic.
 */

export type Role = "user" | "assistant";

export type Usage = {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  cost_usd: number | null;
  context_window: number | null;
};

export type Turn = {
  role: Role;
  content: string;
  at: string;
  partial: boolean;
  usage: Usage | null;
};

export type ConversationDetail = {
  id: string;
  turns: Turn[];
  active_run_id: string | null;
};
