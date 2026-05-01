import { describe, expect, it } from "vitest";

import { SEED_LINK_TYPES, defaultBidirectional } from "@/lib/constants/zettel-link-types";

describe("zettel link type seeds", () => {
  it("exposes the curated seed types in a stable order", () => {
    const types = SEED_LINK_TYPES.map((s) => s.type);
    expect(types).toEqual([
      "related",
      "supports",
      "contradicts",
      "extends",
      "example-of",
      "prerequisite",
    ]);
  });

  it("returns per-type bidirectional defaults", () => {
    expect(defaultBidirectional("related")).toBe(true);
    expect(defaultBidirectional("contradicts")).toBe(true);
    expect(defaultBidirectional("supports")).toBe(false);
    expect(defaultBidirectional("extends")).toBe(false);
    expect(defaultBidirectional("example-of")).toBe(false);
    expect(defaultBidirectional("prerequisite")).toBe(false);
  });

  it("falls back to bidirectional=false for unknown user-defined types", () => {
    // Unknown semantics shouldn't silently imply a reverse row. Users can
    // still opt in via the checkbox.
    expect(defaultBidirectional("my-custom-type")).toBe(false);
    expect(defaultBidirectional("refutes-premise")).toBe(false);
  });
});
