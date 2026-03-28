"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { FileText } from "lucide-react";

type DocumentNodeData = { label: string; summary?: string };

function DocumentNode({ data }: NodeProps) {
  const d = data as DocumentNodeData;
  return (
    <div className="rounded-lg border bg-background p-3 shadow-sm w-48">
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="flex items-start gap-2">
        <FileText className="size-4 text-blue-500 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{d.label}</p>
          {d.summary && <p className="text-muted-foreground mt-1 line-clamp-2 text-[10px]">{d.summary}</p>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

export default memo(DocumentNode);
