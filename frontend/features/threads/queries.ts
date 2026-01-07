import { useQuery } from "@tanstack/react-query";

import { listThreadMessages, listThreads } from "@/lib/api/threads";

export function threadsQueryKey() {
  return ["threads", "list"] as const;
}

export function threadMessagesQueryKey(threadId: string) {
  return ["threads", threadId, "messages"] as const;
}

export function useThreads() {
  return useQuery({
    queryKey: threadsQueryKey(),
    queryFn: () => listThreads(),
  });
}

export function useThreadMessages(threadId: string) {
  return useQuery({
    enabled: Boolean(threadId),
    queryKey: threadMessagesQueryKey(threadId),
    queryFn: () => listThreadMessages(threadId),
    refetchInterval: 4000,
  });
}
