"use client";

import { Sparkles, ZoomIn, ZoomOut } from "lucide-react";
import { useReactFlow } from "@xyflow/react";

import { Button } from "@/components/ui/button";
import { useCanvasStore } from "@/lib/stores/canvas-store";

export function CanvasToolbar() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const { aiSuggestEnabled, toggleAiSuggest } = useCanvasStore();

  return (
    <div className="absolute left-4 top-4 z-10 flex items-center gap-1 rounded-lg border bg-background/90 p-1 shadow-sm backdrop-blur">
      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomIn()}>
        <ZoomIn className="size-4" />
      </Button>
      <Button variant="ghost" size="icon" className="size-7" onClick={() => zoomOut()}>
        <ZoomOut className="size-4" />
      </Button>
      <Button variant="ghost" size="sm" className="text-xs" onClick={() => fitView()}>
        Fit
      </Button>
      <div className="mx-1 h-4 w-px bg-border" />
      <Button
        variant={aiSuggestEnabled ? "secondary" : "ghost"}
        size="sm"
        className="gap-1 text-xs"
        onClick={toggleAiSuggest}
      >
        <Sparkles className="size-3" />
        AI Suggest
      </Button>
    </div>
  );
}
