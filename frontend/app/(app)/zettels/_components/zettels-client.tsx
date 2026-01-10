"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Network, Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import {
  createZettelCard,
  getZettelsGraph,
  listDueZettelReviews,
  listZettelCards,
  completeZettelReview,
} from "@/lib/api/zettels";
import type { GraphSummary, ZettelCardOut, ZettelReviewOut } from "@/lib/api/types/zettels";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { JsonViewer } from "@/components/ui/json-viewer";

function formatError(err: unknown): string {
  return err instanceof Error ? err.message : "Something went wrong.";
}

export function ZettelsClient() {
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [tag, setTag] = useState("");
  const [limit, setLimit] = useState(50);
  const [skip, setSkip] = useState(0);

  const [cards, setCards] = useState<ZettelCardOut[]>([]);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [cardsError, setCardsError] = useState<string | null>(null);

  const [newTitle, setNewTitle] = useState("");
  const [newTopic, setNewTopic] = useState("");
  const [newTags, setNewTags] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newSummary, setNewSummary] = useState("");

  const [graph, setGraph] = useState<GraphSummary | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  const [reviewsLimit, setReviewsLimit] = useState(50);
  const [reviews, setReviews] = useState<ZettelReviewOut[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState(false);
  const [reviewScores, setReviewScores] = useState<Record<number, string>>({});

  const parsedNewTags = useMemo(() => {
    const raw = newTags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    return raw.length ? raw : null;
  }, [newTags]);

  async function loadCards() {
    setCardsLoading(true);
    setCardsError(null);
    try {
      const res = await listZettelCards({
        q: q.trim() || null,
        topic: topic.trim() || null,
        tag: tag.trim() || null,
        limit: Math.max(1, Math.min(200, limit)),
        skip: Math.max(0, skip),
      });
      setCards(res);
    } catch (err) {
      setCardsError(formatError(err));
    } finally {
      setCardsLoading(false);
    }
  }

  async function addCard() {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const created = await createZettelCard({
        title,
        topic: newTopic.trim() || null,
        tags: parsedNewTags,
        content: newContent.trim() || null,
        summary: newSummary.trim() || null,
      });
      toast.success("Card created.");
      setNewTitle("");
      setNewTopic("");
      setNewTags("");
      setNewContent("");
      setNewSummary("");
      setCards((prev) => [created, ...prev]);
    } catch (err) {
      toast.error(formatError(err));
    }
  }

  async function loadGraph() {
    setGraphLoading(true);
    try {
      const res = await getZettelsGraph();
      setGraph(res);
      toast.success("Graph loaded.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setGraphLoading(false);
    }
  }

  async function loadReviews() {
    setReviewsLoading(true);
    try {
      const res = await listDueZettelReviews(Math.max(1, Math.min(200, reviewsLimit)));
      setReviews(res);
      toast.success("Loaded due reviews.");
    } catch (err) {
      toast.error(formatError(err));
    } finally {
      setReviewsLoading(false);
    }
  }

  async function onCompleteReview(reviewId: number) {
    const raw = reviewScores[reviewId]?.trim() ?? "";
    const score = raw ? Number(raw) : null;
    if (score !== null && (!Number.isFinite(score) || score < 0 || score > 1)) {
      toast.error("Score must be between 0 and 1.");
      return;
    }

    try {
      const res = await completeZettelReview(reviewId, { score });
      toast.success("Review completed.");
      setReviews((prev) => prev.map((r) => (r.id === reviewId ? res : r)).filter((r) => !r.completed_at));
    } catch (err) {
      toast.error(formatError(err));
    }
  }

  useEffect(() => {
    void loadCards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex items-center gap-2">
          <Network className="text-muted-foreground h-5 w-5" aria-hidden="true" />
          <h1 className="text-3xl font-semibold tracking-tight">Zettels</h1>
        </div>
        <p className="text-muted-foreground">
          Capture atomic notes, connect them, and review them over time.
        </p>
      </header>

      <Tabs defaultValue="cards">
        <TabsList>
          <TabsTrigger value="cards">Cards</TabsTrigger>
          <TabsTrigger value="graph">Graph</TabsTrigger>
          <TabsTrigger value="reviews">Reviews</TabsTrigger>
        </TabsList>

        <TabsContent value="cards" className="mt-6 space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Create</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="zcNewTitle">Title</Label>
                  <Input
                    id="zcNewTitle"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="A single, sharp idea"
                    onKeyDown={(e) => {
                      if (e.key !== "Enter" || e.shiftKey) return;
                      e.preventDefault();
                      void addCard();
                    }}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="zcNewTopic">Topic</Label>
                    <Input
                      id="zcNewTopic"
                      value={newTopic}
                      onChange={(e) => setNewTopic(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="zcNewTags">Tags</Label>
                    <Input
                      id="zcNewTags"
                      value={newTags}
                      onChange={(e) => setNewTags(e.target.value)}
                      placeholder="comma, separated"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="zcNewSummary">Summary</Label>
                  <Textarea
                    id="zcNewSummary"
                    value={newSummary}
                    onChange={(e) => setNewSummary(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="zcNewContent">Content</Label>
                  <Textarea
                    id="zcNewContent"
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    rows={6}
                  />
                </div>
                <Button type="button" onClick={() => void addCard()} disabled={!newTitle.trim()}>
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Create
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Browse</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-2">
                    <Label htmlFor="zcQ">Query</Label>
                    <Input id="zcQ" value={q} onChange={(e) => setQ(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="zcTopic">Topic</Label>
                    <Input id="zcTopic" value={topic} onChange={(e) => setTopic(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="zcTag">Tag</Label>
                    <Input id="zcTag" value={tag} onChange={(e) => setTag(e.target.value)} />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
                  <div className="space-y-2">
                    <Label htmlFor="zcLimit">Limit</Label>
                    <Input
                      id="zcLimit"
                      inputMode="numeric"
                      value={String(limit)}
                      onChange={(e) => setLimit(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="zcSkip">Skip</Label>
                    <Input
                      id="zcSkip"
                      inputMode="numeric"
                      value={String(skip)}
                      onChange={(e) => setSkip(Number(e.target.value))}
                    />
                  </div>
                  <Button type="button" variant="outline" onClick={() => void loadCards()} disabled={cardsLoading}>
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    {cardsLoading ? "Loading…" : "Refresh"}
                  </Button>
                </div>

                {cardsError ? <p className="text-destructive text-sm">{cardsError}</p> : null}

                <Separator />

                {cards.length ? (
                  <div className="divide-border divide-y rounded-lg border">
                    {cards.map((card) => (
                      <Link
                        key={card.id}
                        href={`/zettels/cards/${card.id}`}
                        className="hover:bg-muted/30 block p-4 transition-colors"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate font-medium">{card.title}</p>
                            <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                              {card.summary || card.content || "—"}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {card.topic ? <Badge variant="secondary">{card.topic}</Badge> : null}
                              {(card.tags ?? []).slice(0, 4).map((t) => (
                                <Badge key={t} variant="outline">
                                  {t}
                                </Badge>
                              ))}
                            </div>
                          </div>
                          <Badge variant="outline" className="shrink-0">
                            {card.id}
                          </Badge>
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">
                    {cardsLoading ? "Loading…" : "No cards found."}
                  </p>
                )}

                {cards.length ? <JsonViewer value={cards} title="Raw cards" collapsed /> : null}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="graph" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Graph</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button type="button" variant="outline" onClick={() => void loadGraph()} disabled={graphLoading}>
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {graphLoading ? "Loading…" : "Load graph"}
              </Button>
              {graph ? (
                <div className="text-muted-foreground text-sm">
                  nodes: {graph.nodes.length} · edges: {graph.edges.length}
                </div>
              ) : null}
              {graph ? <JsonViewer value={graph} title="Graph response" collapsed /> : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="reviews" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Due reviews</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-2">
                  <Label htmlFor="zrLimit">Limit</Label>
                  <Input
                    id="zrLimit"
                    inputMode="numeric"
                    value={String(reviewsLimit)}
                    onChange={(e) => setReviewsLimit(Number(e.target.value))}
                  />
                </div>
                <Button type="button" variant="outline" onClick={() => void loadReviews()} disabled={reviewsLoading}>
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  {reviewsLoading ? "Loading…" : "Refresh"}
                </Button>
              </div>

              {reviews.length ? (
                <div className="space-y-3">
                  {reviews.map((review) => (
                    <div key={review.id} className="rounded-lg border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="space-y-1">
                          <p className="font-medium">
                            Review <span className="text-muted-foreground">#{review.id}</span>
                          </p>
                          <p className="text-muted-foreground text-xs">
                            card:{" "}
                            <Link
                              className="text-primary underline underline-offset-2"
                              href={`/zettels/cards/${review.card_id}`}
                            >
                              {review.card_id}
                            </Link>{" "}
                            · stage {review.stage} · due {new Date(review.due_at).toLocaleString()}
                          </p>
                        </div>
                        <Badge variant="outline">iteration {review.iteration}</Badge>
                      </div>

                      <div className="mt-3 flex flex-wrap items-end gap-2">
                        <div className="space-y-2">
                          <Label htmlFor={`score-${review.id}`}>Score (0..1 optional)</Label>
                          <Input
                            id={`score-${review.id}`}
                            inputMode="decimal"
                            value={reviewScores[review.id] ?? ""}
                            onChange={(e) =>
                              setReviewScores((prev) => ({ ...prev, [review.id]: e.target.value }))
                            }
                            placeholder="e.g. 0.8"
                          />
                        </div>
                        <Button
                          type="button"
                          onClick={() => void onCompleteReview(review.id)}
                          disabled={reviewsLoading}
                        >
                          Complete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">
                  {reviewsLoading ? "Loading…" : "No due reviews."}
                </p>
              )}

              {reviews.length ? <JsonViewer value={reviews} title="Raw reviews" collapsed /> : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

