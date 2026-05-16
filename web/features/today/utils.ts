import { parseISO } from "date-fns";

import type { TodayBriefingResponse, TodayCalendarDay } from "@/lib/api/today";

export type TodayAuditEventKind = "capture" | "stored" | "connection" | "review" | "gap";

export const TODAY_AUDIT_KINDS: TodayAuditEventKind[] = [
  "capture",
  "stored",
  "connection",
  "review",
  "gap",
];

export type TodayAuditEvent = {
  id: string;
  kind: TodayAuditEventKind;
  title: string;
  href: string;
  timestamp: string | null;
  meta: string;
  status?: string;
};

export type TodayInsightTone = "neutral" | "accent" | "warning" | "success";

export type TodayInsightCard = {
  id: "capture" | "stored" | "connection" | "review" | "gap" | "notes";
  label: string;
  value: string;
  metric: string;
  body: string;
  tone: TodayInsightTone;
};

export type TodayAction = {
  id: string;
  title: string;
  body: string;
  cta: string;
  href: string;
  tone: TodayInsightTone;
};

export type TodayThread = {
  id: string;
  name: string;
  cards: number;
  links: number;
  reviews: number;
  gaps: number;
  status: string;
};

function plural(value: number, noun: string): string {
  return `${value} ${noun}${value === 1 ? "" : "s"}`;
}

function normalizeThreadName(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed && trimmed.length > 0 ? trimmed : "Untopiced";
}

function getThreadKey(value: string): string {
  return value.toLowerCase();
}

function makeThreadId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function getTodayConnectionDebt(briefing: TodayBriefingResponse): number {
  return Math.max(briefing.stats.total_cards_created - briefing.stats.total_connections, 0);
}

export function getTodayReviewDebt(briefing: TodayBriefingResponse): number {
  return Math.max(briefing.stats.total_reviews_due - briefing.stats.total_reviews_completed, 0);
}

export function buildTodayThreads(briefing: TodayBriefingResponse, limit = 4): TodayThread[] {
  const threads = new Map<string, TodayThread>();
  const cardThreadByTitle = new Map<string, string>();

  for (const card of briefing.stored_cards) {
    const name = normalizeThreadName(card.topic ?? card.tags[0]);
    const key = getThreadKey(name);
    const existing =
      threads.get(key) ??
      ({
        id: makeThreadId(name) || "untopiced",
        name,
        cards: 0,
        links: 0,
        reviews: 0,
        gaps: 0,
        status: "emerging",
      } satisfies TodayThread);

    existing.cards += 1;
    threads.set(key, existing);
    cardThreadByTitle.set(card.title, key);
  }

  for (const connection of briefing.connections) {
    const key =
      cardThreadByTitle.get(connection.from_title) ?? cardThreadByTitle.get(connection.to_title);
    if (!key) continue;
    const thread = threads.get(key);
    if (thread) thread.links += 1;
  }

  for (const review of briefing.reviews) {
    const key = cardThreadByTitle.get(review.card_title);
    if (!key) continue;
    const thread = threads.get(key);
    if (thread) thread.reviews += 1;
  }

  if (briefing.gaps.length > 0) {
    const key = "knowledge-gaps";
    threads.set(key, {
      id: "knowledge-gaps",
      name: "Knowledge gaps",
      cards: 0,
      links: 0,
      reviews: 0,
      gaps: briefing.gaps.length,
      status: "needs fill-in",
    });
  }

  return [...threads.values()]
    .map((thread) => ({
      ...thread,
      status:
        thread.gaps > 0
          ? "needs fill-in"
          : thread.cards > 0 && thread.links === 0
            ? "needs synthesis"
            : thread.cards >= 3
              ? "active thread"
              : "emerging",
    }))
    .sort((left, right) => {
      const leftScore = left.cards * 3 + left.links * 2 + left.reviews + left.gaps;
      const rightScore = right.cards * 3 + right.links * 2 + right.reviews + right.gaps;
      if (rightScore !== leftScore) return rightScore - leftScore;
      return left.name.localeCompare(right.name);
    })
    .slice(0, limit);
}

