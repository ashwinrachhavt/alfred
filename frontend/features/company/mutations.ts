import { useMutation, useQueryClient } from "@tanstack/react-query";

import { companyResearch } from "@/lib/api/company";
import { recentCompanyResearchReportsQueryKey } from "@/features/company/queries";

export function useStartCompanyResearch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, refresh }: { name: string; refresh?: boolean }) =>
      companyResearch({ name, refresh, background: true }),
    onSuccess: () => {
      // Invalidate all "recent" lists regardless of limit.
      queryClient.invalidateQueries({
        queryKey: recentCompanyResearchReportsQueryKey(20).slice(0, 3),
      });
    },
  });
}
