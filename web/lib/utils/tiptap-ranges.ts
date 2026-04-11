export type TiptapRange = {
  from: number;
  to: number;
};

type PositionMapping = {
  map: (position: number, assoc?: number) => number;
};

export function clampTiptapPosition(position: number, docSize: number): number {
  const normalizedDocSize = Number.isFinite(docSize) ? Math.max(0, Math.floor(docSize)) : 0;
  const normalizedPosition = Number.isFinite(position) ? Math.floor(position) : 0;
  return Math.max(0, Math.min(normalizedPosition, normalizedDocSize));
}

export function normalizeTiptapRange(range: TiptapRange, docSize: number): TiptapRange {
  const from = clampTiptapPosition(range.from, docSize);
  const to = clampTiptapPosition(range.to, docSize);
  return from <= to ? { from, to } : { from: to, to: from };
}

export function remapTiptapRange(
  range: TiptapRange,
  mapping: PositionMapping,
  docSize: number,
): TiptapRange {
  return normalizeTiptapRange(
    {
      from: mapping.map(range.from, -1),
      to: mapping.map(range.to, 1),
    },
    docSize,
  );
}
