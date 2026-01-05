import { useMutation } from "@tanstack/react-query";

import { companyResearch } from "@/lib/api/company";

export function useStartCompanyResearch() {
  return useMutation({
    mutationFn: ({ name, refresh }: { name: string; refresh?: boolean }) =>
      companyResearch({ name, refresh, background: true }),
  });
}
