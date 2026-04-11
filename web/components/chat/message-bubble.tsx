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

import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { InsightToCard } from "@/components/agent/insight-to-card";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { RelatedCards } from "@/components/agent/related-cards";
import { apiFetch } from "@/lib/api/client";
import { copyTextToClipboard } from "@/lib/clipboard";
import type { AgentMessage, ArtifactCard } from "@/lib/stores/agent-store";
import type { ChatMode } from "@/lib/stores/shell-store";
import { cn } from "@/lib/utils";

function ReasoningTrace({ reasoning }: { reasoning: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3 transition-transform", open && "rotate-90")} />
        <span className="uppercase tracking-wider">Thinking</span>
      </button>
      {open ? (
        <div className="mt-1 max-h-64 overflow-y-auto rounded-sm border border-dashed bg-secondary/50 px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">
          {reasoning}
        </div>
      ) : null}
    </div>
  );
}

function ToolCallsDisplay({ toolCalls }: { toolCalls: AgentMessage["toolCalls"] }) {
  if (toolCalls.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 py-0.5">
      {toolCalls.map((toolCall, index) => (
        <span
          key={toolCall.call_id ?? index}
          className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"
        >
          {toolCall.status === "pending" ? (
            <Loader2 className="size-3 animate-spin text-primary" />
          ) : (
            <Check className="size-3 text-primary" />
          )}
          {toolCall.tool.replace(/_/g, " ")}
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

function PlanDisplay({ plan }: { plan: AgentMessage["plan"] }) {
  if (plan.length === 0) return null;

  return (
    <div className="mb-2 rounded-md border bg-secondary/30 px-3 py-2">
      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Plan</div>
      <div className="space-y-1">
        {plan.map((task) => (
          <div key={task.id} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-foreground/90">
              {task.agent}: {task.objective}
            </span>
            <span className="text-muted-foreground">{task.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalDisplay({
  approvals,
}: {
  approvals: AgentMessage["pendingApprovals"];
}) {
  if (approvals.length === 0) return null;

  return (
    <div className="rounded-md border border-dashed bg-[var(--alfred-accent-subtle)]/60 px-3 py-2">
      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        Approval Needed
      </div>
      <div className="space-y-1">
        {approvals.map((approval) => (
          <div key={approval.id} className="text-xs text-foreground/90">
            <span className="font-medium">{approval.action}</span>: {approval.reason}
          </div>
        ))}
      </div>
    </div>
  );
}

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
      toast.error("Failed to save response as a zettel.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-center gap-0.5 pt-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100">
      {isOnNotes ? (
        <button
          className="flex items-center gap-1 rounded px-1.5 py-1 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Insert response into current note"
          title="Insert into Note"
        >
          <FileInput className="size-3" />
          Insert
        </button>
      ) : null}

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

function FeedbackButtons({ content }: { content: string }) {
  return (
    <div className="flex items-center gap-1 pt-1">
      <CopyMessageButton
        content={content}
        className="px-2 py-1 text-[11px] text-muted-foreground/70 hover:text-foreground"
      />
      <button className="rounded p-1 text-muted-foreground/40 transition-colors hover:text-muted-foreground">
        <ThumbsUp className="size-3.5" />
      </button>
      <button className="rounded p-1 text-muted-foreground/40 transition-colors hover:text-muted-foreground">
        <ThumbsDown className="size-3.5" />
      </button>
      <button className="rounded p-1 text-muted-foreground/40 transition-colors hover:text-muted-foreground">
        <RotateCcw className="size-3.5" />
      </button>
    </div>
  );
}

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
  const artifacts = message.artifacts ?? [];
  const relatedCards = message.relatedCards ?? [];
  const gaps = message.gaps ?? [];
  const plan = message.plan ?? [];
  const pendingApprovals = message.pendingApprovals ?? [];
  const toolCalls = message.toolCalls ?? [];

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "rounded-lg bg-secondary text-sm text-foreground",
            isSidebar ? "max-w-[85%] px-3 py-2" : "max-w-[80%] rounded-2xl px-4 py-2.5",
          )}
        >
          {message.content}
        </div>
      </div>
    );
  }

  const createdZettelId =
    artifacts.find((artifact) => artifact.type === "zettel" && artifact.action === "created")?.id ??
    null;
  const showActions = message.content && !message.content.startsWith("Sorry");

  const contentEl = (
    <>
      {plan.length > 0 ? <PlanDisplay plan={plan} /> : null}
      {message.reasoning ? <ReasoningTrace reasoning={message.reasoning} /> : null}
      {toolCalls.length > 0 ? <ToolCallsDisplay toolCalls={toolCalls} /> : null}
      {message.content ? <MarkdownMessage content={message.content} /> : null}
      {pendingApprovals.length > 0 ? <ApprovalDisplay approvals={pendingApprovals} /> : null}
    </>
  );

  return (
    <div className={cn("group space-y-2", !isSidebar && "space-y-3")}>
      {!isSidebar ? (
        <InsightToCard threadTopics={artifacts.map((artifact) => artifact.topic).filter(Boolean) as string[]}>
          {contentEl}
        </InsightToCard>
      ) : (
        contentEl
      )}

      {artifacts.length > 0 ? (
        <div className={cn("space-y-1.5", !isSidebar && "space-y-2")}>
          {artifacts.map((artifact) => (
            <ArtifactCardComponent
              key={`${artifact.type}-${artifact.id}`}
              artifact={artifact}
              onClick={() => onArtifactClick(artifact)}
            />
          ))}
        </div>
      ) : null}

      {relatedCards.length > 0 ? <RelatedCards cards={relatedCards} onCardClick={onArtifactClick} /> : null}

      {gaps.length > 0 ? (
        <div className={cn("flex flex-wrap gap-1", !isSidebar && "gap-1.5")}>
          {gaps.map((gap) => (
            <span
              key={gap.concept}
              className={cn(
                "inline-flex items-center gap-1 rounded-full bg-[var(--alfred-accent-subtle)] text-primary",
                isSidebar ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]",
              )}
            >
              gap: {gap.concept}
            </span>
          ))}
        </div>
      ) : null}

      {showActions
        ? isSidebar
          ? (
            <ActionBar
              message={message}
              isOnNotes={isOnNotes}
              createdZettelId={createdZettelId}
              onViewZettel={onViewZettel}
            />
            )
          : (
            <FeedbackButtons content={message.content} />
            )
        : null}
    </div>
  );
});
