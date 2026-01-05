import { useQuery } from "@tanstack/react-query"

import { getTaskStatus } from "@/lib/api/tasks"

export function taskStatusQueryKey(taskId: string) {
  return ["tasks", "status", taskId] as const
}

export function useTaskStatus(taskId: string | null) {
  return useQuery({
    enabled: Boolean(taskId),
    queryKey: taskId ? taskStatusQueryKey(taskId) : ["tasks", "status", "disabled"],
    queryFn: () => getTaskStatus(taskId!),
    refetchInterval: (query) => (query.state.data?.ready ? false : 2000),
  })
}
