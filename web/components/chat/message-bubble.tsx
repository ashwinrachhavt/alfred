"use client";

import { memo, useMemo, useState } from "react";

import {
  BookmarkPlus,
  Check,
  ChevronRight,
  ClipboardCopy,
  CornerDownRight,
  FilePlus2,
  Loader2,
  MessageCircle,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { toast } from "sonner";

import { ArtifactCardComponent } from "@/components/agent/artifact-card";
import { InsightToCard } from "@/components/agent/insight-to-card";
import { MarkdownMessage } from "@/components/agent/markdown-message";
import { RelatedCards } from "@/components/agent/related-cards";
import { apiRoutes } from "@/lib/api/routes";
import { apiFetch } from "@/lib/api/client";
import { copyTextToClipboard } from "@/lib/clipboard";
import type { AgentMessage, ArtifactCard } from "@/lib/stores/agent-store";
import type { ChatMode } from "@/lib/stores/shell-store";
import { markdownToPlainText } from "@/lib/utils/markdown";
import { cn } from "@/lib/utils";

type ActionTone = "default" | "subtle";

export type ResponseComment = {
  id: string;
  body: string;
  createdAt: number;
  blockId?: string;
  blockPreview?: string;
};

export type ResponseCommentTarget = {
  blockId: string;
  blockPreview: string;
};

type MarkdownBlock = {
  id: string;
  content: string;
  preview: string;
};

const FALLBACK_COMMENT_BLOCK_ID = "response";

function getActionToneClasses(tone: ActionTone): string {
  return tone === "subtle"
    ? "text-muted-foreground/70 hover:text-foreground"
    : "text-muted-foreground hover:text-foreground";
}

function buildZettelTitle(content: string): string {
  const plainText = markdownToPlainText(content);
  return plainText.slice(0, 60).trim() || "Untitled response";
}

function buildNoteTitle(content: string): string {
  const plainText = markdownToPlainText(content);
  return plainText.slice(0, 80).trim() || "Untitled note";
}

function openNote(noteId: string): void {
  if (typeof window === "undefined") return;
  window.location.href = `/notes?note=${encodeURIComponent(noteId)}`;
}

function hashString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

function getMarkdownLineType(
  line: string,
): "code" | "heading" | "list" | "quote" | "table" | "text" {
  const trimmed = line.trim();
  if (/^(```|~~~)/.test(trimmed)) return "code";
  if (/^#{1,6}\s+/.test(trimmed)) return "heading";
  if (/^([-*+]|\d+[.)])\s+/.test(trimmed)) return "list";
  if (/^>\s?/.test(trimmed)) return "quote";
  if (trimmed.includes("|")) return "table";
  return "text";
}

function buildMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.split(/\r?\n/);
  const blocks: string[] = [];
  let current: string[] = [];
  let currentType: ReturnType<typeof getMarkdownLineType> | null = null;
  let inFence = false;

  const flush = () => {
    const block = current.join("\n").trim();
    if (block) blocks.push(block);
    current = [];
    currentType = null;
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (!trimmed && !inFence) {
      flush();
      continue;
    }

    const lineType = getMarkdownLineType(line);

    if (inFence) {
      current.push(line);
      if (lineType === "code") {
        inFence = false;
        flush();
      }
      continue;
    }

    if (lineType === "code") {
      flush();
      current = [line];
      currentType = "code";
      inFence = true;
      continue;
    }

    if (lineType === "heading") {
      flush();
      current = [line];
      flush();
      continue;
    }

    if (!current.length) {
      current = [line];
      currentType = lineType;
      continue;
    }

    if (
      currentType === lineType ||
      currentType === "list" ||
      currentType === "quote" ||
      currentType === "table"
    ) {
      current.push(line);
      continue;
    }

    flush();
    current = [line];
    currentType = lineType;
  }

  flush();

  return blocks.map((block, index) => ({
    id: `block-${index}-${hashString(block)}`,
    content: block,
    preview: markdownToPlainText(block).slice(0, 140).trim() || `Block ${index + 1}`,
  }));
}

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
      {open ? (
        <div className="bg-secondary/50 text-muted-foreground mt-1 max-h-64 overflow-y-auto rounded-sm border border-dashed px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap">
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
          className="text-muted-foreground inline-flex items-center gap-1 text-[10px]"
        >
          {toolCall.status === "pending" ? (
            <Loader2 className="text-primary size-3 animate-spin" />
          ) : (
            <Check className="text-primary size-3" />
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
  tone = "default",
}: {
  content: string;
  className?: string;
  showLabel?: boolean;
  tone?: ActionTone;
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
      type="button"
      onClick={() => void handleCopy()}
      className={cn(
        "flex items-center gap-1 rounded transition-colors",
        copied ? "text-primary" : getActionToneClasses(tone),
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

function ZettelMessageButton({
  content,
  createdZettelId,
  onViewZettel,
  className,
  showLabel = true,
  tone = "default",
  idleLabel = "Save",
  savedLabel = "View",
  createAriaLabel = "Create zettel from response",
  viewAriaLabel = "View zettel",
  createTitle = "Create Zettel",
  viewTitle = "View Zettel",
}: {
  content: string;
  createdZettelId: number | null;
  onViewZettel?: (zettelId: number) => void;
  className?: string;
  showLabel?: boolean;
  tone?: ActionTone;
  idleLabel?: string;
  savedLabel?: string;
  createAriaLabel?: string;
  viewAriaLabel?: string;
  createTitle?: string;
  viewTitle?: string;
}) {
  const [savedZettelId, setSavedZettelId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const viewZettelId = createdZettelId ?? savedZettelId;

  const handleClick = async () => {
    if (viewZettelId) {
      onViewZettel?.(viewZettelId);
      return;
    }

    if (saving) return;

    setSaving(true);
    try {
      const created = await apiFetch<{ id: number }>(apiRoutes.zettels.cards, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: buildZettelTitle(content),
          content,
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
    <button
      type="button"
      onClick={() => void handleClick()}
      disabled={saving}
      className={cn(
        "flex items-center gap-1 rounded transition-colors",
        viewZettelId ? "text-primary" : getActionToneClasses(tone),
        showLabel ? "px-1.5 py-1 text-[10px]" : "p-1",
        className,
      )}
      aria-label={viewZettelId ? viewAriaLabel : createAriaLabel}
      title={viewZettelId ? viewTitle : createTitle}
    >
      {saving ? (
        <Loader2 className="size-3 animate-spin" />
      ) : viewZettelId ? (
        <Check className="size-3" />
      ) : (
        <BookmarkPlus className="size-3" />
      )}
      {showLabel ? (viewZettelId ? savedLabel : idleLabel) : null}
    </button>
  );
}

function NoteMessageButton({
  content,
  createdNoteId,
  onViewNote,
  className,
  showLabel = true,
  tone = "default",
  idleLabel = "Note",
  savedLabel = "View",
  createAriaLabel = "Save as note",
  viewAriaLabel = "View note",
  createTitle = "Save as Note",
  viewTitle = "View Note",
}: {
  content: string;
  createdNoteId?: string | null;
  onViewNote?: (noteId: string) => void;
  className?: string;
  showLabel?: boolean;
  tone?: ActionTone;
  idleLabel?: string;
  savedLabel?: string;
  createAriaLabel?: string;
  viewAriaLabel?: string;
  createTitle?: string;
  viewTitle?: string;
}) {
  const [savedNoteId, setSavedNoteId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const viewNoteId = createdNoteId ?? savedNoteId;

  const handleClick = async () => {
    if (viewNoteId) {
      if (onViewNote) {
        onViewNote(viewNoteId);
      } else {
        openNote(viewNoteId);
      }
      return;
    }

    if (saving) return;

    setSaving(true);
    try {
      const created = await apiFetch<{ id: string }>(apiRoutes.notes.createNote, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: buildNoteTitle(content),
          content_markdown: content,
          content_json: null,
        }),
      });
      setSavedNoteId(created.id);
    } catch {
      toast.error("Failed to save response as a note.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      disabled={saving}
      className={cn(
        "flex items-center gap-1 rounded transition-colors",
        viewNoteId ? "text-primary" : getActionToneClasses(tone),
        showLabel ? "px-1.5 py-1 text-[10px]" : "p-1",
        className,
      )}
      aria-label={viewNoteId ? viewAriaLabel : createAriaLabel}
      title={viewNoteId ? viewTitle : createTitle}
    >
      {saving ? (
        <Loader2 className="size-3 animate-spin" />
      ) : viewNoteId ? (
        <Check className="size-3" />
      ) : (
        <FilePlus2 className="size-3" />
      )}
      {showLabel ? (viewNoteId ? savedLabel : idleLabel) : null}
    </button>
  );
}

function PlanDisplay({ plan }: { plan: AgentMessage["plan"] }) {
  if (plan.length === 0) return null;

  return (
    <div className="bg-secondary/30 mb-2 rounded-md border px-3 py-2">
      <div className="text-muted-foreground mb-1 text-[10px] tracking-wider uppercase">Plan</div>
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

function ApprovalDisplay({ approvals }: { approvals: AgentMessage["pendingApprovals"] }) {
  if (approvals.length === 0) return null;

  return (
    <div className="rounded-md border border-dashed bg-[var(--alfred-accent-subtle)]/60 px-3 py-2">
      <div className="text-muted-foreground mb-1 text-[10px] tracking-wider uppercase">
        Approval Needed
      </div>
      <div className="space-y-1">
        {approvals.map((approval) => (
          <div key={approval.id} className="text-foreground/90 text-xs">
            <span className="font-medium">{approval.action}</span>: {approval.reason}
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionBar({
  message,
  createdZettelId,
  commentCount,
  onToggleComments,
  onViewNote,
  onViewZettel,
}: {
  message: AgentMessage;
  createdZettelId: number | null;
  commentCount: number;
  onToggleComments: () => void;
  onViewNote?: (noteId: string) => void;
  onViewZettel?: (zettelId: number) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 pt-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:opacity-100">
      <ZettelMessageButton
        content={message.content}
        createdZettelId={createdZettelId}
        onViewZettel={onViewZettel}
        idleLabel="Save"
        savedLabel="View"
        createAriaLabel="Save as zettel"
        createTitle="Save as Zettel"
      />

      <NoteMessageButton content={message.content} onViewNote={onViewNote} />

      <CopyMessageButton content={message.content} />

      <button
        type="button"
        onClick={onToggleComments}
        className={cn(
          "flex items-center gap-1 rounded px-1.5 py-1 text-[10px] transition-colors",
          commentCount > 0 ? "text-primary" : "text-muted-foreground hover:text-foreground",
        )}
        aria-label={commentCount > 0 ? `View ${commentCount} comments` : "Add comment"}
        title={commentCount > 0 ? "View comments" : "Add comment"}
      >
        <MessageCircle className="size-3" />
        {commentCount > 0 ? commentCount : "Comment"}
      </button>
    </div>
  );
}

function FeedbackButtons({
  content,
  createdZettelId,
  commentCount,
  onToggleComments,
  onViewNote,
  onViewZettel,
}: {
  content: string;
  createdZettelId: number | null;
  commentCount: number;
  onToggleComments: () => void;
  onViewNote?: (noteId: string) => void;
  onViewZettel?: (zettelId: number) => void;
}) {
  return (
    <div className="flex items-center gap-1 pt-1">
      <CopyMessageButton content={content} tone="subtle" className="px-2 py-1 text-[11px]" />
      <ZettelMessageButton
        content={content}
        createdZettelId={createdZettelId}
        onViewZettel={onViewZettel}
        tone="subtle"
        className="px-2 py-1 text-[11px]"
        idleLabel="Zettel"
        savedLabel="View"
      />
      <NoteMessageButton
        content={content}
        onViewNote={onViewNote}
        tone="subtle"
        className="px-2 py-1 text-[11px]"
      />
      <button
        type="button"
        onClick={onToggleComments}
        className={cn(
          "flex items-center gap-1 rounded px-2 py-1 text-[11px] transition-colors",
          commentCount > 0
            ? "text-primary"
            : "text-muted-foreground/60 hover:text-muted-foreground",
        )}
        aria-label={commentCount > 0 ? `View ${commentCount} comments` : "Add comment"}
        title={commentCount > 0 ? "View comments" : "Add comment"}
      >
        <MessageCircle className="size-3.5" />
        {commentCount > 0 ? `${commentCount} comments` : "Comment"}
      </button>
      <button
        type="button"
        className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors"
        aria-label="Like response"
        title="Like response"
      >
        <ThumbsUp className="size-3.5" />
      </button>
      <button
        type="button"
        className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors"
        aria-label="Dislike response"
        title="Dislike response"
      >
        <ThumbsDown className="size-3.5" />
      </button>
      <button
        type="button"
        className="text-muted-foreground/40 hover:text-muted-foreground rounded p-1 transition-colors"
        aria-label="Regenerate response"
        title="Regenerate response"
      >
        <RotateCcw className="size-3.5" />
      </button>
    </div>
  );
}

function ResponseCommentsPanel({
  comments,
  draft,
  setDraft,
  onAddComment,
  onReplyToComments,
}: {
  comments: ResponseComment[];
  draft: string;
  setDraft: (value: string) => void;
  onAddComment: () => void;
  onReplyToComments: () => void;
}) {
  return (
    <div className="bg-secondary/25 rounded-md border p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="text-primary size-3.5" />
          <span className="font-mono text-[10px] tracking-[0.14em] text-[var(--alfred-text-tertiary)] uppercase">
            Block comments
          </span>
        </div>
        {comments.length > 0 ? (
          <button
            type="button"
            onClick={onReplyToComments}
            className="text-primary hover:text-primary/80 flex items-center gap-1 text-[10px] transition-colors"
          >
            <CornerDownRight className="size-3" />
            Reply to comments
          </button>
        ) : null}
      </div>

      {comments.length > 0 ? (
        <div className="mb-3 space-y-2">
          {comments.map((comment, index) => (
            <div key={comment.id} className="bg-background/70 rounded-sm border px-3 py-2">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] text-[var(--alfred-text-tertiary)] uppercase">
                  Comment {index + 1}
                </span>
                <span className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                  {new Date(comment.createdAt).toLocaleTimeString([], {
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <p className="text-foreground/90 text-xs leading-5 whitespace-pre-wrap">
                {comment.body}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground mb-3 text-xs">
          Add a review note for this block. Alfred can reply to all comments afterward.
        </p>
      )}

      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onAddComment();
            }
          }}
          rows={2}
          placeholder="Write a comment on this response..."
          className="bg-background focus:border-primary min-h-16 flex-1 resize-none rounded-sm border px-3 py-2 text-xs leading-5 transition-colors outline-none placeholder:text-[var(--alfred-text-tertiary)]"
        />
        <button
          type="button"
          onClick={onAddComment}
          disabled={!draft.trim()}
          className={cn(
            "rounded-sm px-3 py-2 text-xs transition-colors",
            draft.trim()
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-secondary text-muted-foreground/50 cursor-not-allowed",
          )}
        >
          Add
        </button>
      </div>
    </div>
  );
}

function CommentableMarkdownBlock({
  block,
  comments,
  draft,
  isOpen,
  setDraft,
  onToggle,
  onAddComment,
  onReplyToComments,
}: {
  block: MarkdownBlock;
  comments: ResponseComment[];
  draft: string;
  isOpen: boolean;
  setDraft: (value: string) => void;
  onToggle: () => void;
  onAddComment: () => void;
  onReplyToComments: () => void;
}) {
  return (
    <div className="group/comment hover:bg-secondary/25 relative -mx-2 rounded-md px-2 py-1 transition-colors">
      <div className="absolute top-1 right-1 z-10 opacity-0 transition-opacity group-hover/comment:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "bg-background/90 flex items-center gap-1 rounded-sm border px-1.5 py-1 text-[10px] shadow-sm backdrop-blur transition-colors",
            comments.length > 0
              ? "text-primary border-[var(--alfred-accent-muted)]"
              : "text-muted-foreground hover:text-foreground",
          )}
          aria-label={
            comments.length > 0 ? `View ${comments.length} block comments` : "Comment on block"
          }
          title={comments.length > 0 ? "View block comments" : "Comment on block"}
        >
          <MessageCircle className="size-3" />
          {comments.length > 0 ? comments.length : "Comment"}
        </button>
      </div>

      <MarkdownMessage content={block.content} />

      {comments.length > 0 && !isOpen ? (
        <button
          type="button"
          onClick={onToggle}
          className="text-primary hover:text-primary/80 mt-1 inline-flex items-center gap-1 rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-1 text-[10px] transition-colors"
        >
          <MessageCircle className="size-3" />
          Commented · {comments.length}
        </button>
      ) : null}

      {isOpen ? (
        <div className="mt-2">
          <ResponseCommentsPanel
            comments={comments}
            draft={draft}
            setDraft={setDraft}
            onAddComment={onAddComment}
            onReplyToComments={onReplyToComments}
          />
        </div>
      ) : null}
    </div>
  );
}

export const MessageBubble = memo(function MessageBubble({
  message,
  mode,
  responseComments = [],
  onAddResponseComment,
  onReplyToResponseComments,
  onArtifactClick,
  onViewNote,
  onViewZettel,
}: {
  message: AgentMessage;
  mode: ChatMode;
  isOnNotes?: boolean;
  responseComments?: ResponseComment[];
  onAddResponseComment?: (messageId: string, body: string, target: ResponseCommentTarget) => void;
  onReplyToResponseComments?: (message: AgentMessage) => void;
  onArtifactClick: (artifact: ArtifactCard) => void;
  onViewNote?: (noteId: string) => void;
  onViewZettel?: (zettelId: number) => void;
}) {
  const [openCommentBlockId, setOpenCommentBlockId] = useState<string | null>(null);
  const [commentDraftsByBlockId, setCommentDraftsByBlockId] = useState<Record<string, string>>({});
  const isSidebar = mode === "sidebar";
  const artifacts = message.artifacts ?? [];
  const relatedCards = message.relatedCards ?? [];
  const gaps = message.gaps ?? [];
  const plan = message.plan ?? [];
  const pendingApprovals = message.pendingApprovals ?? [];
  const toolCalls = message.toolCalls ?? [];
  const markdownBlocks = useMemo(() => buildMarkdownBlocks(message.content), [message.content]);
  const markdownBlockIds = useMemo(
    () => new Set(markdownBlocks.map((block) => block.id)),
    [markdownBlocks],
  );
  const fallbackCommentBlockId = markdownBlocks[0]?.id ?? FALLBACK_COMMENT_BLOCK_ID;
  const commentsByBlockId = useMemo(() => {
    const grouped = new Map<string, ResponseComment[]>();
    for (const comment of responseComments) {
      const blockId = comment.blockId ?? fallbackCommentBlockId;
      grouped.set(blockId, [...(grouped.get(blockId) ?? []), comment]);
    }
    return grouped;
  }, [fallbackCommentBlockId, responseComments]);

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

  const createdZettelId =
    artifacts.find((artifact) => artifact.type === "zettel" && artifact.action === "created")?.id ??
    null;
  const showActions = message.content && !message.content.startsWith("Sorry");
  const commentCount = responseComments.length;
  const firstCommentBlockId =
    responseComments.find((comment) => !comment.blockId || markdownBlockIds.has(comment.blockId))
      ?.blockId ?? fallbackCommentBlockId;
  const firstBlockId = firstCommentBlockId ?? markdownBlocks[0]?.id ?? FALLBACK_COMMENT_BLOCK_ID;

  const setBlockDraft = (blockId: string, value: string) => {
    setCommentDraftsByBlockId((current) => ({
      ...current,
      [blockId]: value,
    }));
  };

  const handleAddComment = (block: MarkdownBlock) => {
    const body = (commentDraftsByBlockId[block.id] ?? "").trim();
    if (!body) return;
    onAddResponseComment?.(message.id, body, {
      blockId: block.id,
      blockPreview: block.preview,
    });
    setBlockDraft(block.id, "");
    setOpenCommentBlockId(block.id);
  };

  const handleReplyToComments = () => {
    if (commentCount === 0) return;
    onReplyToResponseComments?.(message);
  };

  const handleToggleComments = () => {
    setOpenCommentBlockId((current) => (current === firstBlockId ? null : firstBlockId));
  };

  const contentEl = (
    <>
      {plan.length > 0 ? <PlanDisplay plan={plan} /> : null}
      {message.reasoning ? <ReasoningTrace reasoning={message.reasoning} /> : null}
      {toolCalls.length > 0 ? <ToolCallsDisplay toolCalls={toolCalls} /> : null}
      {markdownBlocks.length > 0 ? (
        <div className="space-y-1">
          {markdownBlocks.map((block) => (
            <CommentableMarkdownBlock
              key={block.id}
              block={block}
              comments={commentsByBlockId.get(block.id) ?? []}
              draft={commentDraftsByBlockId[block.id] ?? ""}
              isOpen={openCommentBlockId === block.id}
              setDraft={(value) => setBlockDraft(block.id, value)}
              onToggle={() =>
                setOpenCommentBlockId((current) => (current === block.id ? null : block.id))
              }
              onAddComment={() => handleAddComment(block)}
              onReplyToComments={handleReplyToComments}
            />
          ))}
        </div>
      ) : null}
      {pendingApprovals.length > 0 ? <ApprovalDisplay approvals={pendingApprovals} /> : null}
    </>
  );

  return (
    <div className={cn("group space-y-2", !isSidebar && "space-y-3")}>
      {!isSidebar ? (
        <InsightToCard
          threadTopics={artifacts.map((artifact) => artifact.topic).filter(Boolean) as string[]}
        >
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

      {relatedCards.length > 0 ? (
        <RelatedCards cards={relatedCards} onCardClick={onArtifactClick} />
      ) : null}

      {gaps.length > 0 ? (
        <div className={cn("flex flex-wrap gap-1", !isSidebar && "gap-1.5")}>
          {gaps.map((gap) => (
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
      ) : null}

      {showActions ? (
        isSidebar ? (
          <ActionBar
            message={message}
            createdZettelId={createdZettelId}
            commentCount={commentCount}
            onToggleComments={handleToggleComments}
            onViewNote={onViewNote}
            onViewZettel={onViewZettel}
          />
        ) : (
          <FeedbackButtons
            content={message.content}
            createdZettelId={createdZettelId}
            commentCount={commentCount}
            onToggleComments={handleToggleComments}
            onViewNote={onViewNote}
            onViewZettel={onViewZettel}
          />
        )
      ) : null}

      {commentCount > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={handleToggleComments}
            className="text-primary hover:text-primary/80 inline-flex items-center gap-1 rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-1 text-[10px] transition-colors"
          >
            <MessageCircle className="size-3" />
            Commented · {commentCount}
          </button>
          <button
            type="button"
            onClick={handleReplyToComments}
            className="text-primary hover:text-primary/80 inline-flex items-center gap-1 rounded-sm border border-[var(--alfred-accent-muted)] px-2 py-1 text-[10px] transition-colors"
          >
            <CornerDownRight className="size-3" />
            Reply to comments
          </button>
        </div>
      ) : null}
    </div>
  );
});
