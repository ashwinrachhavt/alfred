"use client";

import type { ArtifactCard } from "@/lib/stores/agent-store";

const ACTION_ICONS: Record<string, string> = {
  created: "📄",
  found: "🔍",
  updated: "✏️",
};

export function ArtifactCardComponent({
  artifact,
  onClick,
}: {
  artifact: ArtifactCard;
  onClick: () => void;
}) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="flex items-start gap-3">
        {/* Page preview icon */}
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-secondary text-lg">
          {ACTION_ICONS[artifact.action] || "📄"}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-xs text-muted-foreground mb-0.5">
            {artifact.action === "created" ? "Created" : artifact.action === "updated" ? "Updated" : "Found"}{" "}
            &ldquo;{artifact.title}&rdquo; page
          </p>
          <button
            onClick={onClick}
            className="text-sm font-medium text-primary hover:underline"
          >
            Open page
          </button>
        </div>

        {/* Mini page thumbnail */}
        {artifact.summary && (
          <div className="hidden sm:block w-20 h-14 shrink-0 rounded border bg-background p-1.5 overflow-hidden">
            <div className="text-[6px] leading-tight text-muted-foreground line-clamp-5">
              <div className="font-medium text-[7px] text-foreground mb-0.5">{artifact.title}</div>
              {artifact.summary}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
