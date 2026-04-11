import { describe, expect, it } from "vitest";

import {
  clampTiptapPosition,
  normalizeTiptapRange,
  remapTiptapRange,
} from "@/lib/utils/tiptap-ranges";

describe("tiptap range utils", () => {
  it("clamps positions into the current document bounds", () => {
    expect(clampTiptapPosition(-8, 24)).toBe(0);
    expect(clampTiptapPosition(12, 24)).toBe(12);
    expect(clampTiptapPosition(80, 24)).toBe(24);
  });

  it("normalizes reversed ranges after clamping", () => {
    expect(normalizeTiptapRange({ from: 22, to: 5 }, 18)).toEqual({ from: 5, to: 18 });
  });

  it("remaps insertion ranges across document changes", () => {
    const insertionAt = 12;
    const insertedLength = 5;
    const mapping = {
      map(position: number, assoc = 1) {
        if (position < insertionAt) return position;
        if (position > insertionAt) return position + insertedLength;
        return assoc > 0 ? position + insertedLength : position;
      },
    };

    expect(remapTiptapRange({ from: 12, to: 12 }, mapping, 40)).toEqual({
      from: 12,
      to: 17,
    });
  });

  it("remaps deleted ranges back into valid bounds", () => {
    const deletedFrom = 8;
    const deletedTo = 16;
    const deletedLength = deletedTo - deletedFrom;
    const mapping = {
      map(position: number) {
        if (position <= deletedFrom) return position;
        if (position <= deletedTo) return deletedFrom;
        return position - deletedLength;
      },
    };

    expect(remapTiptapRange({ from: 10, to: 18 }, mapping, 24)).toEqual({
      from: 8,
      to: 10,
    });
  });
});
