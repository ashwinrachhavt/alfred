"use client";

import { Card, CardContent } from "@/components/ui/card";

type Props = {
  retention: number;
  coverage: number;
  connections: number;
};

export function KnowledgeScore({ retention, coverage, connections }: Props) {
  const score = Math.round(0.4 * retention + 0.3 * coverage + 0.3 * connections);

  return (
    <Card>
      <CardContent className="flex items-center gap-8 p-6">
        <div className="flex size-24 items-center justify-center rounded-full border-4 border-primary">
          <span className="font-data text-4xl font-semibold tabular-nums text-primary">{score}</span>
        </div>
        <div>
          <h2 className="font-serif text-xl">Knowledge Score</h2>
          <div className="mt-2 flex gap-6">
            <div>
              <div className="font-data text-lg font-semibold tabular-nums">{retention}</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">Retention</div>
            </div>
            <div>
              <div className="font-data text-lg font-semibold tabular-nums">{coverage}</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">Coverage</div>
            </div>
            <div>
              <div className="font-data text-lg font-semibold tabular-nums">{connections}</div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">Connections</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
