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
import { toast } from "sonner";

import type { ChatMode } from "@/lib/stores/shell-store";
import type { AgentMessage, ArtifactCard } from "@/lib/stores/agent-store";
import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { RelatedCards } from "@/components/agent/related-cards";
import { InsightToCard } from "@/components/agent/insight-to-card";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { apiFetch } from "@/lib/api/client";
import { copyTextToClipboard } from "@/lib/clipboard";
import { cn } from "@/lib/utils";

// --- Reasoning Trace ---

function ReasoningTrace({ reasoning }: { reasoning: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-[10px] transition-colors"
      >
        <ChevronRight className={cn("size-3 transition-transform", open && "rotate-90")} />
        <span className="tracking-wider uppercase">Thinking</span>
      </button>
      {open && (
        <div className="bg-secondary/50 text-muted-foreground mt-1 max-h-64 overflow-y-auto rounded-sm border border-dashed px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap">
          {reasoning}
        </div>
      )}
    </div>
  );
}

// --- Tool Calls Display ---

function ToolCallsDisplay({ toolCalls }: { toolCalls: AgentMessage["toolCalls"] }) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 py-0.5">
      {toolCalls.map((tc, i) => (
        <span
          key={tc.call_id ?? i}
          className="text-muted-foreground inline-flex items-center gap-1 text-[10px]"
        >
          {tc.status === "pending" ? (
            <Loader2 className="text-primary size-3 animate-spin" />
          ) : (
            <Check className="text-primary size-3" />
          )}
          {tc.tool.replace(/_/g, " ")}
        </span>
      ))}
    </div>
  );
}

function CopyMessageButton({
  content,
  className,
  showLabel = true,
}: {
  content: string;
  className?: string;
  showLabel?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await copyTextToClipboard(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Failed to copy response.");
    }
  };

  return (
    <button
      onClick={() => void handleCopy()}
      className={cn(
        "flex items-center gap-1 rounded transition-colors",
        copied ? "text-primary" : "text-muted-foreground hover:text-foreground",
        showLabel ? "px-1.5 py-1 text-[10px]" : "p-1",
        className,
      )}
      aria-label="Copy response"
      title="Copy"
    >
      {copied ? <Check className="size-3" /> : <ClipboardCopy className="size-3" />}
      {showLabel ? (copied ? "Copied" : "Copy") : null}
    </button>
  );
}

// --- Action Bar (sidebar mode — visible on hover) ---

function ActionBar({
  message,
  isOnNotes,
  createdZettelId,
  onViewZettel,
}: {
  message: AgentMessage;
  isOnNotes: boolean;
  createdZettelId: number | null;
  onViewZettel?: (zettelId: number) => void;
}) {
  const [savedZettelId, setSavedZettelId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const viewZettelId = createdZettelId ?? savedZettelId;

  const handlePrimaryAction = async () => {
    if (viewZettelId) {
      onViewZettel?.(viewZettelId);
      return;
    }

    if (saving) return;
    setSaving(true);
    try {
      const created = await apiFetch<{ id: number }>("/api/zettels/cards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: message.content.slice(0, 60).replace(/[#*_]/g, "").trim(),
          content: message.content,
          tags: [],
          topic: "",
        }),
      });
      setSavedZettelId(created.id);
    } catch {
      // TODO: show error toast
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-0.5 pt-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100">
      {isOnNotes && (
        <button
          className="text-muted-foreground hover:text-foreground flex items-center gap-1 rounded px-1.5 py-1 text-[10px] transition-colors"
          aria-label="Insert response into current note"
          title="Insert into Note"
        >
          <FileInput className="size-3" />
          Insert
        </button>
      )}

      <button
        onClick={() => void handlePrimaryAction()}
        disabled={saving}
        className={cn(
          "flex items-center gap-1 rounded px-1.5 py-1 text-[10px] transition-colors",
          viewZettelId ? "text-primary" : "text-muted-foreground hover:text-foreground",
        )}
        aria-label={viewZettelId ? "View zettel" : "Save as zettel"}
        title={viewZettelId ? "View Zettel" : "Save as Zettel"}
      >
        {saving ? (
          <Loader2 className="size-3 animate-spin" />
        ) : viewZettelId ? (
          <Check className="size-3" />
        ) : (
          <BookmarkPlus className="size-3" />
        )}
        {viewZettelId ? "View" : "Save"}
      </button>

      <CopyMessageButton content={message.content} />
    </div>
  );
}

// --- Feedback Buttons (expanded mode — always visible) ---

function FeedbackButtons({ content }: { content: string }) {
  return (
    <div className="flex items-center gap-1 pt-1">
      <CopyMessageButton
        content={content}
        showLabel
        className="text-muted-foreground/70 hover:text-foreground px-2 py-1 text-[11px]"
      />
      <button className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors">
        <ThumbsUp className="size-3.5" />
      </button>
      <button className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors">
        <ThumbsDown className="size-3.5" />
      </button>
      <button className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors">
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
  onViewZettel,
}: {
  message: AgentMessage;
  mode: ChatMode;
  isOnNotes?: boolean;
  onArtifactClick: (artifact: ArtifactCard) => void;
  onViewZettel?: (zettelId: number) => void;
}) {
  const isSidebar = mode === "sidebar";

  // --- User message ---
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "bg-secondary text-foreground rounded-lg text-sm",
            isSidebar ? "max-w-[85%] px-3 py-2" : "max-w-[80%] rounded-2xl px-4 py-2.5",
          )}
        >
          {message.content}
        </div>
      </div>
    );
  }

  // --- Assistant message ---
  const createdZettelId =
    message.artifacts.find((a) => a.type === "zettel" && a.action === "created")?.id ?? null;
  const showActions = message.content && !message.content.startsWith("Sorry");

  const contentEl = (
    <>
      {/* Reasoning trace */}
      {message.reasoning && <ReasoningTrace reasoning={message.reasoning} />}

      {/* Tool calls */}
      {message.toolCalls.length > 0 && <ToolCallsDisplay toolCalls={message.toolCalls} />}

      {/* Main content */}
      {message.content && <MarkdownMessage content={message.content} />}
    </>
  );

  return (
    <div className={cn("group space-y-2", !isSidebar && "space-y-3")}>
      {/* In expanded mode, wrap content with InsightToCard for text-selection save */}
      {!isSidebar ? (
        <InsightToCard
          threadTopics={message.artifacts.map((a) => a.topic).filter(Boolean) as string[]}
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
                "text-primary inline-flex items-center gap-1 rounded-full bg-[var(--alfred-accent-subtle)]",
                isSidebar ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
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
            createdZettelId={createdZettelId}
            onViewZettel={onViewZettel}
          />
        ) : (
          <FeedbackButtons content={message.content} />
        ))}
    </div>
  );
});
