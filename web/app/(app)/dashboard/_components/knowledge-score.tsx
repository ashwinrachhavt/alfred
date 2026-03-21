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
      <CardContent className="flex items-center gap-6 p-6">
        <div className="flex size-20 items-center justify-center rounded-full border-4 border-primary">
          <span className="text-3xl font-bold">{score}</span>
        </div>
        <div>
          <h2 className="text-lg font-semibold">Knowledge Score</h2>
          <div className="text-muted-foreground mt-1 flex gap-4 text-sm">
            <span>Retention: {retention}</span>
            <span>Coverage: {coverage}</span>
            <span>Connections: {connections}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
