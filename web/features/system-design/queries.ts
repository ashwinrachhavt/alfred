import { useQuery } from "@tanstack/react-query";

import { getSystemDesignComponents, getSystemDesignTemplates } from "@/lib/api/system-design";
import {
  systemDesignComponentsQueryKey,
  systemDesignTemplatesQueryKey,
} from "@/features/system-design/query-keys";

export function useSystemDesignTemplates() {
  return useQuery({
    queryKey: systemDesignTemplatesQueryKey(),
    queryFn: () => getSystemDesignTemplates(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSystemDesignComponents() {
  return useQuery({
    queryKey: systemDesignComponentsQueryKey(),
    queryFn: () => getSystemDesignComponents(),
    staleTime: 5 * 60 * 1000,
  });
}
