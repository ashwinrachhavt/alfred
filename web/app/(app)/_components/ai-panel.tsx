"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";

import {
  BookmarkPlus,
  Check,
  ChevronDown,
  ClipboardCopy,
  FileInput,
  Loader2,
  Plus,
  Send,
  Settings2,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { useShallow } from "zustand/react/shallow";

import { Button } from "@/components/ui/button";
import {
  useAgentStore,
  useToolCallStore,
  selectOrderedMessages,
  PHILOSOPHICAL_LENSES,
  type AgentMessage,
  type ArtifactCard,
} from "@/lib/stores/agent-store";
import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { RelatedCards } from "@/components/agent/related-cards";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { useShellStore } from "@/lib/stores/shell-store";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const EditorDrawer = dynamic(() => import("@/components/agent/editor-drawer").then((mod) => ({ default: mod.EditorDrawer })), {
  ssr: false,
});

// --- Page-contextual suggestions ---

const SUGGESTIONS: Record<string, string[]> = {
  notes: [
    "What are the key arguments?",
    "Find related knowledge",
    "Summarize this note",
  ],
  "notes-empty": [
    "What do I know about...",
    "Find connections between...",
  ],
  default: [
    "What's new today?",
    "Summarize my recent readings",
    "Find connections between...",
  ],
};

export function AiPanel() {
  const { aiPanelOpen, toggleAiPanel } = useShellStore();
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastThreadLoadRef = useRef(0);

  useEffect(() => {
    if (!aiPanelOpen) return;
    const now = Date.now();
    if (now - lastThreadLoadRef.current > 60_000) {
      loadThreads();
      lastThreadLoadRef.current = now;
    }
    // Focus input when panel opens
    setTimeout(() => inputRef.current?.focus(), 200);
  }, [aiPanelOpen, loadThreads]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    setInput("");

    if (!activeThreadId) {
      await createThread(text.slice(0, 60));
    }

    await sendMessage(text);
  }, [input, activeThreadId, createThread, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleArtifactClick = (artifact: ArtifactCard) => {
    setEditingZettelId(artifact.id);
  };

  if (!aiPanelOpen) return null;

  const suggestions = isOnNotes
    ? noteContext
      ? SUGGESTIONS.notes
      : SUGGESTIONS["notes-empty"]
    : SUGGESTIONS.default;

  const emptyTitle = isOnNotes
    ? noteContext
      ? `Ask about "${noteContext.title}"`
      : "Select a note to get started"
    : "Ask about your knowledge";

  return (
    <>
      <aside
        role="complementary"
        aria-label="AI Assistant"
        className="flex h-full w-[380px] shrink-0 flex-col border-l bg-card"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="size-2 rounded-full bg-primary animate-pulse" />
            <button
              onClick={() => setShowThreads(!showThreads)}
              className="flex items-center gap-1 font-mono text-xs uppercase tracking-wider hover:text-foreground transition-colors"
            >
              Alfred AI
              <ChevronDown className={cn("size-3 text-muted-foreground transition-transform", showThreads && "rotate-180")} />
            </button>
          </div>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground"
              onClick={() => { clearMessages(); createThread(); }}
              aria-label="New conversation"
            >
              <Plus className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground"
              onClick={toggleAiPanel}
              aria-label="Close AI panel"
            >
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {/* Thread dropdown */}
        {showThreads && (
          <div className="border-b bg-card">
            <div className="max-h-48 overflow-y-auto py-1">
              {threads.slice(0, 5).map((thread) => (
                <button
                  key={thread.id}
                  onClick={() => {
                    useAgentStore.getState().loadThread(thread.id);
                    setShowThreads(false);
                  }}
                  className={cn(
                    "w-full text-left px-4 py-2 text-sm hover:bg-secondary transition-colors truncate",
                    thread.id === activeThreadId && "bg-secondary text-foreground",
                  )}
                >
                  {thread.title}
                </button>
              ))}
              {threads.length === 0 && (
                <p className="px-4 py-2 text-xs text-muted-foreground">No conversations yet</p>
              )}
            </div>
          </div>
        )}

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto" role="log" aria-live="polite">
          <div className="p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center pt-16 text-center">
                <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[var(--alfred-accent-subtle)]">
                  <Sparkles className="size-6 text-primary" />
                </div>
                <p className="text-sm text-muted-foreground mb-6">{emptyTitle}</p>
                <div className="flex flex-col gap-1.5 w-full max-w-[280px]">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setInput(suggestion)}
                      className="rounded-sm border px-3 py-1.5 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary hover:text-foreground text-left"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <PanelMessage
                key={msg.id}
                message={msg}
                isOnNotes={!!isOnNotes}
                onArtifactClick={handleArtifactClick}
              />
            ))}

            {/* Tool call indicator */}
            {isStreaming && activeToolCalls.some((tc) => tc.status === "pending") && (
              <div className="flex items-center gap-2 py-1">
                <Loader2 className="size-3 animate-spin text-primary" />
                <span className="text-[11px] text-muted-foreground font-mono">
                  {activeToolCalls.filter((tc) => tc.status === "pending").map((tc) => tc.tool.replace(/_/g, " ")).join(", ")}...
                </span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Lens selector */}
        {(activeLens || showSettings) && (
          <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border-t">
            {PHILOSOPHICAL_LENSES.map((l) => (
              <button
                key={l.id}
                onClick={() => setLens(activeLens === l.id ? null : l.id)}
                className={cn(
                  "rounded-full px-2.5 py-0.5 text-[10px] font-mono transition-colors border",
                  activeLens === l.id
                    ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                )}
              >
                {l.label}
              </button>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="border-t p-3">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isOnNotes && noteContext ? `Ask about ${noteContext.title}...` : "Ask about your knowledge..."}
              rows={1}
              className="flex-1 resize-none rounded-sm bg-secondary px-3 py-2 text-sm border border-[var(--border-strong)] outline-none placeholder:text-[var(--alfred-text-tertiary)] focus:border-[var(--accent)] transition-colors"
              disabled={isStreaming}
            />
            <div className="flex flex-col gap-1">
              {isStreaming ? (
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-8 text-primary"
                  onClick={cancelStream}
                  aria-label="Stop generating"
                >
                  <Square className="size-4" />
                </Button>
              ) : (
                <Button
                  size="icon"
                  className="size-8"
                  onClick={handleSend}
                  disabled={!input.trim()}
                  aria-label="Send message"
                >
                  <Send className="size-4" />
                </Button>
              )}
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="p-1 rounded text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Toggle settings"
              >
                <Settings2 className="size-3.5" />
              </button>
            </div>
          </div>
          {/* Model selector */}
          <div className="flex items-center gap-1 mt-1.5">
            <span className="text-primary text-[10px]">★</span>
            <select
              value={activeModel}
              onChange={(e) => setModel(e.target.value)}
              className="bg-transparent outline-none cursor-pointer text-[10px] font-mono text-muted-foreground"
            >
              <option value="gpt-5.4">GPT-5.4</option>
              <option value="gpt-5.4-mini">GPT-5.4 mini</option>
              <option value="gpt-5.4-pro">GPT-5.4 Pro</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="o3">o3</option>
              <option value="o4-mini">o4-mini</option>
            </select>
          </div>
        </div>
      </aside>

      {/* Editor drawer for viewing zettels */}
      <EditorDrawer
        zettelId={editingZettelId}
        onClose={() => setEditingZettelId(null)}
      />
    </>
  );
}

// --- Panel Message Component ---

function PanelMessage({
  message,
  isOnNotes,
  onArtifactClick,
}: {
  message: AgentMessage;
  isOnNotes: boolean;
  onArtifactClick: (artifact: ArtifactCard) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-secondary px-3 py-2 text-sm text-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  // Check if response already has a create_zettel artifact
  const hasCreatedZettel = message.artifacts.some((a) => a.action === "created");

  return (
    <div className="space-y-2">
      {/* Assistant text */}
      {message.content && (
        <MarkdownMessage content={message.content} />
      )}

      {/* Artifact cards */}
      {message.artifacts.length > 0 && (
        <div className="space-y-1.5">
          {message.artifacts.map((artifact) => (
            <ArtifactCardComponent
              key={`${artifact.type}-${artifact.id}`}
              artifact={artifact}
              onClick={() => onArtifactClick(artifact)}
            />
          ))}
        </div>
      )}

      {/* Related knowledge */}
      {message.relatedCards.length > 0 && (
        <RelatedCards cards={message.relatedCards} onCardClick={onArtifactClick} />
      )}

      {/* Gap chips */}
      {message.gaps.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {message.gaps.map((gap) => (
            <span
              key={gap.concept}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-[var(--alfred-accent-subtle)] text-primary"
            >
              gap: {gap.concept}
            </span>
          ))}
        </div>
      )}

      {/* Action bar — visible on hover */}
      {message.content && !message.content.startsWith("Sorry") && (
        <MessageActionBar
          message={message}
          isOnNotes={isOnNotes}
          hasCreatedZettel={hasCreatedZettel}
        />
      )}
    </div>
  );
}

// --- Action Bar ---

function MessageActionBar({
  message,
  isOnNotes,
  hasCreatedZettel,
}: {
  message: AgentMessage;
  isOnNotes: boolean;
  hasCreatedZettel: boolean;
}) {
  const [savedAsZettel, setSavedAsZettel] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleSaveAsZettel = async () => {
    if (savedAsZettel || hasCreatedZettel || saving) return;
    setSaving(true);
    try {
      await apiFetch("/api/zettels/cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: message.content.slice(0, 60).replace(/[#*_]/g, "").trim(),
          content: message.content,
          tags: [],
          topic: "",
        }),
      });
      setSavedAsZettel(true);
    } catch {
      // TODO: show error toast
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-0.5 pt-0.5 opacity-0 hover:opacity-100 transition-opacity group-hover:opacity-100">
      {/* Insert into Note — only on /notes */}
      {isOnNotes && (
        <button
          className="flex items-center gap-1 px-1.5 py-1 rounded text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Insert response into current note"
          title="Insert into Note"
        >
          <FileInput className="size-3" />
          Insert
        </button>
      )}

      {/* Save as Zettel / View Zettel */}
      <button
        onClick={handleSaveAsZettel}
        disabled={savedAsZettel || hasCreatedZettel || saving}
        className={cn(
          "flex items-center gap-1 px-1.5 py-1 rounded text-[10px] font-mono transition-colors",
          savedAsZettel || hasCreatedZettel
            ? "text-primary"
            : "text-muted-foreground hover:text-foreground",
        )}
        aria-label={savedAsZettel || hasCreatedZettel ? "View zettel" : "Save as zettel"}
        title={savedAsZettel || hasCreatedZettel ? "View Zettel" : "Save as Zettel"}
      >
        {saving ? (
          <Loader2 className="size-3 animate-spin" />
        ) : savedAsZettel || hasCreatedZettel ? (
          <Check className="size-3" />
        ) : (
          <BookmarkPlus className="size-3" />
        )}
        {savedAsZettel || hasCreatedZettel ? "Saved" : "Save"}
      </button>

      {/* Copy */}
      <button
        onClick={handleCopy}
        className={cn(
          "flex items-center gap-1 px-1.5 py-1 rounded text-[10px] font-mono transition-colors",
          copied ? "text-primary" : "text-muted-foreground hover:text-foreground",
        )}
        aria-label="Copy response"
        title="Copy"
      >
        {copied ? <Check className="size-3" /> : <ClipboardCopy className="size-3" />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
