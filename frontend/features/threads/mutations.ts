import { useMutation, useQueryClient } from "@tanstack/react-query";

import { appendThreadMessage, createThread } from "@/lib/api/threads";
import type { AppendThreadMessageRequest, CreateThreadRequest } from "@/lib/api/types/threads";
import { threadMessagesQueryKey, threadsQueryKey } from "@/features/threads/queries";

export function useCreateThread() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateThreadRequest) => createThread(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: threadsQueryKey() });
    },
  });
}

export function useAppendThreadMessage(threadId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: AppendThreadMessageRequest) => appendThreadMessage(threadId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: threadMessagesQueryKey(threadId) });
      queryClient.invalidateQueries({ queryKey: threadsQueryKey() });
    },
  });
}
