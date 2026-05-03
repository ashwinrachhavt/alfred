"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  AtSign,
  Brain,
  ChevronDown,
  FileText,
  Loader2,
  Maximize2,
  Minimize2,
  Plus,
  Search,
  Send,
  Settings2,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { Button } from "@/components/ui/button";
import { useLocalStorageString } from "@/lib/hooks/use-local-storage-value";
import { searchChatOmnibox, type OmniboxResult } from "@/lib/api/chat-omnibox";
import { getDocumentDetails } from "@/lib/api/documents";
import { getZettelCard } from "@/lib/api/zettels";
import {
  useAgentStore,
  useToolCallStore,
  selectOrderedMessages,
  PHILOSOPHICAL_LENSES,
  type AgentMessage,
  type ArtifactCard,
} from "@/lib/stores/agent-store";
import { useShellStore, type ChatMode } from "@/lib/stores/shell-store";
import {
  MessageBubble,
  type ResponseComment,
  type ResponseCommentTarget,
} from "@/components/chat/message-bubble";
import { useStickToBottom } from "@/lib/hooks/use-stick-to-bottom";
import { DEFAULT_AI_MODEL } from "@/lib/constants/ai";
import { cn } from "@/lib/utils";

const EditorDrawer = dynamic(
  () =>
    import("@/components/agent/editor-drawer").then((mod) => ({
      default: mod.EditorDrawer,
    })),
  { ssr: false },
);

// --- Page-contextual suggestions ---

const SUGGESTIONS: Record<string, string[]> = {
  notes: [
    "What are the key arguments?",
    "Find related knowledge",
    "Summarize this note",
    "Quiz me on this topic",
  ],
  "notes-empty": [
    "What do I know about...",
    "Find connections between...",
    "What happened in tech news today?",
  ],
  default: [
    "What do I know about...",
    "Search the web for...",
    "Quiz me on my philosophy cards",
    "Find recent papers on...",
    "Draft a zettel comparing...",
    "What happened in tech news today?",
  ],
};

type ResponseCommentsByMessageId = Record<string, ResponseComment[]>;

type AttachedChatContext =
  | {
      kind: "zettel";
      id: number;
      title: string;
      content: string | null;
      summary: string | null;
      topic: string | null;
      tags: string[] | null;
    }
  | {
      kind: "document";
      id: string;
      title: string;
      cleanedText: string;
      summary: unknown;
      sourceUrl: string | null;
      topics: unknown;
    };

type OmniboxMentionMatch = {
  query: string;
  start: number;
  end: number;
};

function buildResponseCommentsStorageKey(threadId: number | null): string {
  return `alfred:chat:response-comments:${threadId ?? "draft"}`;
}

function findOmniboxMention(input: string): OmniboxMentionMatch | null {
  const matches = Array.from(input.matchAll(/(^|\s)@([^\s@]{0,80})/g));
  const match = matches.at(-1);
  if (!match || match.index === undefined) return null;

  const prefix = match[1] ?? "";
  const query = match[2] ?? "";

  const start = match.index + prefix.length;
  return {
    query,
    start,
    end: start + query.length + 1,
  };
}

function removeMentionToken(input: string, match: OmniboxMentionMatch): string {
  return `${input.slice(0, match.start)}${input.slice(match.end)}`
    .replace(/\s{2,}/g, " ")
    .trim();
}

function removeMentionTokenIfCurrent(input: string, match: OmniboxMentionMatch): string {
  if (input.slice(match.start, match.end) !== `@${match.query}`) return input;
  return removeMentionToken(input, match);
}

function chatContextKey(context: Pick<AttachedChatContext, "kind" | "id">): string {
  return `${context.kind}:${context.id}`;
}

