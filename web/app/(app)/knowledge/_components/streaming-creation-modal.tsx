"use client";

import { useCallback, useEffect, useRef } from "react";

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { useZettelCreationStore } from "@/lib/stores/zettel-creation-store";
import {
  Check,
  Loader2,
  X,
  Link2,
  Brain,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPatchJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function StepIndicator({
  done,
  active,
  label,
}: {
  done: boolean;
  active?: boolean;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done ? (
        <Check className="size-3.5 text-green-500" />
      ) : active ? (
        <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
      ) : (
        <div className="size-3.5 rounded-full border border-muted-foreground/30" />
      )}
      <span className={done ? "text-foreground" : "text-muted-foreground"}>
        {label}
      </span>
    </div>
  );
}

function EnrichmentRow({
  label,
  value,
  accepted,
  onToggle,
}: {
  label: string;
  value: string;
  accepted: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <div className="flex-1 min-w-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <p className="text-foreground truncate">{value}</p>
      </div>
      <button
        onClick={onToggle}
        className={`mt-1 size-5 rounded flex items-center justify-center border transition-colors shrink-0 ${
          accepted
            ? "border-green-500 bg-green-500/10 text-green-500"
            : "border-muted-foreground/30 text-muted-foreground"
        }`}
      >
        {accepted && <Check className="size-3" />}
      </button>
    </div>
  );
}

