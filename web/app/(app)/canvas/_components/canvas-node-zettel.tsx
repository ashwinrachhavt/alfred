"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { StickyNote } from "lucide-react";

type ZettelNodeData = { label: string; tags?: string[] };

function ZettelNode({ data }: NodeProps) {
  const d = data as ZettelNodeData;
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-50 dark:bg-amber-950/20 p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-amber-500" />
      <div className="flex items-start gap-2">
        <StickyNote className="size-4 text-amber-500 shrink-0 mt-0.5" />
        <p className="truncate text-xs font-medium">{d.label}</p>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-amber-500" />
    </div>
  );
}

export default memo(ZettelNode);