export function buildTodayBriefingLines(briefing: TodayBriefingResponse): string[] {
  const reviewDebt = getTodayReviewDebt(briefing);
  const connectionDebt = getTodayConnectionDebt(briefing);
  const strongestThread = buildTodayThreads(briefing, 1)[0];

  if (briefing.stats.total_events === 0) {
    return [
      "No new knowledge landed on this date.",
      reviewDebt > 0
        ? `${plural(reviewDebt, "review")} still need attention, so this can be a review-and-connect day.`
        : "Use the quiet day to review due cards, connect recent notes, or resume yesterday's strongest thread.",
    ];
  }

  const cleared = briefing.stats.total_reviews_completed;
  const due = briefing.stats.total_reviews_due;
  const firstLine = `You captured ${plural(
    briefing.stats.total_captures,
    "source",
  )}, created ${plural(briefing.stats.total_cards_created, "card")}, and cleared ${cleared} of ${due} due reviews.`;

  const weakestSignal =
    connectionDebt > 0
      ? "connections"
      : reviewDebt > 0
        ? "reviews"
        : briefing.stats.total_gaps > 0
          ? "gap fill-in"
          : "follow-through";

  const secondLine = strongestThread
    ? `Your strongest thread was ${strongestThread.name}. Your weakest signal was ${weakestSignal}.`
    : `Your weakest signal was ${weakestSignal}.`;

  return [firstLine, secondLine];
}

export function buildTodayInsightCards(briefing: TodayBriefingResponse): TodayInsightCard[] {
  const connectionDebt = getTodayConnectionDebt(briefing);
  const reviewDebt = getTodayReviewDebt(briefing);

  return [
    {
      id: "capture",
      label: "Capture velocity",
      value: String(briefing.stats.total_captures),
      metric: plural(briefing.stats.total_captures, "new source"),
      body:
        briefing.stats.total_captures > 0
          ? "Fresh source material is available for distillation."
          : "No new source material was captured on this date.",
      tone: briefing.stats.total_captures > 0 ? "accent" : "neutral",
    },
    {
      id: "stored",
      label: "Distillation volume",
      value: String(briefing.stats.total_cards_created),
      metric: `${briefing.stats.total_cards_created} ${
        briefing.stats.total_cards_created === 1 ? "card" : "cards"
      } created`,
      body:
        briefing.stats.total_cards_created > 0
          ? "New durable cards are ready to be connected into the graph."
          : "No new cards were stored from this day's work.",
      tone: briefing.stats.total_cards_created > 0 ? "accent" : "neutral",
    },
    {
      id: "connection",
      label: "Connection debt",
      value: String(connectionDebt),
      metric:
        connectionDebt > 0
          ? `${connectionDebt} ${connectionDebt === 1 ? "card" : "cards"} without new links`
          : "no connection debt",
      body:
        connectionDebt > 0
          ? `${plural(
              briefing.stats.total_cards_created,
              "card",
            )} landed with only ${plural(briefing.stats.total_connections, "new link")}.`
          : "New knowledge is being linked as it lands.",
      tone: connectionDebt > 0 ? "warning" : "success",
    },
    {
      id: "review",
      label: "Review debt",
      value: String(reviewDebt),
      metric: `${briefing.stats.total_reviews_completed} cleared of ${briefing.stats.total_reviews_due}`,
      body:
        reviewDebt > 0
          ? `${plural(reviewDebt, "review")} still need attention.`
          : "No review debt remains for this date.",
      tone: reviewDebt > 0 ? "warning" : "success",
    },
    {
      id: "gap",
      label: "Knowledge gaps",
      value: String(briefing.stats.total_gaps),
      metric: plural(briefing.stats.total_gaps, "stub"),
      body:
        briefing.stats.total_gaps > 0
          ? "Placeholder cards need real synthesis before they become useful."
          : "No new stub cards were surfaced.",
      tone: briefing.stats.total_gaps > 0 ? "warning" : "success",
    },
    {
      id: "notes",
      label: "Notes touched",
      value: String(briefing.stats.total_notes_touched),
      metric: plural(briefing.stats.total_notes_touched, "note"),
      body:
        briefing.stats.total_notes_touched > 0
          ? "Active writing surfaces are evolving against the knowledge graph."
          : "No notes were edited on this date.",
      tone: briefing.stats.total_notes_touched > 0 ? "accent" : "neutral",
    },
  ];
}

