import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { streamSSE } from "@/lib/api/sse";

export type DocumentChatThread = {
  id: number;
  title: string | null;
  status: string;
  pinned: boolean;
  source_kind?: string | null;
  source_id?: string | null;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
};

export type DocumentChatMessage = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
};

export type DocumentThreadResponse = {
  thread: DocumentChatThread;
  messages: DocumentChatMessage[];
};

export async function listDocumentThreads(docId: string): Promise<DocumentChatThread[]> {
  const params = new URLSearchParams({
    source_kind: "document",
    source_id: docId,
  });
  return apiFetch<DocumentChatThread[]>(`${apiRoutes.agent.threads}?${params.toString()}`);
}

export async function getDocumentThread(threadId: number): Promise<DocumentThreadResponse> {
  return apiFetch<DocumentThreadResponse>(apiRoutes.agent.threadById(threadId));
}

export async function streamDocumentQuestion({
  docId,
  title,
  threadId,
  message,
  onEvent,
  signal,
}: {
  docId: string;
  title?: string | null;
  threadId?: number | null;
  message: string;
  onEvent: (event: string, data: Record<string, unknown>) => void;
  signal?: AbortSignal;
}): Promise<void> {
  await streamSSE(
    apiRoutes.agent.stream,
    {
      message,
      thread_id: threadId ?? undefined,
      source_context: {
        source_kind: "document",
        source_id: docId,
        title: title || "Document conversation",
      },
    },
    onEvent,
    signal,
  );
}
