"use client";

import { useCallback, useMemo, useState } from "react";

import { formatDistanceToNow } from "date-fns";
import { Check, Expand, Pencil, Plus, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConnectionPill } from "@/components/zettels/connection-pill";
import { LinkEditorDialog } from "@/components/zettels/link-editor-dialog";
import { useShellStore } from "@/lib/stores/shell-store";
import { ZettelReadContent } from "@/app/(app)/knowledge/_components/zettel-read-content";
import { ZettelLinkSuggestions } from "@/app/(app)/knowledge/_components/zettel-link-suggestions";
import {
  useUpdateZettel,
  useDeleteZettel,
} from "@/features/zettels/mutations";
import { useZettelLinks } from "@/features/zettels/queries";
import type { ApiZettelLink } from "@/lib/api/zettels";
import { BloomProgressBar } from "./bloom-badge";
import type { Zettel } from "./mock-data";

type Props = {
  zettel: Zettel;
  allZettels: Zettel[];
  onClose: () => void;
  onSelectZettel: (id: string) => void;
};

export function ZettelDetailPanel({ zettel, allZettels, onClose, onSelectZettel }: Props) {
  const openZettelViewer = useShellStore((state) => state.openZettelViewer);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(zettel.title);
  const [editContent, setEditContent] = useState(zettel.content);
  const [editSummary, setEditSummary] = useState(zettel.summary);
  const [editTags, setEditTags] = useState(zettel.tags.join(", "));
  const [confirmDelete, setConfirmDelete] = useState(false);

  const cardId = parseInt(zettel.id, 10);
  const updateMutation = useUpdateZettel(cardId);
  const deleteMutation = useDeleteZettel();
  const { data: links = [] } = useZettelLinks(Number.isFinite(cardId) ? cardId : null);

  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [editingLink, setEditingLink] = useState<ApiZettelLink | null>(null);

  // Map: other-card-id -> a link row connecting `cardId` to that card.
  // Outbound rows win (they represent the user's authored direction); inbound
  // rows are used when no outbound exists so the pencil can still edit a pair
  // that was originally authored from the other side.
  const linkByNeighbor = useMemo(() => {
    const map = new Map<number, ApiZettelLink>();
    for (const link of links) {
      if (link.from_card_id === cardId) map.set(link.to_card_id, link);
    }
    for (const link of links) {
      if (link.to_card_id === cardId && !map.has(link.from_card_id)) {
        map.set(link.from_card_id, link);
      }
    }
    return map;
  }, [links, cardId]);

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
    <aside className="bg-card flex max-h-[80vh] w-full flex-col rounded-xl border shadow-2xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-2 border-b p-4">
        {isEditing ? (
          <Input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            className="text-lg"
            autoFocus
          />
        ) : (
          <h2 className="min-w-0 text-lg leading-snug line-clamp-2">{zettel.title}</h2>
        )}
        <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {/* Bloom score */}
        <BloomProgressBar level={zettel.bloomLevel} />

        {isEditing ? (
          <>
            <div>
              <div className="mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Summary
              </div>
              <Textarea
                value={editSummary}
                onChange={(e) => setEditSummary(e.target.value)}
                className="text-[13px]"
                rows={3}
              />
            </div>

            <div>
              <div className="mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Content
              </div>
              <Textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="text-[13px]"
                rows={10}
              />
            </div>
          </>
        ) : (
          <ZettelReadContent title={zettel.title} summary={zettel.summary} content={zettel.content} />
        )}

        {/* Connections */}
        {!isEditing && (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
                Connections{connectedZettels.length > 0 && ` (${connectedZettels.length})`}
              </div>
              <button
                type="button"
                onClick={() => {
                  setEditingLink(null);
                  setLinkDialogOpen(true);
                }}
                className="text-muted-foreground hover:text-primary flex items-center gap-1 text-[10px] uppercase tracking-wider"
              >
                <Plus size={10} />
                Add
              </button>
            </div>
            {connectedZettels.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {connectedZettels.map((c) => {
                  const neighborId = parseInt(c.id, 10);
                  const link = linkByNeighbor.get(neighborId);
                  return (
                    <ConnectionPill
                      key={c.id}
                      title={c.title}
                      onNavigate={() => onSelectZettel(c.id)}
                      onEdit={
                        link
                          ? () => {
                              setEditingLink(link);
                              setLinkDialogOpen(true);
                            }
                          : undefined
                      }
                    />
                  );
                })}
              </div>
            ) : (
              <p className="text-[12px] text-[var(--alfred-text-tertiary)]">
                No connections yet — click Add to link to another zettel.
              </p>
            )}
          </div>
        )}

        {/* AI Link Suggestions */}
        <ZettelLinkSuggestions cardId={cardId} />

        {/* Tags */}
        <div>
          <div className="mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
            Tags
          </div>
          {isEditing ? (
            <Input
              value={editTags}
              onChange={(e) => setEditTags(e.target.value)}
              placeholder="comma-separated tags"
              className="text-xs"
            />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {zettel.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-primary rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 text-[10px] font-medium tracking-wider uppercase"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Source */}
        <div>
          <div className="mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
            Source
          </div>
          {zettel.source.url ? (
            <a
              href={zettel.source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary block truncate text-[12px] hover:underline"
            >
              {zettel.source.title}
            </a>
          ) : (
            <p className="text-[12px] text-[var(--alfred-text-tertiary)]">{zettel.source.title}</p>
          )}
          <p className="mt-1 text-[10px] text-[var(--alfred-text-tertiary)]">
            Captured {capturedAgo} · Reviewed {reviewedAgo}
          </p>
        </div>

        {/* Quiz stats */}
        {zettel.quizHistory.attempts > 0 && (
          <div>
            <div className="mb-2 text-[9px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
              Quiz Performance
            </div>
            <p className="font-data text-lg tabular-nums">
              {zettel.quizHistory.correct}/{zettel.quizHistory.attempts}
              <span className="ml-2 text-[10px] text-[var(--alfred-text-tertiary)]">
                ({Math.round((zettel.quizHistory.correct / zettel.quizHistory.attempts) * 100)}%
                accuracy)
              </span>
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2 border-t p-4">
        {isEditing ? (
          <>
            <Button
              size="sm"
              className="flex-1 gap-1.5 text-xs"
              onClick={saveEdit}
              disabled={updateMutation.isPending}
            >
              <Check className="size-3" />
              {updateMutation.isPending ? "Saving..." : "Save"}
            </Button>
            <Button size="sm" variant="outline" className="text-xs" onClick={cancelEdit}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" className="flex-1 text-xs">
              Feynman Test
            </Button>
            <Button size="sm" variant="outline" className="text-xs">
              Review
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="gap-1 text-xs"
              onClick={() => openZettelViewer(cardId)}
            >
              <Expand className="size-3" />
              Open
            </Button>
            <Button size="sm" variant="outline" className="gap-1 text-xs" onClick={startEdit}>
              <Pencil className="size-3" />
              Edit
            </Button>
            <Button
              size="sm"
              variant={confirmDelete ? "destructive" : "outline"}
              className="gap-1 text-xs"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="size-3" />
              {confirmDelete ? "Confirm?" : ""}
            </Button>
          </>
        )}
      </div>

      {Number.isFinite(cardId) && (
        <LinkEditorDialog
          open={linkDialogOpen}
          onOpenChange={(open) => {
            setLinkDialogOpen(open);
            if (!open) setEditingLink(null);
          }}
          mode={editingLink ? "edit" : "create"}
          fromCardId={cardId}
          initialLink={editingLink ?? undefined}
        />
      )}
    </aside>
  );
}
