import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { llmServersApi } from "@/features/settings/api";
import type { LLMServer, LLMServerUpdate } from "@/features/settings/types";

export const llmServerKeys = {
  all: ["llm-servers"] as const,
};

export function useLlmServers() {
  return useQuery({ queryKey: llmServerKeys.all, queryFn: llmServersApi.list });
}

export function useCreateLlmServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: llmServersApi.create,
    onSuccess: (created) => {
      queryClient.setQueryData<LLMServer[]>(llmServerKeys.all, (old) => {
        const others = created.is_default
          ? (old ?? []).map((s) => (s.is_default ? { ...s, is_default: false } : s))
          : old ?? [];
        return [...others, created];
      });
      queryClient.invalidateQueries({ queryKey: llmServerKeys.all });
    },
  });
}

export function useUpdateLlmServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: LLMServerUpdate }) =>
      llmServersApi.update(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: llmServerKeys.all }),
  });
}

export function useDeleteLlmServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: llmServersApi.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: llmServerKeys.all }),
  });
}

export function useSetDefaultLlmServer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: llmServersApi.setDefault,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: llmServerKeys.all }),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: llmServersApi.listModels,
  });
}
