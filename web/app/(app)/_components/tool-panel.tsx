"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useShellStore } from "@/lib/stores/shell-store";

export function ToolPanel() {
  const { toolPanel, closeToolPanel } = useShellStore();

  if (!toolPanel) return null;

  const labels: Record<string, string> = {
    notes: "Notes",
    document: "Document",
    connectors: "Connectors",
    quiz: "Review Session",
    writing: "Writing Assistant",
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-[60vw] max-w-3xl flex-col border-l bg-background shadow-xl">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h2 className="text-sm font-semibold">{labels[toolPanel.type] ?? toolPanel.type}</h2>
        <Button variant="ghost" size="icon" className="size-7" onClick={closeToolPanel}>
          <X className="size-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-muted-foreground text-sm">
          {toolPanel.type} panel — content will be migrated here.
        </p>
      </div>
    </div>
  );
}
