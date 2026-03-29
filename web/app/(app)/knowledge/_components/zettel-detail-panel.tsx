"use client";

import { useCallback, useState } from "react";

import { formatDistanceToNow } from "date-fns";
import { Check, Pencil, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateZettel, useDeleteZettel } from "@/features/zettels/mutations";
import { BloomProgressBar } from "./bloom-badge";
import type { Zettel } from "./mock-data";

type Props = {
  zettel: Zettel;
  allZettels: Zettel[];
  onClose: () => void;
  onSelectZettel: (id: string) => void;
};

export function ZettelDetailPanel({ zettel, allZettels, onClose, onSelectZettel }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(zettel.title);
  const [editContent, setEditContent] = useState(zettel.content);
  const [editSummary, setEditSummary] = useState(zettel.summary);
  const [editTags, setEditTags] = useState(zettel.tags.join(", "));
  const [confirmDelete, setConfirmDelete] = useState(false);

  const cardId = parseInt(zettel.id, 10);
  const updateMutation = useUpdateZettel(cardId);
  const deleteMutation = useDeleteZettel();

  const connectedZettels = allZettels.filter((z) => zettel.connections.includes(z.id));
  const capturedAgo = formatDistanceToNow(new Date(zettel.source.capturedAt), { addSuffix: true });
  const reviewedAgo = zettel.lastReviewedAt
    ? formatDistanceToNow(new Date(zettel.lastReviewedAt), { addSuffix: true })
    : "never";

  const startEdit = useCallback(() => {
    setEditTitle(zettel.title);
    setEditContent(zettel.content);
    setEditSummary(zettel.summary);
    setEditTags(zettel.tags.join(", "));
    setIsEditing(true);
  }, [zettel]);

  const cancelEdit = useCallback(() => {
    setIsEditing(false);
    setConfirmDelete(false);
  }, []);

  const saveEdit = useCallback(() => {
    const tags = editTags
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    updateMutation.mutate(
      { title: editTitle, content: editContent, summary: editSummary, tags },
      { onSuccess: () => setIsEditing(false) },
    );
  }, [editTitle, editContent, editSummary, editTags, updateMutation]);

  const handleDelete = useCallback(() => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    deleteMutation.mutate(cardId, {
      onSuccess: () => onClose(),
    });
  }, [confirmDelete, cardId, deleteMutation, onClose]);

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-l bg-card">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b p-4">
        {isEditing ? (
          <Input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            className="font-serif text-lg"
            autoFocus
          />
        ) : (
          <h2 className="font-serif text-lg leading-snug">{zettel.title}</h2>
        )}
        <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Bloom score */}
        <BloomProgressBar level={zettel.bloomLevel} />

        {/* Summary */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Summary
          </div>
          {isEditing ? (
            <Textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              className="text-[13px]"
              rows={3}
            />
          ) : (
            <p className="text-[13px] leading-relaxed text-muted-foreground">
              {zettel.summary}
            </p>
          )}
        </div>

        {/* Content */}
        {isEditing && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Content
            </div>
            <Textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="text-[13px]"
              rows={5}
            />
          </div>
        )}

        {/* Connections */}
        {connectedZettels.length > 0 && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Connections ({connectedZettels.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {connectedZettels.map((c) => (
                <button
                  key={c.id}
                  onClick={() => onSelectZettel(c.id)}
                  className="rounded-md border px-2.5 py-1 text-[12px] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                >
                  {c.title}
                </button>
              ))}
            </div>
          </div>
        )}

        {connectedZettels.length === 0 && !isEditing && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Connections
            </div>
            <p className="text-[12px] text-[var(--alfred-text-tertiary)] italic">
              No connections yet
            </p>
          </div>
        )}

        {/* Tags */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Tags
          </div>
          {isEditing ? (
            <Input
              value={editTags}
              onChange={(e) => setEditTags(e.target.value)}
              placeholder="comma-separated tags"
              className="font-mono text-xs"
            />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {zettel.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-primary"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Source */}
        <div>
          <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
            Source
          </div>
          <p className="text-[12px] text-[var(--alfred-text-tertiary)]">
            {zettel.source.title}
          </p>
          <p className="mt-1 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
            Captured {capturedAgo} · Reviewed {reviewedAgo}
          </p>
        </div>

        {/* Quiz stats */}
        {zettel.quizHistory.attempts > 0 && (
          <div>
            <div className="font-mono text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
              Quiz Performance
            </div>
            <p className="font-data text-lg tabular-nums">
              {zettel.quizHistory.correct}/{zettel.quizHistory.attempts}
              <span className="ml-2 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                ({Math.round((zettel.quizHistory.correct / zettel.quizHistory.attempts) * 100)}% accuracy)
              </span>
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="border-t p-4 flex gap-2">
        {isEditing ? (
          <>
            <Button
              size="sm"
              className="flex-1 gap-1.5 font-mono text-xs"
              onClick={saveEdit}
              disabled={updateMutation.isPending}
            >
              <Check className="size-3" />
              {updateMutation.isPending ? "Saving..." : "Save"}
            </Button>
            <Button size="sm" variant="outline" className="font-mono text-xs" onClick={cancelEdit}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" className="flex-1 font-mono text-xs">
              Feynman Test
            </Button>
            <Button size="sm" variant="outline" className="font-mono text-xs">
              Review
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 font-mono text-xs"
              onClick={startEdit}
            >
              <Pencil className="size-3" />
              Edit
            </Button>
            <Button
              size="sm"
              variant={confirmDelete ? "destructive" : "outline"}
              className="gap-1 font-mono text-xs"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="size-3" />
              {confirmDelete ? "Confirm?" : ""}
            </Button>
          </>
        )}
      </div>
    </aside>
  );
}
