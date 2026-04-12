import { describe, expect, it } from "vitest";

import { normalizePastedEditorText } from "@/lib/utils/editor-paste";

describe("normalizePastedEditorText", () => {
  it("normalizes wrapped multiline paste and removes whitespace-only lines", () => {
    const input = "  \n  First line   \n    \n  Second line  \n\n";

    expect(normalizePastedEditorText(input)).toBe("First line\n\nSecond line");
  });

  it("dedents shared indentation while preserving relative nesting", () => {
    const input = "    - parent\n      - child\n    tail";

    expect(normalizePastedEditorText(input)).toBe("- parent\n  - child\ntail");
  });

  it("replaces invisible clipboard whitespace characters", () => {
    const input = "Alpha\u00a0Beta\u200b";

    expect(normalizePastedEditorText(input)).toBe("Alpha Beta");
  });

  it("keeps single-line spacing intact", () => {
    const input = " keep this spacing ";

    expect(normalizePastedEditorText(input)).toBe(" keep this spacing ");
  });
});
