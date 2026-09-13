import { useQuery } from "@tanstack/react-query";

import { conversationsApi } from "@/features/chat/api";

export const conversationKeys = {
  detail: (id: string) => ["conversations", id] as const,
};

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: conversationKeys.detail(id ?? ""),
    queryFn: () => conversationsApi.get(id as string),
    enabled: id !== null,
  });
}
