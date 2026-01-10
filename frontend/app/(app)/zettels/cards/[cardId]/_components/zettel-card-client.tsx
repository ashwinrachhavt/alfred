"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ArrowLeft, Link2, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  bulkUpdateZettelCards,
  getZettelCard,
  linkZettelCard,
  listZettelLinks,
  suggestZettelLinks,
} from "@/lib/api/zettels";
import type { LinkSuggestion, ZettelCardOut, ZettelLinkOut } from "@/lib/api/types/zettels";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function formatError(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

export function ZettelCardClient({ cardId }: { cardId: number }) {
  const [card, setCard] = useState<ZettelCardOut | null>(null);
  const [links, setLinks] = useState<ZettelLinkOut[]>([]);
  const [suggestions, setSuggestions] = useState<LinkSuggestion[] | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editTitle, setEditTitle] = useState("");
  const [editTopic, setEditTopic] = useState("");
  const [editTags, setEditTags] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editSummary, setEditSummary] = useState("");

  const [linkToId, setLinkToId] = useState("");
  const [linkType, setLinkType] = useState("reference");
  const [linkContext, setLinkContext] = useState("");
  const [linkBidirectional, setLinkBidirectional] = useState(true);

  const [suggestMinConfidence, setSuggestMinConfidence] = useState(0.6);
  const [suggestLimit, setSuggestLimit] = useState(10);

  const parsedTags = useMemo(() => {
    const raw = editTags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    return raw.length ? raw : null;
  }, [editTags]);

  async function load() {
    if (!Number.isFinite(cardId)) return;
    setIsLoading(true);
    setError(null);
    try {
      const [c, l] = await Promise.all([getZettelCard(cardId), listZettelLinks(cardId)]);
      setCard(c);
      setLinks(l);
      setSuggestions(null);
      setEditTitle(c.title ?? "");
      setEditTopic(c.topic ?? "");
      setEditTags((c.tags ?? []).join(", "));
      setEditContent(c.content ?? "");
      setEditSummary(c.summary ?? "");
    } catch (err) {
      setError(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cardId]);

  async function saveEdits() {
    if (!card) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await bulkUpdateZettelCards([
        {
          id: card.id,
          title: editTitle.trim() || null,
          topic: editTopic.trim() || null,
          tags: parsedTags,
          content: editContent.trim() || null,
          summary: editSummary.trim() || null,
        },
      ]);
      toast.success("Saved.");
      if (res.updated_ids.includes(card.id)) await load();
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function createLink() {
    const toId = Number(linkToId.trim());
    if (!Number.isFinite(toId)) {
      toast.error("Enter a valid card id to link to.");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const res = await linkZettelCard(cardId, {
        to_card_id: toId,
        type: linkType.trim() || "reference",
        context: linkContext.trim() || null,
        bidirectional: linkBidirectional,
      });
      setLinks(res);
      toast.success("Link created.");
      setLinkToId("");
      setLinkContext("");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function runSuggestions() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await suggestZettelLinks(
        cardId,
        {},
        {
          min_confidence: Math.max(0, Math.min(1, suggestMinConfidence)),
          limit: Math.max(1, Math.min(50, suggestLimit)),
        },
      );
      setSuggestions(res);
      toast.success("Suggestions ready.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setIsLoading(false);
    }
  }

  if (!Number.isFinite(cardId)) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Card</h1>
        <p className="text-muted-foreground text-sm">Invalid card id.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button asChild variant="ghost" size="sm">
            <Link href="/zettels">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Back to Zettels
            </Link>
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={isLoading}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>
        </div>

        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">
            {card?.title?.trim() || (isLoading ? "Loading…" : "Card")}
          </h1>
          {card ? (
            <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="secondary">id: {card.id}</Badge>
              {card.topic ? <Badge variant="outline">topic: {card.topic}</Badge> : null}
              <Badge variant="outline">status: {card.status}</Badge>
            </div>
          ) : null}
        </div>
      </header>

      {error ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Error</CardTitle>
          </CardHeader>
          <CardContent className="text-destructive text-sm">{error}</CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Edit card</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="zcTitle">Title</Label>
              <Input id="zcTitle" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="zcTopic">Topic</Label>
                <Input id="zcTopic" value={editTopic} onChange={(e) => setEditTopic(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="zcTags">Tags (comma-separated)</Label>
                <Input id="zcTags" value={editTags} onChange={(e) => setEditTags(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="zcSummary">Summary</Label>
              <Textarea id="zcSummary" value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="zcContent">Content</Label>
              <Textarea id="zcContent" value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={8} />
            </div>
            <Button type="button" onClick={() => void saveEdits()} disabled={!card || isLoading}>
              Save
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Links</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
              <div className="space-y-2">
                <Label htmlFor="zcLinkTo">Link to card id</Label>
                <Input id="zcLinkTo" value={linkToId} onChange={(e) => setLinkToId(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="zcLinkType">Type</Label>
                <Input id="zcLinkType" value={linkType} onChange={(e) => setLinkType(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="zcLinkContext">Context (optional)</Label>
              <Textarea id="zcLinkContext" value={linkContext} onChange={(e) => setLinkContext(e.target.value)} rows={3} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" onClick={() => void createLink()} disabled={isLoading}>
                <Link2 className="h-4 w-4" aria-hidden="true" />
                Link
              </Button>
              <label className="text-muted-foreground flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  className="accent-primary"
                  checked={linkBidirectional}
                  onChange={(e) => setLinkBidirectional(e.target.checked)}
                />
                bidirectional
              </label>
            </div>

            <Separator />

            {links.length ? (
              <div className="space-y-2">
                {links.map((link) => (
                  <div key={link.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3">
                    <div className="text-sm">
                      <span className="font-medium">{link.type}</span>{" "}
                      <span className="text-muted-foreground">→</span>{" "}
                      <Link className="text-primary underline underline-offset-2" href={`/zettels/cards/${link.to_card_id}`}>
                        {link.to_card_id}
                      </Link>
                      {link.context ? <p className="text-muted-foreground mt-1 text-xs">{link.context}</p> : null}
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {link.id}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No links yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Suggest links</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
            <div className="space-y-2">
              <Label htmlFor="zcMinConf">Min confidence</Label>
              <Input
                id="zcMinConf"
                inputMode="decimal"
                value={String(suggestMinConfidence)}
                onChange={(e) => setSuggestMinConfidence(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="zcSuggestLimit">Limit</Label>
              <Input
                id="zcSuggestLimit"
                inputMode="numeric"
                value={String(suggestLimit)}
                onChange={(e) => setSuggestLimit(Number(e.target.value))}
              />
            </div>
            <Button type="button" onClick={() => void runSuggestions()} disabled={isLoading}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              Suggest
            </Button>
          </div>

          {suggestions ? (
            suggestions.length ? (
              <div className="space-y-2">
                {suggestions.map((s) => (
                  <div key={s.to_card_id} className="rounded-lg border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium">
                          <Link className="text-primary underline underline-offset-2" href={`/zettels/cards/${s.to_card_id}`}>
                            {s.to_title}
                          </Link>{" "}
                          <span className="text-muted-foreground text-sm">({s.to_card_id})</span>
                        </p>
                        <p className="text-muted-foreground mt-1 text-sm">{s.reason}</p>
                      </div>
                      <Badge variant="secondary" className="shrink-0">
                        {s.scores.confidence}
                      </Badge>
                    </div>
                    <div className="text-muted-foreground mt-3 text-xs">
                      score: {s.scores.composite_score.toFixed(2)} · semantic:{" "}
                      {s.scores.semantic_score.toFixed(2)} · tags: {s.scores.tag_overlap.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No suggestions.</p>
            )
          ) : (
            <p className="text-muted-foreground text-sm">
              Generate suggestions to find high-confidence neighbors.
            </p>
          )}

          {suggestions ? <JsonViewer value={suggestions} title="Raw suggestions" collapsed /> : null}
        </CardContent>
      </Card>

      {card ? <JsonViewer value={card} title="Raw card" collapsed /> : null}
    </div>
  );
}

