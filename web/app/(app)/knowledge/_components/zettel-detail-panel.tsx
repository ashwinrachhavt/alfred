"use client";

import { useCallback, useState } from "react";

import { formatDistanceToNow } from "date-fns";
import { Check, Link2, Loader2, Pencil, Sparkles, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateZettel, useDeleteZettel, useCreateZettelLink } from "@/features/zettels/mutations";
import { suggestZettelLinks, type LinkSuggestion } from "@/lib/api/zettels";
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
 const [suggestions, setSuggestions] = useState<LinkSuggestion[]>([]);
 const [suggestLoading, setSuggestLoading] = useState(false);
 const [acceptedLinks, setAcceptedLinks] = useState<Set<number>>(new Set());

 const cardId = parseInt(zettel.id, 10);
 const updateMutation = useUpdateZettel(cardId);
 const deleteMutation = useDeleteZettel();
 const linkMutation = useCreateZettelLink(cardId);

 const connectedZettels = allZettels.filter((z) => zettel.connections.includes(z.id));
 const capturedAgo = formatDistanceToNow(new Date(zettel.source.capturedAt), { addSuffix: true });
 const reviewedAgo = zettel.lastReviewedAt
 ? formatDistanceToNow(new Date(zettel.lastReviewedAt), { addSuffix: true })
 : "never";

 const handleSuggestLinks = useCallback(async () => {
 setSuggestLoading(true);
 try {
 const results = await suggestZettelLinks(cardId, { min_confidence: 0.4, limit: 8 });
 setSuggestions(results);
 setAcceptedLinks(new Set());
 } catch {
 setSuggestions([]);
 } finally {
 setSuggestLoading(false);
 }
 }, [cardId]);

 const handleAcceptLink = useCallback((toCardId: number) => {
 linkMutation.mutate(
 { to_card_id: toCardId, type: "ai-suggested", bidirectional: true },
 {
 onSuccess: () => {
 setAcceptedLinks((prev) => new Set([...prev, toCardId]));
 },
 },
 );
 }, [linkMutation]);

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
 className="text-lg"
 autoFocus
 />
 ) : (
 <h2 className="text-lg leading-snug">{zettel.title}</h2>
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
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
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
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
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
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
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
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
 Connections
 </div>
 <p className="text-[12px] text-[var(--alfred-text-tertiary)]">
 No connections yet — link to this card from a note using{" "}
 <code className="rounded bg-muted px-1 py-0.5 text-[11px] font-mono">[[{zettel.title.slice(0, 20)}...</code>
 </p>
 </div>
 )}

 {/* AI Link Suggestions */}
 <div>
 <div className="flex items-center justify-between mb-2">
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 AI Suggestions
 </div>
 <Button
 variant="ghost"
 size="sm"
 className="h-6 gap-1 text-[10px] text-primary"
 onClick={handleSuggestLinks}
 disabled={suggestLoading}
 >
 {suggestLoading ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
 {suggestions.length > 0 ? "Refresh" : "Find Links"}
 </Button>
 </div>
 {suggestions.length > 0 && (
 <div className="space-y-1.5">
 {suggestions.map((s) => (
 <div
 key={s.to_card_id}
 className="flex items-center gap-2 rounded-md border px-2.5 py-1.5"
 >
 <div className="flex-1 min-w-0">
 <p className="text-[12px] font-medium truncate">{s.to_title}</p>
 <p className="text-[9px] text-[var(--alfred-text-tertiary)]">
 {s.reason} · {Math.round(s.scores.composite_score * 100)}%
 </p>
 </div>
 {acceptedLinks.has(s.to_card_id) ? (
 <span className="shrink-0 text-[10px] text-green-500 flex items-center gap-0.5">
 <Check className="size-3" /> Linked
 </span>
 ) : (
 <Button
 variant="ghost"
 size="sm"
 className="h-6 shrink-0 gap-1 text-[10px] text-primary"
 onClick={() => handleAcceptLink(s.to_card_id)}
 disabled={linkMutation.isPending}
 >
 <Link2 className="size-3" />
 Link
 </Button>
 )}
 </div>
 ))}
 </div>
 )}
 {suggestions.length === 0 && !suggestLoading && (
 <p className="text-[11px] text-[var(--alfred-text-tertiary)]">
 Click &ldquo;Find Links&rdquo; to discover related cards
 </p>
 )}
 </div>

 {/* Tags */}
 <div>
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
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
 className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-medium text-[10px] uppercase tracking-wider text-primary"
 >
 {tag}
 </span>
 ))}
 </div>
 )}
 </div>

 {/* Source */}
 <div>
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
 Source
 </div>
 {zettel.source.url ? (
 <a
 href={zettel.source.url}
 target="_blank"
 rel="noopener noreferrer"
 className="text-[12px] text-primary hover:underline truncate block"
 >
 {zettel.source.title}
 </a>
 ) : (
 <p className="text-[12px] text-[var(--alfred-text-tertiary)]">
 {zettel.source.title}
 </p>
 )}
 <p className="mt-1 text-[10px] text-[var(--alfred-text-tertiary)]">
 Captured {capturedAgo} · Reviewed {reviewedAgo}
 </p>
 </div>

 {/* Quiz stats */}
 {zettel.quizHistory.attempts > 0 && (
 <div>
 <div className="font-medium text-[9px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] mb-2">
 Quiz Performance
 </div>
 <p className="font-data text-lg tabular-nums">
 {zettel.quizHistory.correct}/{zettel.quizHistory.attempts}
 <span className="ml-2 text-[10px] text-[var(--alfred-text-tertiary)]">
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
 onClick={startEdit}
 >
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
 </aside>
 );
}
