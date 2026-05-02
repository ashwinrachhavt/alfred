/**
 * Bloom's Taxonomy product-layer registry (T10 / D3).
 *
 * NOTE: These color mappings are product-layer decisions, NOT DESIGN.md tokens.
 * They map Bloom level → semantic Tailwind class. The Zettel Workspace
 * imports from here; do not re-introduce hard-coded hexes into components.
 */

export type BloomLevel = 1 | 2 | 3 | 4 | 5 | 6;

export const BLOOM_LABELS: Record<BloomLevel, string> = {
  1: "Remember",
  2: "Understand",
  3: "Apply",
  4: "Analyze",
  5: "Evaluate",
  6: "Create",
};

// D3: product-layer concern, NOT a DESIGN.md token. Values map to
// Tailwind-semantic classes the workspace uses (text-muted-foreground / warning / primary).
export const BLOOM_COLOR_CLASSES: Record<BloomLevel, string> = {
  1: "text-muted-foreground",
  2: "text-muted-foreground",
  3: "text-amber-700/80", // "warning-muted"
  4: "text-amber-700", // "warning"
  5: "text-primary", // #E8590C accent
  6: "text-primary",
};

/** Companion map for filled backgrounds (dots, pills). */
export const BLOOM_BG_CLASSES: Record<BloomLevel, string> = {
  1: "bg-muted-foreground/50",
  2: "bg-muted-foreground",
  3: "bg-amber-700/70",
  4: "bg-amber-700",
  5: "bg-primary",
  6: "bg-primary",
};

export const BLOOM_QUESTIONS: Record<BloomLevel, string[]> = {
  1: [
    "Add one concrete example.",
    "What's the opposite of this?",
    "Where did you first encounter this?",
  ],
  2: [
    "Teach this to a 10-year-old.",
    "What's an analogy that captures this?",
    "What does this explicitly NOT mean?",
  ],
  3: [
    "Apply this to a case you know.",
    "When would this fail?",
    "What would using this look like in practice?",
  ],
  4: [
    "What are the component parts?",
    "Compare this to a related idea.",
    "What causes what, in this system?",
  ],
  5: [
    "Steelman the opposing view.",
    "What's the weakest claim here?",
    "What evidence would change your mind?",
  ],
  6: [
    "What new question does this open up?",
    "Combine this with another idea to produce a new claim.",
    "What would a radically different framing look like?",
  ],
};

/**
 * Pick one question per level deterministically based on the user's content length.
 * The same card keeps getting the same prompt until the user types substantially more,
 * so the prompt doesn't thrash every keystroke.
 */
export function pickBloomQuestion(level: BloomLevel, wordCount: number): string {
  const pool = BLOOM_QUESTIONS[level];
  const idx = Math.floor(Math.max(0, wordCount) / 30) % pool.length;
  return pool[idx]!;
}
