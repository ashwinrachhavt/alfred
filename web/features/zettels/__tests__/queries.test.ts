import { describe, expect, it } from "vitest";

import { mapApiToZettel } from "@/features/zettels/queries";
import type { ApiZettelCard } from "@/lib/api/zettels";

const baseCard: ApiZettelCard = {
  id: 42,
  title: "Streaming Architecture",
  content: null,
  summary: null,
  tags: ["architecture"],
  topic: "systems",
  source_url: null,
  document_id: null,
  importance: 5,
  confidence: 0.7,
  status: "active",
  created_at: "2026-04-10T12:00:00Z",
  updated_at: "2026-04-10T12:00:00Z",
};

describe("mapApiToZettel", () => {
  it("keeps markdown bodies out of the summary field while deriving a readable preview", () => {
    const card = {
      ...baseCard,
      content:
        "# PR #706 and #707\n\n## Purpose\nA hub for **learning** from [[streaming architecture]] reviews.",
    };

    const zettel = mapApiToZettel(card, []);

    expect(zettel.summary).toBe("");
    expect(zettel.content).toBe(card.content);
    expect(zettel.preview).toBe(
      "PR #706 and #707 Purpose A hub for learning from streaming architecture reviews.",
    );
  });

  it("uses the dedicated summary for previews when one exists", () => {
    const card = {
      ...baseCard,
      content: "# Full body\n\nThis should stay in content.",
      summary: "## Review hub\n\nA concise **summary** for the card.",
    };

    const zettel = mapApiToZettel(card, []);

    expect(zettel.summary).toBe(card.summary);
    expect(zettel.preview).toBe("Review hub A concise summary for the card.");
  });
});