export function buildTodayNextActions(briefing: TodayBriefingResponse): TodayAction[] {
  const actions: TodayAction[] = [];
  const reviewDebt = getTodayReviewDebt(briefing);
  const connectionDebt = getTodayConnectionDebt(briefing);
  const strongestThread = buildTodayThreads(briefing, 1)[0];

  if (reviewDebt > 0) {
    actions.push({
      id: "review-due",
      title: `Review ${plural(reviewDebt, "due card")}`,
      body: "Clear the spaced-repetition queue before new capture work piles on top.",
      cta: "Start review session",
      href: `/today?view=table&date=${briefing.date}`,
      tone: "warning",
    });
  }

  if (connectionDebt > 0) {
    actions.push({
      id: "connect-new-knowledge",
      title: `Connect ${plural(connectionDebt, "new card")}`,
      body: "The day's cards have not produced enough cross-links yet.",
      cta: "Open connection pass",
      href: "/knowledge",
      tone: "warning",
    });
  }

  if (strongestThread) {
    actions.push({
      id: "resume-thread",
      title: `Resume ${strongestThread.name}`,
      body:
        strongestThread.status === "needs synthesis"
          ? "This thread has new material but needs a synthesis pass."
          : "This was the strongest signal in the day's knowledge work.",
      cta: "Open knowledge",
      href: "/knowledge",
      tone: "accent",
    });
  }

  if (briefing.stats.total_gaps > 0) {
    actions.push({
      id: "fill-gaps",
      title: `Fill ${plural(briefing.stats.total_gaps, "surfaced gap")}`,
      body: "Turn placeholder cards into usable notes while the context is still warm.",
      cta: "Review gaps",
      href: "/knowledge",
      tone: "warning",
    });
  }

  if (actions.length === 0) {
    actions.push({
      id: "quiet-day",
      title: "Use the quiet day deliberately",
      body: "Review due cards, connect recent notes, or capture one high-signal source.",
      cta: "Open today workbench",
      href: `/today?view=table&date=${briefing.date}`,
      tone: "neutral",
    });
  }

  return actions.slice(0, 4);
}

function scoreTimestamp(timestamp: string | null): number {
  if (!timestamp) return Number.NEGATIVE_INFINITY;
  const parsed = parseISO(timestamp).getTime();
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
}

export function buildTodayTimeline(briefing: TodayBriefingResponse): TodayAuditEvent[] {
  const captures: TodayAuditEvent[] = briefing.captures.map((capture) => ({
    id: `capture-${capture.id}`,
    kind: "capture",
    title: capture.title,
    href: `/documents/${capture.id}`,
    timestamp: capture.created_at,
    meta: capture.pipeline_status,
    status: capture.pipeline_status,
  }));

  const storedCards: TodayAuditEvent[] = briefing.stored_cards.map((card) => ({
    id: `stored-${card.card_id}`,
    kind: "stored",
    title: card.title,
    href: `/knowledge/${card.card_id}`,
    timestamp: card.created_at,
    meta: card.topic
      ? `Topic: ${card.topic}`
      : card.tags.length > 0
        ? card.tags.join(" · ")
        : "Stored card",
    status: card.status,
  }));

  const connections: TodayAuditEvent[] = briefing.connections.map((connection) => ({
    id: `connection-${connection.link_id}`,
    kind: "connection",
    title: `${connection.from_title} → ${connection.to_title}`,
    href: `/knowledge/${connection.from_card_id}`,
    timestamp: connection.created_at,
    meta: `${connection.type} connection`,
  }));

  const reviews: TodayAuditEvent[] = briefing.reviews.map((review) => ({
    id: `review-${review.review_id}`,
    kind: "review",
    title: review.card_title,
    href: `/knowledge/${review.card_id}`,
    timestamp: review.due_at,
    meta: `Stage ${review.stage}`,
    status: review.status,
  }));

  const gaps: TodayAuditEvent[] = briefing.gaps.map((gap) => ({
    id: `gap-${gap.card_id}`,
    kind: "gap",
    title: gap.title,
    href: `/knowledge/${gap.card_id}`,
    timestamp: gap.created_at,
    meta: "Stub card surfaced",
    status: "stub",
  }));

  return [...captures, ...storedCards, ...connections, ...reviews, ...gaps].sort((left, right) => {
    return scoreTimestamp(right.timestamp) - scoreTimestamp(left.timestamp);
  });
}

export function getBriefingCountForKind(
  briefing: TodayBriefingResponse,
  kind: TodayAuditEventKind,
): number {
  switch (kind) {
    case "capture":
      return briefing.captures.length;
    case "stored":
      return briefing.stored_cards.length;
    case "connection":
      return briefing.connections.length;
    case "review":
      return briefing.reviews.length;
    case "gap":
      return briefing.gaps.length;
  }
}

export function getCalendarDayCountForKind(
  day: TodayCalendarDay,
  kind: TodayAuditEventKind,
): number {
  switch (kind) {
    case "capture":
      return day.captures;
    case "stored":
      return day.stored_cards;
    case "connection":
      return day.connections;
    case "review":
      return day.reviews_due;
    case "gap":
      return day.gaps;
  }
}

export function getCalendarDayTotalForKinds(
  day: TodayCalendarDay,
  kinds: Iterable<TodayAuditEventKind>,
): number {
  let total = 0;

  for (const kind of kinds) {
    total += getCalendarDayCountForKind(day, kind);
  }

  return total;
}

export function makeCalendarDayMap(days: TodayCalendarDay[]): Map<string, TodayCalendarDay> {
  return new Map(days.map((day) => [day.date, day]));
}
