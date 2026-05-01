export type SeedLinkType = {
  type: string;
  label: string;
  bidirectional: boolean;
};

export const SEED_LINK_TYPES: readonly SeedLinkType[] = [
  { type: "related", label: "Related", bidirectional: true },
  { type: "supports", label: "Supports", bidirectional: false },
  { type: "contradicts", label: "Contradicts", bidirectional: true },
  { type: "extends", label: "Extends", bidirectional: false },
  { type: "example-of", label: "Example of", bidirectional: false },
  { type: "prerequisite", label: "Prerequisite", bidirectional: false },
] as const;

// For unknown (user-defined) types, default to unidirectional. A bidirectional
// default would silently invent reverse semantics the user never endorsed —
// e.g., a custom "refutes-premise" type would auto-create a reverse row whose
// meaning is not clear. Known curated types opt in to bidirectional explicitly.
export function defaultBidirectional(type: string): boolean {
  const seed = SEED_LINK_TYPES.find((s) => s.type === type);
  return seed?.bidirectional ?? false;
}
