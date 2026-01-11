import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateNotionPageMarkdown } from "@/lib/api/notion";
import type { UpdateNotionPageMarkdownRequest } from "@/lib/api/types/notion";
import { notionPageMarkdownQueryKey } from "@/features/notion/queries";

export function useUpdateNotionPageMarkdown(pageId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UpdateNotionPageMarkdownRequest) =>
      updateNotionPageMarkdown(pageId, payload),
    onSuccess: (_resp, payload) => {
      queryClient.setQueryData(notionPageMarkdownQueryKey(pageId), (prev) => {
        if (!prev || typeof prev !== "object") return prev;
        return { ...(prev as Record<string, unknown>), markdown: payload.markdown };
      });
    },
  });
}
