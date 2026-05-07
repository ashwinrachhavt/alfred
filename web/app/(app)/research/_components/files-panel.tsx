"use client";

import { useState } from "react";
import { FileText } from "lucide-react";

import { MessageResponse } from "@/components/ai-elements/message";
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
      <div className="px-5 py-6">
        <div className="rounded-md border border-dashed border-border/70 bg-muted/10 px-4 py-5">
          <p className="text-sm text-foreground">No files yet</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Reports and artifacts will stream into this panel.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <ul className="max-h-44 shrink-0 overflow-y-auto border-b border-border/60">
        {paths.map((path) => (
          <li key={path}>
            <button
              type="button"
              onClick={() => setActive(path)}
              className={cn(
                "flex w-full items-center gap-2 px-5 py-2.5 text-left text-xs transition-colors",
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

      <div className="flex-1 overflow-auto px-5 py-4">
        {selected?.content ? (
          selected.path.toLowerCase().endsWith(".md") ? (
            <MessageResponse className="text-xs leading-5 text-foreground/90">
              {selected.content}
            </MessageResponse>
          ) : (
            <pre className="text-xs leading-5 whitespace-pre-wrap">{selected.content}</pre>
          )
        ) : (
          <p className="text-xs text-muted-foreground">
            {selected
              ? "File streamed but content not yet available. Final contents arrive on `done`."
              : "Select a file to view its contents."}
          </p>
        )}
      </div>
    </div>
  );
}
