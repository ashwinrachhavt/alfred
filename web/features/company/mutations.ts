import { useMutation, useQueryClient } from "@tanstack/react-query";

import { companyResearch, discoverCompanyContacts } from "@/lib/api/company";
import {
  companyContactsDbQueryKey,
  recentCompanyResearchReportsQueryKey,
} from "@/features/company/queries";

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

export function useDiscoverCompanyContacts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, role }: { name: string; role?: string }) =>
      discoverCompanyContacts({ name, role, limit: 20, refresh: true }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: companyContactsDbQueryKey({ name: variables.name, role: variables.role, limit: 20 })
          .slice(0, 3),
      });
    },
  });
}
