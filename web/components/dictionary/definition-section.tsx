"use client";

import type { DefinitionGroup } from "@/lib/api/dictionary";

export function DefinitionSection({ groups }: { groups: DefinitionGroup[] }) {
  if (groups.length === 0) return null;

  return (
    <div className="space-y-6">
      {groups.map((group, gi) => (
        <div key={gi}>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {group.part_of_speech}
          </span>
          <ol className="mt-2 list-decimal space-y-3 pl-5">
            {group.senses.map((sense, si) => (
              <li key={si} className="text-foreground leading-relaxed">
                <span>{sense.definition}</span>
                {sense.examples.length > 0 && (
                  <div className="mt-1 space-y-1">
                    {sense.examples.map((ex, ei) => (
                      <p key={ei} className="text-sm italic text-muted-foreground">
                        &ldquo;{ex}&rdquo;
                      </p>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
