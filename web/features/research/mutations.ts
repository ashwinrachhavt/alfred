import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deepResearch } from "@/lib/api/research";
import { recentResearchReportsQueryKey } from "@/features/research/queries";

export function useStartDeepResearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ topic, refresh }: { topic: string; refresh?: boolean }) =>
      deepResearch({ topic, refresh, background: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: recentResearchReportsQueryKey(20).slice(0, 3),
      });
    },
  });
}
