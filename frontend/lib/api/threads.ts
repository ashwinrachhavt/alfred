import { apiFetch, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  AppendThreadMessageRequest,
  CreateThreadRequest,
  Thread,
  ThreadMessage,
} from "@/lib/api/types/threads";

export function listThreads(): Promise<Thread[]> {
  return apiFetch<Thread[]>(apiRoutes.threads.list, { cache: "no-store" });
}

export function createThread(payload: CreateThreadRequest): Promise<Thread> {
  return apiPostJson<Thread, CreateThreadRequest>(apiRoutes.threads.create, payload, {
    cache: "no-store",
  });
}

export function listThreadMessages(threadId: string): Promise<ThreadMessage[]> {
  return apiFetch<ThreadMessage[]>(apiRoutes.threads.messages(threadId), { cache: "no-store" });
}

export function appendThreadMessage(
  threadId: string,
  payload: AppendThreadMessageRequest,
): Promise<ThreadMessage> {
  return apiPostJson<ThreadMessage, AppendThreadMessageRequest>(
    apiRoutes.threads.messages(threadId),
    payload,
    { cache: "no-store" },
  );
}
