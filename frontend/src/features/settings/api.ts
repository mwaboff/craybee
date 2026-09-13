import { api } from "@/api/client";
import type { LLMServer, LLMServerCreate, LLMServerUpdate, ModelList } from "@/features/settings/types";

export const llmServersApi = {
  list: () => api<LLMServer[]>("/llm-servers"),
  get: (id: string) => api<LLMServer>(`/llm-servers/${id}`),
  create: (body: LLMServerCreate) =>
    api<LLMServer>("/llm-servers", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: LLMServerUpdate) =>
    api<LLMServer>(`/llm-servers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/llm-servers/${id}`, { method: "DELETE" }),
  setDefault: (id: string) => api<LLMServer>(`/llm-servers/${id}/default`, { method: "POST" }),
  listModels: (id: string) => api<ModelList>(`/llm-servers/${id}/models`),
};
