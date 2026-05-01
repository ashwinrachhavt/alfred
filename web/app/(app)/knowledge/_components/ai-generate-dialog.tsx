"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import {
  Check,
  ChevronDown,
  FileText,
  Link2,
  Loader2,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateZettel } from "@/features/zettels/mutations";
import { useCardSearch, useZettelTopics } from "@/features/zettels/queries";
import {
  createZettelLink,
  streamGeneratedZettelPreview,
  type AIGeneratePayload,
  type CardSearchMatch,
  type ZettelCardCreatePayload,
} from "@/lib/api/zettels";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const GENERATION_STEPS = [
  "Reading the input",
  "Extracting the atomic idea",
  "Writing the card",
  "Suggesting tags",
  "Finding nearby concepts",
];

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim().toLowerCase())
    .filter(Boolean);
}

function formatTags(tags: string[] | null | undefined): string {
  return (tags ?? []).join(", ");
}

function inputLooksLikeContent(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length > 140 || trimmed.includes("\n");
}

function buildPayload(input: string, topic: string, tags: string): AIGeneratePayload {
  const trimmed = input.trim();
  const tagList = parseTags(tags);
  const looksLikeContent = inputLooksLikeContent(trimmed);
  return {
    prompt: looksLikeContent ? undefined : trimmed,
    content: looksLikeContent ? trimmed : undefined,
    topic: topic.trim() || undefined,
    tags: tagList.length > 0 ? tagList : undefined,
  };
}

function normalizeDraft(draft: ZettelCardCreatePayload): ZettelCardCreatePayload {
  return {
    ...draft,
    title: draft.title.trim() || "Untitled",
    content: draft.content?.trim() || "",
    summary: draft.summary?.trim() || "",
    topic: draft.topic?.trim() || undefined,
    tags: draft.tags?.map((tag) => tag.trim().toLowerCase()).filter(Boolean) ?? [],
    status: draft.status || "active",
    importance: draft.importance ?? 5,
    confidence: draft.confidence ?? 0.7,
  };
}

function decodeJsonStringFragment(value: string): string {
  return value
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, "\\");
}

