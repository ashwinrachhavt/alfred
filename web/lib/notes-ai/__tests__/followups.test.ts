import { describe, expect, it } from "vitest";

import {
  FOLLOWUPS,
  followupsByGroup,
  getFollowup,
  primaryFollowups,
  resolveFollowup,
  TONE_VARIANTS,
  TRANSLATE_VARIANTS,
  type FollowupContext,
  type FollowupId,
} from "../followups";

const SAMPLE_CTX: FollowupContext = {
  prevOutput: "The system uses a cache to reduce database load.",
  originalSelection: "The system uses a cache.",
  pageTitle: "Caching strategy",
};

describe("followups registry", () => {
  it("includes every primary, tone, and translate variant", () => {
    const ids = FOLLOWUPS.map((f) => f.id);

    expect(ids).toContain("try_again");
    expect(ids).toContain("continue_writing");
    expect(ids).toContain("make_longer");
    expect(ids).toContain("make_shorter");
    expect(ids).toContain("improve_writing");
    expect(ids).toContain("fix_grammar");
    expect(ids).toContain("summarize");
    expect(ids).toContain("explain");
    expect(ids).toContain("simplify");
    expect(ids).toContain("find_action_items");

    for (const variant of TONE_VARIANTS) {
      expect(ids).toContain(`change_tone:${variant}`);
    }
    for (const variant of TRANSLATE_VARIANTS) {
      expect(ids).toContain(`translate:${variant}`);
    }
  });

  it("registry ids are unique", () => {
    const ids = FOLLOWUPS.map((f) => f.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("primaryFollowups returns only group=primary entries", () => {
    const primaries = primaryFollowups();
    expect(primaries.length).toBeGreaterThan(0);
    for (const followup of primaries) {
      expect(followup.group).toBe("primary");
    }
  });

  it("followupsByGroup partitions every followup into exactly one group", () => {
    const groups = followupsByGroup();
    const totalGrouped =
      groups.primary.length +
      groups.tone.length +
      groups.translate.length +
      groups.transform.length;
    expect(totalGrouped).toBe(FOLLOWUPS.length);
  });

  it("every followup resolves to a non-empty instruction", () => {
    for (const followup of FOLLOWUPS) {
      const instruction = resolveFollowup(followup.id, SAMPLE_CTX);
      expect(instruction.trim().length).toBeGreaterThan(0);
    }
  });

  it("rewrite-mode templates embed the prior output", () => {
    const rewrites = FOLLOWUPS.filter((f) => f.mode === "rewrite" && f.id !== "try_again");
    for (const followup of rewrites) {
      const instruction = resolveFollowup(followup.id, SAMPLE_CTX);
      expect(instruction).toContain(SAMPLE_CTX.prevOutput);
    }
  });

  it("tone variants produce distinct instructions", () => {
    const seen = new Set<string>();
    for (const variant of TONE_VARIANTS) {
      const id = `change_tone:${variant}` as FollowupId;
      const instruction = resolveFollowup(id, SAMPLE_CTX);
      expect(instruction.toLowerCase()).toContain(variant);
      seen.add(instruction);
    }
    expect(seen.size).toBe(TONE_VARIANTS.length);
  });

  it("translate variants produce distinct instructions", () => {
    const seen = new Set<string>();
    for (const variant of TRANSLATE_VARIANTS) {
      const id = `translate:${variant}` as FollowupId;
      const instruction = resolveFollowup(id, SAMPLE_CTX);
      seen.add(instruction);
    }
    expect(seen.size).toBe(TRANSLATE_VARIANTS.length);
  });

  it("try_again does not embed the prior output (it asks for a fresh attempt)", () => {
    const instruction = resolveFollowup("try_again", SAMPLE_CTX);
    expect(instruction).not.toContain(SAMPLE_CTX.prevOutput);
  });

  it("try_again falls back gracefully when there is no original selection", () => {
    const instruction = resolveFollowup("try_again", {
      ...SAMPLE_CTX,
      originalSelection: null,
    });
    expect(instruction.trim().length).toBeGreaterThan(0);
  });

  it("getFollowup returns undefined for unknown ids", () => {
    expect(getFollowup("nonsense" as FollowupId)).toBeUndefined();
  });

  it("resolveFollowup throws for unknown ids", () => {
    expect(() => resolveFollowup("nonsense" as FollowupId, SAMPLE_CTX)).toThrow();
  });
});
