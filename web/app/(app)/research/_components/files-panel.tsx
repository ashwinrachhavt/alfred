"use client";

import { useState } from "react";
import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useResearchFiles } from "@/lib/stores/research-store";

export function FilesPanel() {
  const files = useResearchFiles();
  const paths = Object.keys(files).sort();
  const [active, setActive] = useState<string | null>(null);

  const selected = active && files[active] ? files[active] : null;

  if (paths.length === 0) {
    return (
      <div className="text-muted-foreground px-4 py-6 text-xs leading-relaxed">
        No files written yet. The agent typically writes `/final_report.md` once it has
        synthesized its findings.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <ul className="border-border/60 max-h-40 shrink-0 overflow-y-auto border-b">
        {paths.map((path) => (
          <li key={path}>
            <button
              type="button"
              onClick={() => setActive(path)}
              className={cn(
                "flex w-full items-center gap-2 px-4 py-2 text-left text-xs transition-colors",
                active === path ? "bg-primary/5" : "hover:bg-muted/50",
              )}
            >
              <FileText className="text-muted-foreground h-3 w-3" />
              <span className="truncate font-mono">{path}</span>
              <Badge variant="outline" className="ml-auto text-[10px]">
                {files[path].bytes} B
              </Badge>
            </button>
          </li>
        ))}
      </ul>

      <div className="flex-1 overflow-auto px-4 py-3">
        {selected?.content ? (
          <pre className="text-xs leading-relaxed whitespace-pre-wrap">{selected.content}</pre>
        ) : (
          <p className="text-muted-foreground text-xs">
            {selected
              ? "File streamed but content not yet available. Final contents arrive on `done`."
              : "Select a file to view its contents."}
          </p>
        )}
      </div>
    </div>
  );
}
