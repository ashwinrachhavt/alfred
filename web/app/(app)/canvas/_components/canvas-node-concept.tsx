"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Lightbulb } from "lucide-react";

type ConceptNodeData = { label: string; description?: string };

function ConceptNode({ data }: NodeProps) {
  const d = data as ConceptNodeData;
  return (
    <div className="rounded-lg border border-purple-500/30 bg-purple-50 dark:bg-purple-950/20 p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-purple-500" />
      <div className="flex items-start gap-2">
        <Lightbulb className="size-4 text-purple-500 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{d.label}</p>
          {d.description && <p className="text-muted-foreground mt-1 line-clamp-2 text-[10px]">{d.description}</p>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-purple-500" />
    </div>
  );
}

export default memo(ConceptNode);
