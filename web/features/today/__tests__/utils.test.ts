import { describe, expect, it } from "vitest";

import type { TodayBriefingResponse } from "@/lib/api/today";
import {
  TODAY_AUDIT_KINDS,
  buildTodayBriefingLines,
  buildTodayInsightCards,
  buildTodayNextActions,
  buildTodayTimeline,
  buildTodayThreads,
  getBriefingCountForKind,
  getCalendarDayCountForKind,
  getCalendarDayTotalForKinds,
  getTodayConnectionDebt,
  getTodayReviewDebt,
  makeCalendarDayMap,
} from "@/features/today/utils";

const briefing: TodayBriefingResponse = {
  date: "2026-04-10",
  timezone: "UTC",
  generated_at: "2026-04-10T18:00:00Z",
  captures: [
    {
      id: "doc-1",
      title: "Captured article",
      source_url: null,
      pipeline_status: "complete",
      content_type: "web",
      created_at: "2026-04-10T09:00:00Z",
    },
  ],
  stored_cards: [
    {
      card_id: 42,
      title: "Stored zettel",
      topic: "AI",
      status: "active",
      tags: ["agents"],
      created_at: "2026-04-10T10:00:00Z",
    },
  ],
  connections: [
    {
      link_id: 7,
      from_card_id: 42,
      from_title: "Stored zettel",
      to_card_id: 99,
      to_title: "Related zettel",
      type: "reference",
      created_at: "2026-04-10T11:00:00Z",
    },
  ],
  reviews: [
    {
      review_id: 3,
      card_id: 42,
      card_title: "Stored zettel",
      stage: 2,
      due_at: "2026-04-10T08:00:00Z",
      completed_at: null,
      status: "pending",
    },
  ],
  gaps: [
    {
      card_id: 100,
      title: "Need to flesh this out",
      created_at: "2026-04-10T07:30:00Z",
    },
  ],
  notes: [],
  stats: {
    total_captures: 1,
    total_cards_created: 1,
    total_connections: 1,
    total_reviews_due: 1,
    total_reviews_completed: 0,
    total_gaps: 1,
    total_events: 5,
    total_cards: 10,
    total_links: 12,
    total_notes_touched: 0,
  },
};

describe("today utils", () => {
  it("builds a reverse-chronological timeline", () => {
    const timeline = buildTodayTimeline(briefing);

    expect(timeline.map((item) => item.kind)).toEqual([
      "connection",
      "stored",
      "capture",
      "review",
      "gap",
    ]);
    expect(timeline[0]?.href).toBe("/knowledge/42");
    expect(timeline[2]?.href).toBe("/documents/doc-1");
  });

  it("maps calendar days by iso date", () => {
    const map = makeCalendarDayMap([
      {
        date: "2026-04-10",
        captures: 2,
        stored_cards: 1,
        connections: 0,
        reviews_due: 3,
        reviews_completed: 1,
        gaps: 0,
        total_events: 6,
      },
    ]);

    expect(map.get("2026-04-10")?.total_events).toBe(6);
  });

  it("counts events by kind for a briefing", () => {
    expect(TODAY_AUDIT_KINDS.map((kind) => getBriefingCountForKind(briefing, kind))).toEqual([
      1, 1, 1, 1, 1,
    ]);
  });

  it("counts and totals calendar activity for selected kinds", () => {
    const day = {
      date: "2026-04-10",
      captures: 2,
      stored_cards: 1,
      connections: 3,
      reviews_due: 4,
      reviews_completed: 2,
      gaps: 1,
      total_events: 11,
    };

    expect(getCalendarDayCountForKind(day, "connection")).toBe(3);
    expect(getCalendarDayTotalForKinds(day, ["capture", "review", "gap"])).toBe(7);
  });

  it("derives briefing lines from the action-oriented day state", () => {
    const lines = buildTodayBriefingLines(briefing);

    expect(lines[0]).toContain("captured 1 source");
    expect(lines[0]).toContain("created 1 card");
    expect(lines[1]).toContain("AI");
    expect(lines[1]).toContain("reviews");
  });

  it("builds insight cards with interpreted debt", () => {
    const debtBriefing: TodayBriefingResponse = {
      ...briefing,
      connections: [],
      stats: {
        ...briefing.stats,
        total_connections: 0,
        total_cards_created: 3,
        total_reviews_due: 4,
        total_reviews_completed: 1,
      },
    };

    expect(getTodayConnectionDebt(debtBriefing)).toBe(3);
    expect(getTodayReviewDebt(debtBriefing)).toBe(3);

    const insightCards = buildTodayInsightCards(debtBriefing);
    expect(insightCards.find((card) => card.id === "connection")?.tone).toBe("warning");
    expect(insightCards.find((card) => card.id === "review")?.metric).toBe("1 cleared of 4");
  });

  it("groups knowledge threads from cards and linked activity", () => {
    const multiThreadBriefing: TodayBriefingResponse = {
      ...briefing,
      stored_cards: [
        ...briefing.stored_cards,
        {
          card_id: 43,
          title: "Agent memory",
          topic: "AI",
          status: "active",
          tags: ["memory"],
          created_at: "2026-04-10T12:00:00Z",
        },
        {
          card_id: 44,
          title: "Stoic reading",
          topic: "Philosophy",
          status: "active",
          tags: [],
          created_at: "2026-04-10T12:30:00Z",
        },
      ],
    };

    const threads = buildTodayThreads(multiThreadBriefing);

    expect(threads[0]?.name).toBe("AI");
    expect(threads[0]?.cards).toBe(2);
    expect(threads.some((thread) => thread.name === "Knowledge gaps")).toBe(true);
  });

  it("prioritizes review and connection actions", () => {
    const actionBriefing: TodayBriefingResponse = {
      ...briefing,
      connections: [],
      stats: {
        ...briefing.stats,
        total_connections: 0,
        total_cards_created: 4,
        total_reviews_due: 3,
        total_reviews_completed: 0,
      },
    };

    const actions = buildTodayNextActions(actionBriefing);

    expect(actions[0]?.id).toBe("review-due");
    expect(actions[1]?.id).toBe("connect-new-knowledge");
  });
});