function extractPartialJsonStringField(raw: string, field: string): string | null {
  const keyIndex = raw.indexOf(`"${field}"`);
  if (keyIndex === -1) return null;

  const colonIndex = raw.indexOf(":", keyIndex);
  if (colonIndex === -1) return null;

  const valueStart = raw.indexOf('"', colonIndex + 1);
  if (valueStart === -1) return null;

  let escaped = false;
  let value = "";
  for (let index = valueStart + 1; index < raw.length; index += 1) {
    const character = raw[index];
    if (escaped) {
      value += `\\${character}`;
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (character === '"') break;
    value += character;
  }

  return decodeJsonStringFragment(value);
}

function formatGeneratedStream(raw: string): string {
  const title = extractPartialJsonStringField(raw, "title");
  const summary = extractPartialJsonStringField(raw, "summary");
  const content = extractPartialJsonStringField(raw, "content");

  const sections = [
    title ? `Title\n${title}` : null,
    summary ? `Summary\n${summary}` : null,
    content ? `Content\n${content}` : null,
  ].filter(Boolean);

  return sections.length > 0 ? sections.join("\n\n") : raw;
}

export function AIGenerateDialog({ open, onOpenChange }: Props) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [topic, setTopic] = useState("");
  const [tags, setTags] = useState("");
  const [draft, setDraft] = useState<ZettelCardCreatePayload | null>(null);
  const [draftTags, setDraftTags] = useState("");
  const [selectedRelatedIds, setSelectedRelatedIds] = useState<Set<number>>(new Set());
  const [relatedSelectionTouched, setRelatedSelectionTouched] = useState(false);
  const [generationStep, setGenerationStep] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedText, setGeneratedText] = useState("");
  const [showGeneratedText, setShowGeneratedText] = useState(false);
  const streamAbortRef = useRef<AbortController | null>(null);

  const createMutation = useCreateZettel();
  const topicsQuery = useZettelTopics();

  const previewQuery = useMemo(() => {
    if (!draft) return null;
    const text = [draft.title, draft.summary, draft.topic].filter(Boolean).join(" ");
    return text.trim().length > 2 ? text.trim() : null;
  }, [draft]);

  const relatedQuery = useCardSearch(previewQuery, undefined);
  const relatedCards = useMemo<CardSearchMatch[]>(() => {
    const seen = new Set<number>();
    return (relatedQuery.data?.text_matches ?? [])
      .filter((card) => {
        if (seen.has(card.id)) return false;
        seen.add(card.id);
        return true;
      })
      .slice(0, 4);
  }, [relatedQuery.data?.text_matches]);
  const defaultRelatedIds = useMemo(
    () => relatedCards.slice(0, 3).map((card) => card.id),
    [relatedCards],
  );
  const draftTagList = useMemo(() => parseTags(draftTags), [draftTags]);
  const summaryRows = draft
    ? Math.min(4, Math.max(2, Math.ceil((draft.summary ?? "").length / 72)))
    : 3;
  const contentRows = draft
    ? Math.min(14, Math.max(7, Math.ceil((draft.content ?? "").length / 82)))
    : 8;
  const readableGeneratedText = useMemo(
    () => formatGeneratedStream(generatedText),
    [generatedText],
  );

  const reset = useCallback(() => {
    setInput("");
    setTopic("");
    setTags("");
    setDraft(null);
    setDraftTags("");
    setSelectedRelatedIds(new Set());
    setRelatedSelectionTouched(false);
    setGenerationStep(0);
    setGeneratedText("");
    setShowGeneratedText(false);
    setIsGenerating(false);
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && !createMutation.isPending) {
        reset();
      }
      onOpenChange(nextOpen);
    },
    [createMutation.isPending, onOpenChange, reset],
  );

  useEffect(() => {
    if (!isGenerating) return;
    const timer = window.setInterval(() => {
      setGenerationStep((step) => (step + 1) % GENERATION_STEPS.length);
    }, 900);
    return () => window.clearInterval(timer);
  }, [isGenerating]);

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
    };
  }, []);

  const handleGeneratePreview = useCallback(async () => {
    if (!input.trim()) return;
    const payload = buildPayload(input, topic, tags);
    const controller = new AbortController();
    streamAbortRef.current?.abort();
    streamAbortRef.current = controller;
    setDraft(null);
    setDraftTags("");
    setSelectedRelatedIds(new Set());
    setRelatedSelectionTouched(false);
    setGeneratedText("");
    setShowGeneratedText(true);
    setIsGenerating(true);

    let streamedError: Error | null = null;
    let receivedDraft = false;
    try {
      await streamGeneratedZettelPreview(
        payload,
        {
          onToken: (token) => {
            setGeneratedText((current) => current + token);
          },
          onDone: (nextDraft) => {
            receivedDraft = true;
            const normalizedDraft = normalizeDraft(nextDraft);
            setDraft(normalizedDraft);
            setDraftTags(formatTags(normalizedDraft.tags));
          },
          onError: (error) => {
            streamedError = error;
          },
        },
        controller.signal,
      );
      if (streamedError) throw streamedError;
      if (!receivedDraft && !controller.signal.aborted) {
        throw new Error("Generation stream ended before a draft was returned.");
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      toast.error(error instanceof Error ? error.message : "Generation failed.");
    } finally {
      if (streamAbortRef.current === controller) {
        streamAbortRef.current = null;
      }
      if (!controller.signal.aborted) {
        setIsGenerating(false);
      }
    }
  }, [input, tags, topic]);

  const handleRegenerate = useCallback(() => {
    void handleGeneratePreview();
  }, [handleGeneratePreview]);

  const handleGenerateShortcut = useCallback(
    (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      if (
        event.key !== "Enter" ||
        event.shiftKey ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.nativeEvent.isComposing
      ) {
        return;
      }

      if (!input.trim() || isGenerating) return;
      event.preventDefault();
      void handleGeneratePreview();
    },
    [handleGeneratePreview, input, isGenerating],
  );

  const handleSave = useCallback(async () => {
    if (!draft) return;
    const payload = normalizeDraft({
      ...draft,
      tags: parseTags(draftTags),
    });
    const relatedIdsToLink = relatedSelectionTouched
      ? Array.from(selectedRelatedIds)
      : defaultRelatedIds;

    try {
      const created = await createMutation.mutateAsync(payload);
      const selectedIds = relatedIdsToLink.filter((id) => id !== created.id);
      await Promise.all(
        selectedIds.map((id) =>
          createZettelLink(created.id, {
            to_card_id: id,
            type: "reference",
            context: "Suggested during AI zettel creation.",
            bidirectional: true,
          }),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: ["zettels"] });
      toast.success("Zettel saved");
      reset();
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save zettel.");
    }
  }, [
    createMutation,
    draft,
    draftTags,
    onOpenChange,
    queryClient,
    defaultRelatedIds,
    relatedSelectionTouched,
    reset,
    selectedRelatedIds,
  ]);

  const hasInput = input.trim().length > 0;
  const inferredMode = inputLooksLikeContent(input) ? "content" : "topic";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-1rem)] w-[calc(100vw-1rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:w-[calc(100vw-2rem)] sm:max-w-[1120px] lg:max-h-[min(900px,calc(100dvh-2rem))]">
        <DialogHeader className="border-b px-5 pt-5 pb-4 sm:px-8 sm:pt-6">
          <DialogTitle className="flex items-center gap-2 text-xl sm:text-2xl">
            <Sparkles className="text-primary size-5" />
            AI Generate Zettel
          </DialogTitle>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto px-5 py-5 sm:px-8">
          {!draft ? (
            <div className="space-y-5">
              <div className="space-y-2">
                <label className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                  Capture
                </label>
                <Textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleGenerateShortcut}
                  placeholder='Write a topic, paste source text, or drop a rough thought like "CAP theorem and practical tradeoffs"...'
                  rows={8}
                  className="resize-none text-[14px] leading-6"
                  autoFocus
                />
                <p className="text-xs text-[var(--alfred-text-tertiary)]">
                  {inferredMode === "content"
                    ? "Looks like source content. Alfred will extract one atomic zettel."
                    : "Looks like a topic. Alfred will write a concise knowledge card."}
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                    Topic
                  </label>
                  <Input
                    value={topic}
                    onChange={(event) => setTopic(event.target.value)}
                    onKeyDown={handleGenerateShortcut}
                    list="zettel-topic-options"
                    placeholder="Optional domain"
                    className="text-sm"
                  />
                  <datalist id="zettel-topic-options">
                    {(topicsQuery.data ?? []).map((existingTopic) => (
                      <option key={existingTopic} value={existingTopic} />
                    ))}
                  </datalist>
                </div>
                <div className="space-y-2">
                  <label className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                    Tags
                  </label>
                  <Input
                    value={tags}
                    onChange={(event) => setTags(event.target.value)}
                    onKeyDown={handleGenerateShortcut}
                    placeholder="optional, comma-separated"
                    className="text-sm"
                  />
                </div>
              </div>

              {isGenerating ? (
                <div className="rounded-md border bg-[var(--alfred-accent-subtle)] px-4 py-3">
                  <div className="text-primary flex items-center gap-2 text-sm">
                    <Loader2 className="size-4 animate-spin" />
                    {GENERATION_STEPS[generationStep]}
                  </div>
                  <div className="bg-background/80 mt-3 max-h-48 overflow-y-auto rounded-sm border p-3">
                    <p className="mb-2 text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                      Generated Text
                    </p>
                    <pre className="text-foreground text-sm leading-6 break-words whitespace-pre-wrap">
                      {readableGeneratedText || "Waiting for first token..."}
                    </pre>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="space-y-4">
                <div className="bg-card rounded-lg border">
                  <div className="flex items-start justify-between gap-3 border-b px-4 py-4 sm:px-5">
                    <div>
                      <p className="text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                        Draft Preview
                      </p>
                      <p className="text-muted-foreground text-xs">
                        Edit the card before it enters the corpus.
                      </p>
                    </div>
                    <span className="text-primary rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-1 text-[10px] font-medium uppercase">
                      Unsaved
                    </span>
                  </div>

                  <div className="space-y-4 px-4 py-4 sm:px-5">
                    <Input
                      value={draft.title}
                      onChange={(event) =>
                        setDraft((current) =>
                          current ? { ...current, title: event.target.value } : current,
                        )
                      }
                      aria-label="Draft title"
                      className="h-auto border-none px-0 py-1 font-serif text-[clamp(1.4rem,2vw,1.85rem)] leading-tight shadow-none focus-visible:ring-0"
                    />
                    <Textarea
                      value={draft.summary ?? ""}
                      onChange={(event) =>
                        setDraft((current) =>
                          current ? { ...current, summary: event.target.value } : current,
                        )
                      }
                      rows={summaryRows}
                      className="resize-none bg-[var(--alfred-accent-subtle)] text-base leading-7"
                      placeholder="One-sentence distillation"
                    />
                    <Textarea
                      value={draft.content ?? ""}
                      onChange={(event) =>
                        setDraft((current) =>
                          current ? { ...current, content: event.target.value } : current,
                        )
                      }
                      rows={contentRows}
                      className="resize-none text-base leading-7"
                      placeholder="Card content"
                    />
                    <div className="grid gap-3 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                      <label className="space-y-1.5">
                        <span className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                          Topic
                        </span>
                        <Input
                          value={draft.topic ?? ""}
                          onChange={(event) =>
                            setDraft((current) =>
                              current ? { ...current, topic: event.target.value } : current,
                            )
                          }
                          placeholder="Topic"
                          className="text-sm"
                        />
                      </label>
                      <label className="space-y-1.5">
                        <span className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                          Tags
                        </span>
                        <Textarea
                          value={draftTags}
                          onChange={(event) => setDraftTags(event.target.value)}
                          placeholder="comma-separated tags"
                          rows={2}
                          className="min-h-[44px] resize-none text-sm leading-5"
                        />
                      </label>
                    </div>
                    {draftTagList.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {draftTagList.map((tag) => (
                          <Badge
                            key={tag}
                            variant="secondary"
                            className="rounded-sm bg-[var(--alfred-accent-muted)] px-2 py-1 text-[10px] font-medium tracking-wide uppercase"
                          >
                            {tag}
                            <button
                              type="button"
                              onClick={() =>
                                setDraftTags(
                                  formatTags(
                                    draftTagList.filter((currentTag) => currentTag !== tag),
                                  ),
                                )
                              }
                              className="text-muted-foreground hover:text-foreground -mr-0.5 ml-0.5"
                              aria-label={`Remove ${tag} tag`}
                            >
                              <X className="size-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              <aside className="bg-card self-start rounded-lg border p-4">
                <div className="mb-4 flex items-start gap-2.5">
                  <Link2 className="text-primary mt-0.5 size-4" />
                  <div>
                    <p className="text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                      Connections Found
                    </p>
                    <p className="text-muted-foreground text-xs">
                      Checked cards will be linked on save.
                    </p>
                  </div>
                </div>

                {relatedQuery.isLoading ? (
                  <div className="text-muted-foreground flex items-center gap-2 py-4 text-xs">
                    <Loader2 className="size-3.5 animate-spin" />
                    Searching corpus
                  </div>
                ) : relatedCards.length > 0 ? (
                  <div className="space-y-1.5">
                    {relatedCards.map((card) => {
                      const checked = relatedSelectionTouched
                        ? selectedRelatedIds.has(card.id)
                        : defaultRelatedIds.includes(card.id);
                      return (
                        <button
                          key={card.id}
                          type="button"
                          onClick={() =>
                            setSelectedRelatedIds((current) => {
                              setRelatedSelectionTouched(true);
                              const next = new Set(
                                relatedSelectionTouched ? current : defaultRelatedIds,
                              );
                              if (next.has(card.id)) next.delete(card.id);
                              else next.add(card.id);
                              return next;
                            })
                          }
                          className={cn(
                            "flex w-full items-start gap-2 rounded-md border px-2.5 py-2 text-left transition-colors",
                            checked
                              ? "border-primary/30 bg-[var(--alfred-accent-subtle)]"
                              : "hover:bg-secondary/60",
                          )}
                        >
                          <span
                            className={cn(
                              "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-sm border",
                              checked && "border-primary bg-primary text-primary-foreground",
                            )}
                          >
                            {checked ? <Check className="size-3" /> : null}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-medium">{card.title}</span>
                            {card.topic ? (
                              <span className="block truncate text-[10px] text-[var(--alfred-text-tertiary)] uppercase">
                                {card.topic}
                              </span>
                            ) : null}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-muted-foreground flex gap-2 py-2 text-xs leading-5">
                    <Link2 className="mt-0.5 size-3.5 shrink-0" />
                    <p>
                      No strong nearby cards found yet. Saving this zettel will still add it to the
                      corpus.
                    </p>
                  </div>
                )}

                {generatedText ? (
                  <div className="mt-4 border-t pt-4">
                    <button
                      type="button"
                      onClick={() => setShowGeneratedText((current) => !current)}
                      className="flex w-full items-center justify-between gap-2 text-left"
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <FileText className="text-primary size-4 shrink-0" />
                        <span>
                          <span className="block text-[10px] font-medium text-[var(--alfred-text-tertiary)] uppercase">
                            Generated Text
                          </span>
                          <span className="text-muted-foreground block text-xs">
                            Live text captured from the model stream.
                          </span>
                        </span>
                      </span>
                      <ChevronDown
                        className={cn(
                          "text-muted-foreground size-4 shrink-0 transition-transform",
                          showGeneratedText && "rotate-180",
                        )}
                      />
                    </button>
                    {showGeneratedText ? (
                      <div className="bg-secondary/50 mt-3 max-h-56 overflow-y-auto rounded-sm border px-3 py-2">
                        <pre className="text-foreground text-sm leading-6 break-words whitespace-pre-wrap">
                          {readableGeneratedText}
                        </pre>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </aside>
            </div>
          )}
        </div>

        <DialogFooter className="bg-background/95 border-t px-5 py-4 sm:px-8">
          {!draft ? (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)} className="text-xs">
                Cancel
              </Button>
              <Button
                onClick={handleGeneratePreview}
                disabled={!hasInput || isGenerating}
                className="gap-1.5 text-xs"
              >
                {isGenerating ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                Generate Preview
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  setDraft(null);
                  setDraftTags("");
                  setSelectedRelatedIds(new Set());
                  setRelatedSelectionTouched(false);
                }}
                className="text-muted-foreground gap-1.5 text-xs sm:mr-auto"
              >
                <Trash2 className="size-3.5" />
                Discard
              </Button>
              <Button
                variant="outline"
                onClick={handleRegenerate}
                disabled={isGenerating || createMutation.isPending}
                className="gap-1.5 text-xs"
              >
                <RotateCcw className="size-3.5" />
                Regenerate
              </Button>
              <Button
                onClick={handleSave}
                disabled={createMutation.isPending || isGenerating}
                className="gap-1.5 text-xs"
              >
                {createMutation.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Check className="size-3.5" />
                )}
                Create Zettel
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
