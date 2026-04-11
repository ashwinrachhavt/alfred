import { describe, expect, it } from "vitest";

import type { TodayBriefingResponse } from "@/lib/api/today";
import {
  TODAY_AUDIT_KINDS,
  buildTodayTimeline,
  getBriefingCountForKind,
  getCalendarDayCountForKind,
  getCalendarDayTotalForKinds,
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
      1,
      1,
      1,
      1,
      1,
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
});
