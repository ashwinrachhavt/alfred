"use client";

import { memo, useState } from "react";

import {
  BookmarkPlus,
  Check,
  ChevronRight,
  ClipboardCopy,
  FileInput,
  Loader2,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";

import type { ChatMode } from "@/lib/stores/shell-store";
import type { AgentMessage, ArtifactCard } from "@/lib/stores/agent-store";
import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { RelatedCards } from "@/components/agent/related-cards";
import { InsightToCard } from "@/components/agent/insight-to-card";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";

// --- Reasoning Trace ---

function ReasoningTrace({ reasoning }: { reasoning: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronRight
          className={cn("size-3 transition-transform", open && "rotate-90")}
        />
        <span className="uppercase tracking-wider">Thinking</span>
      </button>
      {open && (
        <div className="mt-1 rounded-sm border border-dashed bg-secondary/50 px-3 py-2 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
          {reasoning}
        </div>
      )}
    </div>
  );
}

// --- Tool Calls Display ---

function ToolCallsDisplay({
  toolCalls,
}: {
  toolCalls: AgentMessage["toolCalls"];
}) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 py-0.5">
      {toolCalls.map((tc, i) => (
        <span
          key={tc.call_id ?? i}
          className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"
        >
          {tc.status === "pending" ? (
            <Loader2 className="size-3 animate-spin text-primary" />
          ) : (
            <Check className="size-3 text-primary" />
          )}
          {tc.tool.replace(/_/g, " ")}
        </span>
      ))}
    </div>
  );
}

// --- Action Bar (sidebar mode — visible on hover) ---

function ActionBar({
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
      {isOnNotes && (
        <button
          className="flex items-center gap-1 px-1.5 py-1 rounded text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Insert response into current note"
          title="Insert into Note"
        >
          <FileInput className="size-3" />
          Insert
        </button>
      )}

      <button
        onClick={handleSaveAsZettel}
        disabled={savedAsZettel || hasCreatedZettel || saving}
        className={cn(
          "flex items-center gap-1 px-1.5 py-1 rounded text-[10px] transition-colors",
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

      <button
        onClick={handleCopy}
        className={cn(
          "flex items-center gap-1 px-1.5 py-1 rounded text-[10px] transition-colors",
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

// --- Feedback Buttons (expanded mode — always visible) ---

function FeedbackButtons() {
  return (
    <div className="flex items-center gap-1 pt-1">
      <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        <ThumbsUp className="size-3.5" />
      </button>
      <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        <ThumbsDown className="size-3.5" />
      </button>
      <button className="p-1 rounded text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        <RotateCcw className="size-3.5" />
      </button>
    </div>
  );
}

// --- Main MessageBubble ---

export const MessageBubble = memo(function MessageBubble({
  message,
  mode,
  isOnNotes = false,
  onArtifactClick,
}: {
  message: AgentMessage;
  mode: ChatMode;
  isOnNotes?: boolean;
  onArtifactClick: (artifact: ArtifactCard) => void;
}) {
  const isSidebar = mode === "sidebar";

  // --- User message ---
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "rounded-lg bg-secondary text-sm text-foreground",
            isSidebar
              ? "max-w-[85%] px-3 py-2"
              : "max-w-[80%] rounded-2xl px-4 py-2.5",
          )}
        >
          {message.content}
        </div>
      </div>
    );
  }

  // --- Assistant message ---
  const hasCreatedZettel = message.artifacts.some((a) => a.action === "created");
  const showActions = message.content && !message.content.startsWith("Sorry");

  const contentEl = (
    <>
      {/* Reasoning trace */}
      {message.reasoning && <ReasoningTrace reasoning={message.reasoning} />}

      {/* Tool calls */}
      {message.toolCalls.length > 0 && (
        <ToolCallsDisplay toolCalls={message.toolCalls} />
      )}

      {/* Main content */}
      {message.content && <MarkdownMessage content={message.content} />}
    </>
  );

  return (
    <div className={cn("group space-y-2", !isSidebar && "space-y-3")}>
      {/* In expanded mode, wrap content with InsightToCard for text-selection save */}
      {!isSidebar ? (
        <InsightToCard
          threadTopics={
            message.artifacts.map((a) => a.topic).filter(Boolean) as string[]
          }
        >
          {contentEl}
        </InsightToCard>
      ) : (
        contentEl
      )}

      {/* Artifact cards */}
      {message.artifacts.length > 0 && (
        <div className={cn("space-y-1.5", !isSidebar && "space-y-2")}>
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
        <div className={cn("flex flex-wrap gap-1", !isSidebar && "gap-1.5")}>
          {message.gaps.map((gap) => (
            <span
              key={gap.concept}
              className={cn(
                "inline-flex items-center gap-1 rounded-full bg-[var(--alfred-accent-subtle)] text-primary",
                isSidebar
                  ? "px-2 py-0.5 text-[10px]"
                  : "px-2.5 py-1 text-[11px]",
              )}
            >
              gap: {gap.concept}
            </span>
          ))}
        </div>
      )}

      {/* Actions: sidebar gets hover action bar, expanded gets feedback buttons */}
      {showActions &&
        (isSidebar ? (
          <ActionBar
            message={message}
            isOnNotes={isOnNotes}
            hasCreatedZettel={hasCreatedZettel}
          />
        ) : (
          <FeedbackButtons />
        ))}
    </div>
  );
});
