import { parseISO } from "date-fns";

import type {
  TodayBriefingResponse,
  TodayCalendarDay,
} from "@/lib/api/today";

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
    meta: card.topic ? `Topic: ${card.topic}` : card.tags.length > 0 ? card.tags.join(" · ") : "Stored card",
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
