import { useQuery } from "@tanstack/react-query"

import { getSystemDesignTemplates } from "@/lib/api/system-design"
import { systemDesignTemplatesQueryKey } from "@/features/system-design/query-keys"

export function useSystemDesignTemplates() {
  return useQuery({
    queryKey: systemDesignTemplatesQueryKey(),
    queryFn: () => getSystemDesignTemplates(),
    staleTime: 5 * 60 * 1000,
  })
}

