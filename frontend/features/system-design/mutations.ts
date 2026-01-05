import { useMutation } from "@tanstack/react-query"

import { createSystemDesignSession } from "@/lib/api/system-design"
import type { SystemDesignSessionCreate } from "@/lib/api/types/system-design"

export function useCreateSystemDesignSession() {
  return useMutation({
    mutationFn: (payload: SystemDesignSessionCreate) => createSystemDesignSession(payload),
  })
}

