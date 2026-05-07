"use client";

import { memo, useMemo, useState } from "react";
import NextImage from "next/image";

import {
  AlertCircle,
  BookmarkPlus,
  Check,
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
import { RelatedCards } from "@/components/agent/related-cards";
import {
  ChainOfThought,
  ChainOfThoughtStep,
} from "@/components/ai-elements/chain-of-thought";
import { MessageResponse } from "@/components/ai-elements/message";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { apiRoutes } from "@/lib/api/routes";
import { apiFetch } from "@/lib/api/client";
import { copyTextToClipboard } from "@/lib/clipboard";
import type {
  AgentMessage,
  ArtifactCard,
  ImagePart,
  MessagePart,
  StepPart,
} from "@/lib/stores/agent-store";
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
          Add a review note for this block. Polymath can reply to all comments afterward.
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
  onViewZettel,
}: {
  block: MarkdownBlock;
  comments: ResponseComment[];
  draft: string;
  isOpen: boolean;
  setDraft: (value: string) => void;
  onToggle: () => void;
  onAddComment: () => void;
  onReplyToComments: () => void;
  onViewZettel?: (zettelId: number) => void;
}) {
  return (
    <div className="group/comment hover:bg-secondary/25 relative -mx-2 rounded-md px-2 py-1 transition-colors">
      <div className="absolute top-1 right-1 z-10 flex items-center gap-1 opacity-0 transition-opacity group-hover/comment:opacity-100 focus-within:opacity-100">
        <ZettelMessageButton
          content={block.content}
          createdZettelId={null}
          onViewZettel={onViewZettel}
          idleLabel="Zettel"
          savedLabel="View"
          createAriaLabel="Save block as zettel"
          viewAriaLabel="View block zettel"
          createTitle="Save Block as Zettel"
          viewTitle="View Block Zettel"
          className="bg-background/90 rounded-sm border px-1.5 py-1 text-[10px] shadow-sm backdrop-blur"
        />
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

      <MessageResponse>{block.content}</MessageResponse>

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

/**
 * Synthesize MessagePart[] from legacy AgentMessage fields.
 *
 * Used as a fallback for messages that predate the parts[] dual-write
 * (e.g., threads loaded from the DB before Task 4 ships persistence).
 * Order mirrors how the new SSE pipeline would emit them:
 * reasoning -> plan steps -> tool calls -> text.
 */
function synthesizePartsFromLegacy(message: AgentMessage): MessagePart[] {
  const parts: MessagePart[] = [];
  if (message.reasoning) {
    parts.push({
      type: "reasoning",
      text: message.reasoning,
      state: "done",
      startedAt: 0,
      finishedAt: 0,
    });
  }
  // Legacy DB rows carry plan[] but no StepParts. Mirror what the SSE
  // "plan"/"task_*" events would have produced so ChainOfThought renders.
  for (const task of message.plan ?? []) {
    const state: StepPart["state"] =
      task.status === "queued"
        ? "pending"
        : task.status === "running"
          ? "active"
          : task.status === "error"
            ? "error"
            : "complete";
    parts.push({
      type: "step",
      label: `${task.agent}: ${task.objective}`,
      state,
      taskId: task.id,
    });
  }
  for (const tc of message.toolCalls ?? []) {
    parts.push({
      type: `tool-${tc.tool}` as `tool-${string}`,
      toolCallId: tc.call_id ?? `legacy-${tc.tool}-${parts.length}`,
      state:
        tc.status === "done"
          ? "output-available"
          : tc.status === "error"
            ? "output-error"
            : "input-available",
      input: tc.args ?? {},
      output: tc.result,
    });
  }
  if (message.content) {
    parts.push({ type: "text", text: message.content, state: "done" });
  }
  return parts;
}

type GroupedEntry =
  | { kind: "part"; part: MessagePart }
  | { kind: "steps"; steps: StepPart[] };

/**
 * Group consecutive StepParts into single ChainOfThought segments so plan
 * steps render together as one cohesive block rather than scattered rows.
 */
function groupSteps(parts: MessagePart[]): GroupedEntry[] {
  const out: GroupedEntry[] = [];
  let buffer: StepPart[] = [];
  for (const p of parts) {
    if (p.type === "step") {
      buffer.push(p);
    } else {
      if (buffer.length) {
        out.push({ kind: "steps", steps: buffer });
        buffer = [];
      }
      out.push({ kind: "part", part: p });
    }
  }
  if (buffer.length) out.push({ kind: "steps", steps: buffer });
  return out;
}

/**
 * Renders a single tool part with a controlled open state so that tools
 * which transition into `output-error` after mount auto-expand (the
 * uncontrolled `defaultOpen` prop was only read on first render and
 * silently ignored post-mount).
 *
 * Implementation note: we avoid a setState-in-effect pattern (flagged by
 * `react-hooks/set-state-in-effect`) by OR-ing local "user intent" state
 * with the derived `output-error` signal when computing `open`.
 */
function ToolPart({
  part,
}: {
  part: Extract<MessagePart, { type: `tool-${string}` }>;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const isError = part.state === "output-error";
  // Error auto-opens. Otherwise respect user intent if they've toggled,
  // else fall back to closed (matches previous defaultOpen=false default).
  const open = userOpen ?? isError;

  return (
    <Tool open={open} onOpenChange={setUserOpen}>
      <ToolHeader type={part.type} state={part.state} />
      <ToolContent>
        <ToolInput input={part.input} />
        <ToolOutput output={part.output} errorText={part.errorText} />
      </ToolContent>
    </Tool>
  );
}

function renderNonTextPart(entry: GroupedEntry, index: number) {
  if (entry.kind === "steps") {
    return (
      <ChainOfThought key={`steps-${index}`} defaultOpen>
        {entry.steps.map((step, j) => {
          const isError = step.state === "error";
          const status: "complete" | "active" | "pending" =
            step.state === "complete"
              ? "complete"
              : step.state === "active"
                ? "active"
                : step.state === "error"
                  ? // Error surfaces as "complete" (the primitive's finished
                    // state) but styled destructively via `icon` + className
                    // below so it reads as a failure, not a success.
                    "complete"
                  : "pending";
          return (
            <ChainOfThoughtStep
              key={step.taskId ?? `${index}-${j}`}
              label={step.label}
              description={
                isError
                  ? step.description
                    ? `Error: ${step.description}`
                    : "Error"
                  : step.description
              }
              status={status}
              icon={isError ? AlertCircle : undefined}
              className={isError ? "text-destructive" : undefined}
            />
          );
        })}
      </ChainOfThought>
    );
  }

  const part = entry.part;

  if (part.type === "reasoning") {
    const isStreaming = part.state === "streaming";
    const duration =
      part.finishedAt && part.startedAt
        ? Math.max(0, Math.round((part.finishedAt - part.startedAt) / 1000))
        : undefined;
    return (
      <Reasoning
        key={`reasoning-${index}`}
        isStreaming={isStreaming}
        duration={duration}
      >
        <ReasoningTrigger />
        <ReasoningContent>{part.text}</ReasoningContent>
      </Reasoning>
    );
  }

  if (typeof part.type === "string" && part.type.startsWith("tool-")) {
    const tool = part as Extract<MessagePart, { type: `tool-${string}` }>;
    return <ToolPart key={tool.toolCallId || `tool-${index}`} part={tool} />;
  }

  return null;
}

function isImagePart(part: MessagePart): part is ImagePart {
  return part.type === "image";
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
  const pendingApprovals = message.pendingApprovals ?? [];
  const assistantParts = useMemo<MessagePart[]>(
    () => (message.parts?.length ? message.parts : synthesizePartsFromLegacy(message)),
    [message],
  );
  const groupedParts = useMemo(() => groupSteps(assistantParts), [assistantParts]);
  const isAssistantStreaming = useMemo(
    () =>
      assistantParts.some(
        (p) =>
          (p.type === "text" && p.state === "streaming") ||
          (p.type === "reasoning" && p.state === "streaming"),
      ),
    [assistantParts],
  );
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
  const userImageParts = useMemo(
    () => (message.role === "user" ? (message.parts ?? []).filter(isImagePart) : []),
    [message.parts, message.role],
  );

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className={cn(
            "bg-secondary text-foreground rounded-lg text-[15px] leading-relaxed",
            isSidebar ? "max-w-[85%] px-3 py-2" : "max-w-[80%] rounded-2xl px-4 py-2.5",
          )}
        >
          {userImageParts.length > 0 ? (
            <div
              className={cn(
                "mb-2 grid gap-2",
                userImageParts.length === 1 ? "grid-cols-1" : "grid-cols-2",
              )}
            >
              {userImageParts.map((part, index) => (
                <a
                  key={`${part.name ?? "image"}-${index}`}
                  href={part.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block overflow-hidden rounded-md border border-border/60 bg-background/40"
                >
                  <NextImage
                    src={part.url}
                    alt={part.name ?? "Attached image"}
                    width={640}
                    height={360}
                    unoptimized
                    className={cn(
                      "w-full object-cover",
                      userImageParts.length === 1 ? "max-h-64" : "h-28",
                    )}
                  />
                </a>
              ))}
            </div>
          ) : null}
          {message.content ? <p className="whitespace-pre-wrap">{message.content}</p> : null}
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

  // Render every part in order. Text parts render via <MessageResponse>; a
  // separate block-commenting pass below takes over once the stream is done.
  // During streaming, text parts render inline here for a live preview;
  // once `done` we swap to per-block rendering so block comments keep working.
  // This produces a brief flicker at stream-end — acceptable for the first cut.
  const streamingPartsEl = (
    <>
      {groupedParts.map((entry, index) => {
        if (entry.kind === "part" && entry.part.type === "text") {
          return (
            <MessageResponse key={`text-${index}`}>{entry.part.text}</MessageResponse>
          );
        }
        if (entry.kind === "part" && entry.part.type === "source-url") {
          // Sources are handled separately (Task 5) — skip here.
          return null;
        }
        return renderNonTextPart(entry, index);
      })}
    </>
  );

  const doneNonTextPartsEl = (
    <>
      {groupedParts.map((entry, index) => {
        if (entry.kind === "part" && entry.part.type === "text") return null;
        if (entry.kind === "part" && entry.part.type === "source-url") return null;
        return renderNonTextPart(entry, index);
      })}
    </>
  );

  const contentEl =
    isAssistantStreaming || !message.content ? (
      <>
        {streamingPartsEl}
        {pendingApprovals.length > 0 ? <ApprovalDisplay approvals={pendingApprovals} /> : null}
      </>
    ) : (
      <>
        {doneNonTextPartsEl}
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
                onViewZettel={onViewZettel}
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
