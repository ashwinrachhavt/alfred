"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageSquareText, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  getDocumentThread,
  listDocumentThreads,
  streamDocumentQuestion,
  type DocumentChatMessage,
} from "@/lib/api/document-chat";
import { cn } from "@/lib/utils";

type Props = {
  docId: string;
  title?: string | null;
};

const threadKeys = {
  list: (docId: string) => ["document-chat", docId, "threads"] as const,
  detail: (threadId: number | null) => ["document-chat", "thread", threadId] as const,
};

function normalizeMessage(message: DocumentChatMessage): DocumentChatMessage {
  return {
    ...message,
    id: message.id,
    role: message.role,
    content: message.content || "",
  };
}

export function DocumentChatThread({ docId, title }: Props) {
  const queryClient = useQueryClient();
  const [threadId, setThreadId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<DocumentChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const threadsQuery = useQuery({
    queryKey: threadKeys.list(docId),
    queryFn: () => listDocumentThreads(docId),
    staleTime: 15_000,
  });

  useEffect(() => {
    if (!threadId && threadsQuery.data?.[0]?.id) {
      setThreadId(threadsQuery.data[0].id);
    }
  }, [threadId, threadsQuery.data]);

  const threadQuery = useQuery({
    queryKey: threadKeys.detail(threadId),
    queryFn: () => getDocumentThread(threadId!),
    enabled: Boolean(threadId),
    staleTime: 10_000,
  });

  useEffect(() => {
    if (!isStreaming && threadQuery.data?.messages) {
      setMessages(threadQuery.data.messages.map(normalizeMessage));
    }
  }, [isStreaming, threadQuery.data]);

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.content.trim()),
    [messages],
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || isStreaming) return;

    abortRef.current?.abort();
    const abortController = new AbortController();
    abortRef.current = abortController;

    const userId = `local-user-${Date.now()}`;
    const assistantId = `local-assistant-${Date.now()}`;
    setDraft("");
    setIsStreaming(true);
    setMessages((current) => [
      ...current,
      { id: userId, role: "user", content: text },
      { id: assistantId, role: "assistant", content: "" },
    ]);

    try {
      await streamDocumentQuestion({
        docId,
        title,
        threadId,
        message: text,
        signal: abortController.signal,
        onEvent: (eventName, data) => {
          if (eventName === "thread_created" && typeof data.thread_id === "number") {
            setThreadId(data.thread_id);
          }
          if (eventName === "token" && typeof data.content === "string") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + data.content }
                  : message,
              ),
            );
          }
          if (eventName === "error") {
            const fallback = typeof data.message === "string" ? data.message : "The agent could not answer.";
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId ? { ...message, content: fallback } : message,
              ),
            );
          }
        },
      });
      await queryClient.invalidateQueries({ queryKey: threadKeys.list(docId) });
      if (threadId) {
        await queryClient.invalidateQueries({ queryKey: threadKeys.detail(threadId) });
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, content: "The agent could not be reached. Please try again." }
              : message,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  return (
    <section className="not-prose mt-8 border-t border-[var(--alfred-ruled-line)] pt-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageSquareText className="size-4 text-[var(--alfred-accent)]" />
          <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Ask This Capture
          </span>
        </div>
        {(threadsQuery.isLoading || threadQuery.isFetching) && !isStreaming ? (
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
        ) : null}
      </div>

      <div className="space-y-3">
        {visibleMessages.length > 0 ? (
          visibleMessages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "max-w-[92%] whitespace-pre-wrap rounded-md border px-3 py-2 text-[13px] leading-relaxed",
                message.role === "user"
                  ? "ml-auto border-[var(--alfred-accent-muted)] bg-[var(--alfred-accent-subtle)] text-foreground"
                  : "border-[var(--alfred-ruled-line)] bg-muted/25 text-muted-foreground",
              )}
            >
              {message.content}
            </div>
          ))
        ) : (
          <p className="text-[13px] text-muted-foreground">No questions asked yet.</p>
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 flex items-end gap-2">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder="Ask a question about this source..."
          className="min-h-20 resize-none text-sm"
        />
        <Button
          type="submit"
          size="icon"
          className="size-10 shrink-0"
          disabled={!draft.trim() || isStreaming}
          title="Send"
        >
          {isStreaming ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </Button>
      </form>
    </section>
  );
}