export function StreamingCreationModal({ open, onOpenChange }: Props) {
  const store = useZettelCreationStore();
  const queryClient = useQueryClient();
  const thinkingRef = useRef<HTMLDivElement>(null);

  // Auto-scroll thinking block
  useEffect(() => {
    if (thinkingRef.current) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
    }
  }, [store.thinkingBuffer]);

  const handleApplyAndClose = useCallback(async () => {
    if (!store.cardId) {
      onOpenChange(false);
      store.reset();
      return;
    }

    const patch: Record<string, unknown> = {};
    if (store.enrichment) {
      if (store.acceptedEnrichments.has("title") && store.enrichment.suggested_title) {
        patch.title = store.enrichment.suggested_title;
      }
      if (store.acceptedEnrichments.has("summary") && store.enrichment.summary) {
        patch.summary = store.enrichment.summary;
      }
      if (store.acceptedEnrichments.has("tags") && store.enrichment.suggested_tags.length > 0) {
        patch.tags = store.enrichment.suggested_tags;
      }
      if (store.acceptedEnrichments.has("topic") && store.enrichment.suggested_topic) {
        patch.topic = store.enrichment.suggested_topic;
      }
    }

    if (Object.keys(patch).length > 0) {
      try {
        await apiPatchJson(apiRoutes.zettels.cardById(store.cardId), patch);
      } catch {
        // Non-critical
      }
    }

    for (const linkId of store.rejectedLinkIds) {
      try {
        await fetch(apiRoutes.zettels.deleteLink(linkId), { method: "DELETE" });
      } catch {
        // Non-critical
      }
    }

    queryClient.invalidateQueries({ queryKey: ["zettels"] });
    onOpenChange(false);
    store.reset();
  }, [store, onOpenChange, queryClient]);

  const handleClose = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["zettels"] });
    onOpenChange(false);
    store.reset();
  }, [onOpenChange, store, queryClient]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px] p-0 gap-0 overflow-hidden max-h-[80vh] flex flex-col">
        <VisuallyHidden>
          <DialogTitle>Creating Zettel</DialogTitle>
        </VisuallyHidden>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b">
          <span className="text-sm font-medium text-foreground">
            {store.phase === "complete" ? "Zettel Created" : "Creating Zettel..."}
          </span>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Progress Steps */}
          <div className="space-y-2">
            <StepIndicator
              done={store.steps.card_saved}
              active={store.phase === "streaming" && !store.steps.card_saved}
              label="Card saved"
            />
            <StepIndicator
              done={store.steps.embedding_done}
              active={store.steps.card_saved && !store.steps.embedding_done}
              label="Embedding generated"
            />
            <StepIndicator
              done={store.steps.links_searched}
              active={store.steps.embedding_done && !store.steps.links_searched}
              label="Knowledge base searched"
            />
            <StepIndicator
              done={store.steps.ai_complete}
              active={store.steps.card_saved && !store.steps.ai_complete}
              label="AI analysis complete"
            />
          </div>

          {/* Thinking Block */}
          {store.thinkingBuffer && (
            <details className="group">
              <summary className="flex items-center gap-2 cursor-pointer text-xs text-[var(--alfred-text-tertiary)] hover:text-muted-foreground transition-colors">
                <Brain className="size-3" />
                AI Thinking
              </summary>
              <div
                ref={thinkingRef}
                className="mt-2 p-3 rounded-md border border-[var(--alfred-ruled-line)] bg-card max-h-[200px] overflow-y-auto"
              >
                <pre className="font-mono text-xs text-[var(--alfred-text-tertiary)] whitespace-pre-wrap break-words leading-relaxed">
                  {store.thinkingBuffer}
                  {store.phase === "streaming" && (
                    <span className="animate-pulse">|</span>
                  )}
                </pre>
              </div>
            </details>
          )}

          {/* Enrichment Suggestions */}
          {store.enrichment && (
            <div className="rounded-md border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-3.5 text-[#E8590C]" />
                Enrichment
              </div>
              {store.enrichment.suggested_title && (
                <EnrichmentRow
                  label="Title"
                  value={store.enrichment.suggested_title}
                  accepted={store.acceptedEnrichments.has("title")}
                  onToggle={() => store.toggleEnrichment("title")}
                />
              )}
              {store.enrichment.summary && (
                <EnrichmentRow
                  label="Summary"
                  value={store.enrichment.summary}
                  accepted={store.acceptedEnrichments.has("summary")}
                  onToggle={() => store.toggleEnrichment("summary")}
                />
              )}
              {store.enrichment.suggested_tags.length > 0 && (
                <EnrichmentRow
                  label="Tags"
                  value={store.enrichment.suggested_tags.join(", ")}
                  accepted={store.acceptedEnrichments.has("tags")}
                  onToggle={() => store.toggleEnrichment("tags")}
                />
              )}
              {store.enrichment.suggested_topic && (
                <EnrichmentRow
                  label="Topic"
                  value={store.enrichment.suggested_topic}
                  accepted={store.acceptedEnrichments.has("topic")}
                  onToggle={() => store.toggleEnrichment("topic")}
                />
              )}
            </div>
          )}

          {/* Link Suggestions */}
          {store.linkSuggestions.length > 0 && (
            <div className="rounded-md border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Link2 className="size-3.5 text-[#E8590C]" />
                {store.linkSuggestions.length} Links Found
              </div>
              {store.linkSuggestions.map((link) => {
                const autoLink = store.createdLinks.find(
                  (l) =>
                    l.target_id === link.card_id ||
                    l.source_id === link.card_id,
                );
                const isRejected = autoLink
                  ? store.rejectedLinkIds.has(autoLink.id)
                  : false;

                return (
                  <div
                    key={link.card_id}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="truncate block">{link.title}</span>
                      <span className="text-xs text-muted-foreground">
                        {link.reason}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {(link.score * 100).toFixed(0)}%
                      </span>
                      {autoLink && (
                        <button
                          onClick={() => store.toggleLink(autoLink.id)}
                          className={`size-5 rounded flex items-center justify-center border transition-colors ${
                            isRejected
                              ? "border-muted-foreground/30 text-muted-foreground"
                              : "border-green-500 bg-green-500/10 text-green-500"
                          }`}
                        >
                          {!isRejected && <Check className="size-3" />}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Decomposition */}
          {store.decomposition && !store.decomposition.is_atomic && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-amber-500">
                <AlertTriangle className="size-3.5" />
                Decomposition Suggested
              </div>
              <p className="text-xs text-muted-foreground">
                {store.decomposition.reason}
              </p>
              {store.decomposition.suggested_cards.map((card, i) => (
                <div
                  key={i}
                  className="text-xs pl-3 border-l-2 border-amber-500/30"
                >
                  <span className="font-medium">{card.title}</span>
                </div>
              ))}
            </div>
          )}

          {/* Knowledge Gaps */}
          {store.gaps &&
            (store.gaps.missing_topics.length > 0 ||
              store.gaps.weak_areas.length > 0) && (
              <div className="rounded-md border bg-card p-4 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Brain className="size-3.5 text-muted-foreground" />
                  Knowledge Gaps
                </div>
                {store.gaps.missing_topics.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    No cards on: {store.gaps.missing_topics.join(", ")}
                  </p>
                )}
                {store.gaps.weak_areas.map((area, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    {area.topic}: {area.note} ({area.existing_count} cards)
                  </p>
                ))}
              </div>
            )}

          {/* Errors (non-fatal) */}
          {store.errors.length > 0 && (
            <div className="text-xs text-muted-foreground space-y-1">
              {store.errors.map((err, i) => (
                <p key={i} className="text-amber-500">
                  {err.step}: {err.message}
                </p>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {store.phase === "complete" && (
          <div className="border-t px-5 py-3 flex justify-end">
            <button
              onClick={handleApplyAndClose}
              className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Apply & Close
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