function stringifyContextValue(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value === "string") return value.trim() || null;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function buildChatContextPrompt(userText: string, contexts: AttachedChatContext[]): string {
  if (contexts.length === 0) return userText;

  const context = contexts
    .map((item) => {
      const body =
        item.kind === "zettel"
          ? (item.summary || item.content || "").replace(/\s+/g, " ").trim()
          : item.cleanedText.replace(/\s+/g, " ").trim();
      const excerpt = body.length > 700 ? `${body.slice(0, 697)}...` : body;
      const metadata =
        item.kind === "zettel"
          ? [
              item.topic ? `Topic: ${item.topic}` : null,
              item.tags?.length ? `Tags: ${item.tags.join(", ")}` : null,
            ]
              .filter(Boolean)
              .join(" | ")
          : [
              item.sourceUrl ? `Source: ${item.sourceUrl}` : null,
              stringifyContextValue(item.summary)
                ? `Summary: ${stringifyContextValue(item.summary)}`
                : null,
              stringifyContextValue(item.topics) ? `Topics: ${stringifyContextValue(item.topics)}` : null,
            ]
              .filter(Boolean)
              .join(" | ");

      return [
        `${item.kind === "zettel" ? "Zettel" : "Document"} [${item.id}] ${item.title}`,
        metadata,
        excerpt ? `Excerpt: ${excerpt}` : null,
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n\n");

  return [
    userText,
    "",
    "Referenced Polymath context:",
    context,
    "",
    "Use the referenced Polymath context as explicit chat context. Do not assume it is the only relevant knowledge.",
  ].join("\n");
}

function parseResponseComments(raw: string): ResponseCommentsByMessageId {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed as ResponseCommentsByMessageId;
  } catch {
    return {};
  }
}

function buildResponseCommentsPrompt(
  message: { content: string },
  comments: ResponseComment[],
): string {
  const formattedComments = comments
    .map((comment, index) => {
      const blockContext = comment.blockPreview
        ? [`On markdown block:`, `> ${comment.blockPreview}`, ""].join("\n")
        : "";

      return [`Comment ${index + 1}:`, blockContext, comment.body].filter(Boolean).join("\n");
    })
    .join("\n");

  return [
    "Reply to the review comments on your previous response.",
    "Treat these like GitHub PR or Notion comments: answer each comment, revise your position if needed, and call out any concrete actions you would take.",
    "",
    "Original AI response being reviewed:",
    "```markdown",
    message.content,
    "```",
    "",
    "Comments:",
    formattedComments,
  ].join("\n");
}

// --- UnifiedChat ---

export function UnifiedChat({ mode }: { mode: ChatMode }) {
  const { aiPanelOpen, toggleAiPanel, toggleChatExpanded } = useShellStore();
  const {
    messagesById,
    messageOrder,
    threads,
    activeThreadId,
    isStreaming,
    activeLens,
    activeModel,
    noteContext,
    sendMessage,
    cancelStream,
    setLens,
    setModel,
    loadThreads,
    createThread,
    clearMessages,
  } = useAgentStore(
    useShallow((s) => ({
      messagesById: s.messagesById,
      messageOrder: s.messageOrder,
      threads: s.threads,
      activeThreadId: s.activeThreadId,
      isStreaming: s.isStreaming,
      activeLens: s.activeLens,
      activeModel: s.activeModel,
      noteContext: s.noteContext,
      sendMessage: s.sendMessage,
      cancelStream: s.cancelStream,
      setLens: s.setLens,
      setModel: s.setModel,
      loadThreads: s.loadThreads,
      createThread: s.createThread,
      clearMessages: s.clearMessages,
    })),
  );

  const messages = useMemo(
    () => selectOrderedMessages({ messagesById, messageOrder }),
    [messagesById, messageOrder],
  );

  const { activeToolCalls } = useToolCallStore(
    useShallow((s) => ({ activeToolCalls: s.activeToolCalls })),
  );

  const pathname = usePathname();
  const isOnNotes = pathname?.startsWith("/notes");

  const [input, setInput] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showThreads, setShowThreads] = useState(false);
  const [editingZettelId, setEditingZettelId] = useState<number | null>(null);
  const [attachedContext, setAttachedContext] = useState<AttachedChatContext[]>([]);
  const [dismissedOmniboxToken, setDismissedOmniboxToken] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastThreadLoadRef = useRef(0);
  const queryClient = useQueryClient();
  const {
    containerRef: messagesContainerRef,
    endRef: messagesEndRef,
    maybeScrollToBottom,
    scrollToBottom,
  } = useStickToBottom();

  const isSidebar = mode === "sidebar";
  const commentsStorageKey = useMemo(
    () => buildResponseCommentsStorageKey(activeThreadId),
    [activeThreadId],
  );
  const [responseCommentsRaw, setResponseCommentsRaw] = useLocalStorageString(
    commentsStorageKey,
    "{}",
  );

  const omniboxMention = useMemo(() => findOmniboxMention(input), [input]);
  const omniboxMentionToken = omniboxMention
    ? `${omniboxMention.start}:${omniboxMention.end}:${omniboxMention.query}`
    : null;
  const isOmniboxDismissed =
    omniboxMentionToken !== null && omniboxMentionToken === dismissedOmniboxToken;
  const isOmniboxQueryEnabled = !!omniboxMention && !isStreaming && !isOmniboxDismissed;
  const omniboxSearch = useQuery({
    queryKey: ["chat-omnibox", omniboxMention?.query ?? ""],
    queryFn: () => searchChatOmnibox(omniboxMention?.query ?? "", 8),
    enabled: isOmniboxQueryEnabled,
    staleTime: 30_000,
  });

  const omniboxRows = useMemo<OmniboxResult[]>(() => {
    const response = omniboxSearch.data;
    if (!response || !omniboxMention || isOmniboxDismissed) return [];
    const selectedContext = new Set(attachedContext.map(chatContextKey));
    return response.results
      .filter((row) => row.kind === "action" || !selectedContext.has(chatContextKey(row)))
      .slice(0, 8);
  }, [attachedContext, isOmniboxDismissed, omniboxMention, omniboxSearch.data]);

  const commentsByMessageId = useMemo(
    () => parseResponseComments(responseCommentsRaw),
    [responseCommentsRaw],
  );

  const handleInputChange = useCallback((value: string) => {
    setInput(value);
    setDismissedOmniboxToken(null);
  }, []);

  const handleSelectOmniboxResult = useCallback(
    async (row: OmniboxResult) => {
      if (!omniboxMention) return;
      const selectedMention = omniboxMention;

      if (row.kind === "action") {
        const instruction =
          row.action === "search_all"
            ? `Search all knowledge for ${row.query}`
            : `Create a card from ${row.query}`;

        setInput((current) =>
          [removeMentionTokenIfCurrent(current, selectedMention), instruction]
            .filter(Boolean)
            .join(" "),
        );
        setDismissedOmniboxToken(null);
        requestAnimationFrame(() => inputRef.current?.focus());
        return;
      }

      if (row.kind === "zettel") {
        const card = await queryClient.fetchQuery({
          queryKey: ["zettels", "card", "raw", row.id],
          queryFn: () => getZettelCard(row.id),
          staleTime: 60_000,
        });

        setAttachedContext((current) =>
          current.some((context) => context.kind === "zettel" && context.id === card.id)
            ? current
            : [
                ...current,
                {
                  kind: "zettel",
                  id: card.id,
                  title: card.title,
                  content: card.content,
                  summary: card.summary,
                  topic: card.topic,
                  tags: card.tags,
                },
            ],
        );
        setInput((current) => removeMentionTokenIfCurrent(current, selectedMention));
        setDismissedOmniboxToken(null);
        requestAnimationFrame(() => inputRef.current?.focus());
        return;
      }

      const document = await queryClient.fetchQuery({
        queryKey: ["documents", "details", row.id],
        queryFn: () => getDocumentDetails(row.id),
        staleTime: 60_000,
      });

      setAttachedContext((current) =>
        current.some((context) => context.kind === "document" && context.id === document.id)
          ? current
          : [
              ...current,
              {
                kind: "document",
                id: document.id,
                title: document.title ?? row.title,
                cleanedText: document.cleaned_text,
                summary: document.summary ?? null,
                sourceUrl: document.source_url ?? document.canonical_url ?? null,
                topics: document.topics ?? null,
              },
            ],
      );
      setInput((current) => removeMentionTokenIfCurrent(current, selectedMention));
      setDismissedOmniboxToken(null);
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [omniboxMention, queryClient],
  );

  const handleCloseOmnibox = useCallback(() => {
    if (omniboxMentionToken) setDismissedOmniboxToken(omniboxMentionToken);
  }, [omniboxMentionToken]);

  const handleRemoveAttachedContext = useCallback((contextKey: string) => {
    setAttachedContext((current) =>
      current.filter((context) => chatContextKey(context) !== contextKey),
    );
  }, []);

  // Load threads on mount/open
  useEffect(() => {
    if (isSidebar && !aiPanelOpen) return;
    const now = Date.now();
    if (now - lastThreadLoadRef.current > 60_000) {
      loadThreads();
      lastThreadLoadRef.current = now;
    }
    setTimeout(() => inputRef.current?.focus(), 200);
  }, [aiPanelOpen, isSidebar, loadThreads]);

  useEffect(() => {
    if (messages.length === 0) return;
    maybeScrollToBottom(isStreaming ? "auto" : "smooth");
  }, [messages, isStreaming, maybeScrollToBottom]);

  useEffect(() => {
    if (isSidebar && !aiPanelOpen) return;
    requestAnimationFrame(() => {
      scrollToBottom("auto");
    });
  }, [activeThreadId, aiPanelOpen, isSidebar, scrollToBottom]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    setAttachedContext([]);
    setDismissedOmniboxToken(null);
    scrollToBottom("smooth");

    if (!activeThreadId) {
      await createThread(text.slice(0, 60));
    }
    await sendMessage(buildChatContextPrompt(text, attachedContext), { displayText: text });
  }, [input, activeThreadId, attachedContext, createThread, scrollToBottom, sendMessage]);

  const handleAddResponseComment = useCallback(
    (messageId: string, body: string, target: ResponseCommentTarget) => {
      const trimmed = body.trim();
      if (!trimmed) return;

      const comment: ResponseComment = {
        id: `${messageId}-${Date.now()}`,
        body: trimmed,
        createdAt: Date.now(),
        blockId: target.blockId,
        blockPreview: target.blockPreview,
      };

      setResponseCommentsRaw((currentRaw) => {
        const currentThreadComments = parseResponseComments(currentRaw);

        return JSON.stringify({
          ...currentThreadComments,
          [messageId]: [...(currentThreadComments[messageId] ?? []), comment],
        });
      });
    },
    [setResponseCommentsRaw],
  );

  const handleReplyToResponseComments = useCallback(
    async (message: AgentMessage) => {
      const comments = commentsByMessageId[message.id] ?? [];
      if (comments.length === 0) return;

      const text = buildResponseCommentsPrompt(message, comments);
      scrollToBottom("smooth");

      if (!activeThreadId) {
        await createThread("Response comments");
      }
      await sendMessage(text);
    },
    [activeThreadId, commentsByMessageId, createThread, scrollToBottom, sendMessage],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleViewZettel = useCallback((zettelId: number) => {
    const shell = useShellStore.getState();
    shell.setChatMode("sidebar");
    shell.openZettelViewer(zettelId);
    setEditingZettelId(null);
  }, []);

  const handleArtifactClick = useCallback(
    (artifact: ArtifactCard) => {
      if (artifact.type !== "zettel") return;
      if (mode === "expanded") {
        handleViewZettel(artifact.id);
        return;
      }
      setEditingZettelId(artifact.id);
    },
    [handleViewZettel, mode],
  );

  // Determine suggestions and empty state text
  const suggestions = isOnNotes
    ? noteContext
      ? SUGGESTIONS.notes
      : SUGGESTIONS["notes-empty"]
    : SUGGESTIONS.default;

  const emptyTitle = isSidebar
    ? isOnNotes
      ? noteContext
        ? `Ask about "${noteContext.title}"`
        : "Select a note to get started"
      : "Ask about your knowledge"
    : "What would you like to explore?";

  const activeThread = threads.find((t) => t.id === activeThreadId);

  // --- Sidebar: hide when panel is closed ---
  if (isSidebar && !aiPanelOpen) return null;

  return (
    <>
      <div
        role={isSidebar ? "complementary" : "main"}
        aria-label="AI Assistant"
        className={cn(
          "flex flex-col",
          isSidebar ? "bg-card h-full w-[380px] shrink-0 border-l" : "h-full flex-1",
        )}
      >
        {/* ---- Header ---- */}
        {isSidebar ? (
          <SidebarHeader
            showThreads={showThreads}
            setShowThreads={setShowThreads}
            onNewConversation={() => {
              clearMessages();
              createThread();
            }}
            onClose={toggleAiPanel}
            onExpand={toggleChatExpanded}
          />
        ) : (
          <ExpandedHeader
            activeThread={activeThread ?? null}
            onNewConversation={() => {
              clearMessages();
              createThread();
            }}
            onCollapse={toggleChatExpanded}
            onToggleThreads={() => setShowThreads((v) => !v)}
          />
        )}

        {/* ---- Thread dropdown ---- */}
        {showThreads && (
          <div className="bg-card border-b">
            <div className="max-h-48 overflow-y-auto py-1">
              {threads.slice(0, 5).map((thread) => (
                <button
                  key={thread.id}
                  onClick={() => {
                    useAgentStore.getState().loadThread(thread.id);
                    setShowThreads(false);
                  }}
                  className={cn(
                    "hover:bg-secondary w-full truncate px-4 py-2 text-left text-sm transition-colors",
                    thread.id === activeThreadId && "bg-secondary text-foreground",
                  )}
                >
                  {thread.title}
                </button>
              ))}
              {threads.length === 0 && (
                <p className="text-muted-foreground px-4 py-2 text-xs">No conversations yet</p>
              )}
            </div>
          </div>
        )}

        {/* ---- Messages area ---- */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto"
          role="log"
          aria-live="polite"
        >
          <div
            className={cn(isSidebar ? "space-y-4 p-4" : "mx-auto max-w-3xl space-y-6 px-6 py-6")}
          >
            {/* Empty state */}
            {messages.length === 0 && (
              <EmptyState
                mode={mode}
                title={emptyTitle}
                description={
                  !isSidebar
                    ? "Ask anything. Polymath can search your knowledge, research the web, create cards, run quizzes, find connections, and just chat."
                    : undefined
                }
                suggestions={suggestions}
                onSuggestionClick={setInput}
              />
            )}

            {/* Messages */}
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                mode={mode}
                isOnNotes={!!isOnNotes}
                responseComments={commentsByMessageId[msg.id] ?? []}
                onAddResponseComment={handleAddResponseComment}
                onReplyToResponseComments={handleReplyToResponseComments}
                onArtifactClick={handleArtifactClick}
                onViewZettel={handleViewZettel}
              />
            ))}

            {/* Active tool call indicator */}
            {isStreaming && activeToolCalls.some((tc) => tc.status === "pending") && (
              <div className="flex items-center gap-2 py-1">
                <Loader2
                  className={cn("text-primary animate-spin", isSidebar ? "size-3" : "size-3.5")}
                />
                <span
                  className={cn("text-muted-foreground", isSidebar ? "text-[11px]" : "text-xs")}
                >
                  {activeToolCalls
                    .filter((tc) => tc.status === "pending")
                    .map((tc) => tc.tool.replace(/_/g, " "))
                    .join(", ")}
                  ...
                </span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* ---- Lens selector ---- */}
        {(activeLens || showSettings) && (
          <div
            className={cn(
              "flex flex-wrap items-center gap-1.5 border-t",
              isSidebar ? "px-3 py-2" : "mx-auto w-full max-w-3xl px-6 py-3",
            )}
          >
            {PHILOSOPHICAL_LENSES.map((l) => (
              <button
                key={l.id}
                onClick={() => setLens(activeLens === l.id ? null : l.id)}
                className={cn(
                  "rounded-full border transition-colors",
                  isSidebar ? "px-2.5 py-0.5 text-[10px]" : "px-3 py-1 text-[11px]",
                  activeLens === l.id
                    ? "border-primary text-primary bg-[var(--alfred-accent-subtle)]"
                    : "text-muted-foreground hover:border-border hover:text-foreground border-transparent",
                )}
              >
                {l.label}
              </button>
            ))}
          </div>
        )}

        {/* ---- Input area ---- */}
        {isSidebar ? (
          <SidebarInput
            ref={inputRef}
            input={input}
            setInput={handleInputChange}
            isStreaming={isStreaming}
            activeModel={activeModel}
            isOnNotes={!!isOnNotes}
            noteContext={noteContext}
            attachedContext={attachedContext}
            omniboxRows={omniboxRows}
            isOmniboxOpen={isOmniboxQueryEnabled}
            isOmniboxLoading={isOmniboxQueryEnabled && omniboxSearch.isFetching}
            onSelectOmniboxResult={handleSelectOmniboxResult}
            onCloseOmnibox={handleCloseOmnibox}
            onRemoveAttachedContext={handleRemoveAttachedContext}
            showSettings={showSettings}
            onToggleSettings={() => setShowSettings(!showSettings)}
            onSend={handleSend}
            onCancel={cancelStream}
            onKeyDown={handleKeyDown}
            onModelChange={setModel}
          />
        ) : (
          <ExpandedInput
            ref={inputRef}
            input={input}
            setInput={handleInputChange}
            isStreaming={isStreaming}
            activeModel={activeModel}
            attachedContext={attachedContext}
            omniboxRows={omniboxRows}
            isOmniboxOpen={isOmniboxQueryEnabled}
            isOmniboxLoading={isOmniboxQueryEnabled && omniboxSearch.isFetching}
            onSelectOmniboxResult={handleSelectOmniboxResult}
            onCloseOmnibox={handleCloseOmnibox}
            onRemoveAttachedContext={handleRemoveAttachedContext}
            showSettings={showSettings}
            onToggleSettings={() => setShowSettings(!showSettings)}
            onSend={handleSend}
            onCancel={cancelStream}
            onKeyDown={handleKeyDown}
            onModelChange={setModel}
          />
        )}
      </div>

      {/* Editor drawer for viewing zettels */}
      <EditorDrawer zettelId={editingZettelId} onClose={() => setEditingZettelId(null)} />
    </>
  );
}

// --- Sub-components ---

function SidebarHeader({
  showThreads,
  setShowThreads,
  onNewConversation,
  onClose,
  onExpand,
}: {
  showThreads: boolean;
  setShowThreads: (v: boolean) => void;
  onNewConversation: () => void;
  onClose: () => void;
  onExpand: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b px-4 py-2.5">
      <div className="flex items-center gap-2">
        <div className="bg-primary size-2 animate-pulse rounded-full" />
        <button
          onClick={() => setShowThreads(!showThreads)}
          className="hover:text-foreground flex items-center gap-1 text-xs tracking-wider uppercase transition-colors"
        >
          Polymath AI
          <ChevronDown
            className={cn(
              "text-muted-foreground size-3 transition-transform",
              showThreads && "rotate-180",
            )}
          />
        </button>
      </div>
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground size-8"
          onClick={onExpand}
          aria-label="Expand chat"
        >
          <Maximize2 className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground size-8"
          onClick={onNewConversation}
          aria-label="New conversation"
        >
          <Plus className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground size-8"
          onClick={onClose}
          aria-label="Close AI panel"
        >
          <X className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function ExpandedHeader({
  activeThread,
  onNewConversation,
  onCollapse,
  onToggleThreads,
}: {
  activeThread: { id: number; title: string } | null;
  onNewConversation: () => void;
  onCollapse: () => void;
  onToggleThreads: () => void;
}) {
  return (
    <div className="flex items-center gap-2 border-b px-6 py-2">
      <button
        onClick={onToggleThreads}
        className="hover:bg-secondary flex items-center gap-2 rounded-md px-2 py-1 transition-colors"
      >
        <span className="text-[10px] font-medium tracking-wider text-[var(--alfred-text-tertiary)] uppercase">
          Polymath AI
        </span>
        {activeThread && (
          <>
            <span className="text-[var(--alfred-text-tertiary)]">/</span>
            <span className="text-foreground max-w-xs min-w-0 truncate text-sm">
              {activeThread.title}
            </span>
          </>
        )}
        <ChevronDown className="text-muted-foreground size-3" />
      </button>
      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground h-7 gap-1.5 text-[10px] font-medium tracking-wider uppercase"
          onClick={onNewConversation}
        >
          <Plus className="size-3.5" />
          New
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground size-7"
          onClick={onCollapse}
          aria-label="Collapse to sidebar"
        >
          <Minimize2 className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function EmptyState({
  mode,
  title,
  description,
  suggestions,
  onSuggestionClick,
}: {
  mode: ChatMode;
  title: string;
  description?: string;
  suggestions: string[];
  onSuggestionClick: (s: string) => void;
}) {
  const isSidebar = mode === "sidebar";

  return (
    <div className={cn("flex flex-col items-center text-center", isSidebar ? "pt-16" : "pt-24")}>
      <div
        className={cn(
          "flex items-center justify-center rounded-full bg-[var(--alfred-accent-subtle)]",
          isSidebar ? "mb-4 size-12" : "mb-5 size-14",
        )}
      >
        {isSidebar ? (
          <Sparkles className="text-primary size-6" />
        ) : (
          <Brain className="text-primary size-7" />
        )}
      </div>

      {isSidebar ? (
        <p className="text-muted-foreground mb-6 text-sm">{title}</p>
      ) : (
        <>
          <h2 className="text-foreground mb-2 text-2xl">{title}</h2>
          {description && (
            <p className="text-muted-foreground mb-8 max-w-sm text-sm">{description}</p>
          )}
        </>
      )}

      <div
        className={cn(
          isSidebar
            ? "flex w-full max-w-[280px] flex-col gap-1.5"
            : "flex flex-wrap justify-center gap-2",
        )}
      >
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSuggestionClick(suggestion)}
            className={cn(
              "text-muted-foreground hover:border-primary hover:text-foreground text-left transition-colors",
              isSidebar
                ? "rounded-sm border px-3 py-1.5 text-[11px]"
                : "rounded-full border px-4 py-2 text-[13px]",
            )}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

// --- Input components ---

import { forwardRef } from "react";
import type { NoteContext } from "@/lib/stores/agent-store";

type InputProps = {
  input: string;
  setInput: (v: string) => void;
  isStreaming: boolean;
  activeModel: string;
  attachedContext: AttachedChatContext[];
  omniboxRows: OmniboxResult[];
  isOmniboxOpen: boolean;
  isOmniboxLoading: boolean;
  showSettings: boolean;
  onSelectOmniboxResult: (row: OmniboxResult) => void | Promise<void>;
  onCloseOmnibox: () => void;
  onRemoveAttachedContext: (contextKey: string) => void;
  onToggleSettings: () => void;
  onSend: () => void;
  onCancel: () => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onModelChange: (model: string) => void;
};

const MODEL_OPTIONS = [
  { value: DEFAULT_AI_MODEL, label: "GPT-5.5" },
  { value: "gpt-5.4", label: "GPT-5.4" },
  { value: "gpt-5.4-mini", label: "GPT-5.4 mini" },
  { value: "gpt-5.4-pro", label: "GPT-5.4 Pro" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "o3", label: "o3" },
  { value: "o4-mini", label: "o4-mini" },
];

function ChatContextChips({
  attachedContext,
  onRemove,
}: {
  attachedContext: AttachedChatContext[];
  onRemove: (contextKey: string) => void;
}) {
  if (attachedContext.length === 0) return null;

  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {attachedContext.map((context) => (
        <span
          key={chatContextKey(context)}
          className="inline-flex max-w-full items-center gap-1.5 rounded-sm border border-[var(--border-strong)] bg-[var(--alfred-accent-subtle)] px-2 py-1 text-[11px] text-foreground"
        >
          {context.kind === "zettel" ? (
            <AtSign className="text-primary size-3 shrink-0" />
          ) : (
            <FileText className="text-primary size-3 shrink-0" />
          )}
          <span className="text-[var(--alfred-text-tertiary)]">{context.kind}</span>
          <span className="truncate">{context.title}</span>
          <button
            type="button"
            onClick={() => onRemove(chatContextKey(context))}
            className="text-muted-foreground hover:text-foreground"
            aria-label={`Remove ${context.title} context`}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
    </div>
  );
}

function OmniboxIcon({ row }: { row: OmniboxResult }) {
  if (row.kind === "document") return <FileText className="text-primary size-3 shrink-0" />;
  if (row.kind === "action") return <Search className="text-primary size-3 shrink-0" />;
  return <AtSign className="text-primary size-3 shrink-0" />;
}

function omniboxRowMeta(row: OmniboxResult): string {
  if (row.kind === "action") return row.description;

  return [
    row.kind,
    row.topic,
    row.tags?.length ? row.tags.slice(0, 3).join(", ") : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

function OmniboxPicker({
  rows,
  loading,
  open,
  onSelect,
}: {
  rows: OmniboxResult[];
  loading: boolean;
  open: boolean;
  onSelect: (row: OmniboxResult) => void | Promise<void>;
}) {
  if (!open || (!loading && rows.length === 0)) return null;

  return (
    <div
      id="polymath-omnibox-listbox"
      role="listbox"
      aria-label="Polymath context search"
      className="bg-popover absolute right-0 bottom-full left-0 z-50 mb-2 max-h-56 overflow-y-auto rounded-md border border-[var(--border-strong)] shadow-lg"
    >
      {loading && rows.length === 0 ? (
        <div className="text-muted-foreground flex items-center gap-2 px-3 py-2 text-xs">
          <Loader2 className="size-3 animate-spin" />
          Searching Polymath
        </div>
      ) : (
        rows.map((row) => (
          <button
            key={`${row.kind}-${row.id}`}
            id={`polymath-omnibox-option-${row.kind}-${row.id}`}
            type="button"
            role="option"
            aria-selected={false}
            aria-label={`${row.title} ${row.kind}`}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onSelect(row)}
            className="hover:bg-secondary flex w-full items-center gap-2 px-3 py-2 text-left transition-colors"
          >
            <OmniboxIcon row={row} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs text-foreground">{row.title}</span>
              <span className="text-muted-foreground block truncate text-[10px]">
                {omniboxRowMeta(row)}
              </span>
            </span>
          </button>
        ))
      )}
    </div>
  );
}

const SidebarInput = forwardRef<
  HTMLTextAreaElement,
  InputProps & {
    isOnNotes: boolean;
    noteContext: NoteContext | null;
  }
>(function SidebarInput(
  {
    input,
    setInput,
    isStreaming,
    activeModel,
    isOnNotes,
    noteContext,
    attachedContext,
    omniboxRows,
    isOmniboxOpen,
    isOmniboxLoading,
    onSend,
    onCancel,
    onKeyDown,
    onSelectOmniboxResult,
    onCloseOmnibox,
    onRemoveAttachedContext,
    onModelChange,
    onToggleSettings,
  },
  ref,
) {
  const handleInputKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape" && isOmniboxOpen) {
      event.preventDefault();
      onCloseOmnibox();
      return;
    }
    if (event.key === "Enter" && !event.shiftKey && isOmniboxOpen && omniboxRows.length > 0) {
      event.preventDefault();
      void onSelectOmniboxResult(omniboxRows[0]);
      return;
    }
    onKeyDown(event);
  };

  return (
    <div className="border-t p-3">
      <ChatContextChips
        attachedContext={attachedContext}
        onRemove={onRemoveAttachedContext}
      />
      <div className="relative flex gap-2">
        <OmniboxPicker
          rows={omniboxRows}
          loading={isOmniboxLoading}
          open={isOmniboxOpen}
          onSelect={onSelectOmniboxResult}
        />
        <textarea
          ref={ref}
          role="combobox"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleInputKeyDown}
          aria-autocomplete="list"
          aria-controls={isOmniboxOpen ? "polymath-omnibox-listbox" : undefined}
          aria-expanded={isOmniboxOpen}
          aria-haspopup="listbox"
          placeholder={
            isOnNotes && noteContext
              ? `Ask about ${noteContext.title}...`
              : "Ask about your knowledge..."
          }
          rows={1}
          className="bg-secondary flex-1 resize-none rounded-sm border border-[var(--border-strong)] px-3 py-2 text-sm transition-colors outline-none placeholder:text-[var(--alfred-text-tertiary)] focus:border-[var(--accent)]"
          disabled={isStreaming}
        />
        <div className="flex flex-col gap-1">
          {isStreaming ? (
            <Button
              size="icon"
              variant="ghost"
              className="text-primary size-8"
              onClick={onCancel}
              aria-label="Stop generating"
            >
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="size-8"
              onClick={onSend}
              disabled={!input.trim()}
              aria-label="Send message"
            >
              <Send className="size-4" />
            </Button>
          )}
          <button
            onClick={onToggleSettings}
            className="text-muted-foreground hover:text-foreground rounded p-1 transition-colors"
            aria-label="Toggle settings"
          >
            <Settings2 className="size-3.5" />
          </button>
        </div>
      </div>
      <div className="mt-1.5 flex items-center gap-1">
        <span className="text-primary text-[10px]">&#9733;</span>
        <select
          value={activeModel}
          onChange={(e) => onModelChange(e.target.value)}
          className="text-muted-foreground cursor-pointer bg-transparent text-[10px] outline-none"
        >
          {MODEL_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
});

const ExpandedInput = forwardRef<HTMLTextAreaElement, InputProps>(function ExpandedInput(
  {
    input,
    setInput,
    isStreaming,
    activeModel,
    attachedContext,
    omniboxRows,
    isOmniboxOpen,
    isOmniboxLoading,
    onSend,
    onCancel,
    onKeyDown,
    onSelectOmniboxResult,
    onCloseOmnibox,
    onRemoveAttachedContext,
    onModelChange,
    onToggleSettings,
  },
  ref,
) {
  const handleInputKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape" && isOmniboxOpen) {
      event.preventDefault();
      onCloseOmnibox();
      return;
    }
    if (event.key === "Enter" && !event.shiftKey && isOmniboxOpen && omniboxRows.length > 0) {
      event.preventDefault();
      void onSelectOmniboxResult(omniboxRows[0]);
      return;
    }
    onKeyDown(event);
  };

  return (
    <div className="border-t">
      <div className="mx-auto max-w-3xl px-6 py-4">
        <ChatContextChips
          attachedContext={attachedContext}
          onRemove={onRemoveAttachedContext}
        />
        <div className="bg-card focus-within:border-primary relative flex items-end gap-0 rounded-xl border shadow-sm transition-colors">
          <OmniboxPicker
            rows={omniboxRows}
            loading={isOmniboxLoading}
            open={isOmniboxOpen}
            onSelect={onSelectOmniboxResult}
          />
          <textarea
            ref={ref}
            role="combobox"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleInputKeyDown}
            aria-autocomplete="list"
            aria-controls={isOmniboxOpen ? "polymath-omnibox-listbox" : undefined}
            aria-expanded={isOmniboxOpen}
            aria-haspopup="listbox"
            placeholder="Do anything with AI..."
            rows={1}
            className="placeholder:text-muted-foreground flex-1 resize-none bg-transparent px-4 py-3 text-sm outline-none"
          />
          <div className="flex items-center gap-1 px-2 py-2">
            <button
              onClick={onToggleSettings}
              className="text-muted-foreground hover:text-foreground rounded-md p-1.5 transition-colors"
            >
              <Settings2 className="size-4" />
            </button>
            <button className="text-muted-foreground hover:text-foreground flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-colors">
              <span className="text-primary">&#9733;</span>
              <select
                value={activeModel}
                onChange={(e) => onModelChange(e.target.value)}
                className="cursor-pointer bg-transparent text-[11px] outline-none"
              >
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </button>
            {isStreaming ? (
              <button
                onClick={onCancel}
                className="text-primary rounded-md p-1.5 transition-colors hover:bg-[var(--alfred-accent-subtle)]"
              >
                <Square className="size-4" />
              </button>
            ) : (
              <button
                onClick={onSend}
                disabled={!input.trim()}
                className={cn(
                  "rounded-md p-1.5 transition-colors",
                  input.trim()
                    ? "text-primary hover:bg-[var(--alfred-accent-subtle)]"
                    : "text-muted-foreground/40 cursor-not-allowed",
                )}
              >
                <Send className="size-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
