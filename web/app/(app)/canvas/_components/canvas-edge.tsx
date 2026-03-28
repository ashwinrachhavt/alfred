"use client";

import { memo } from "react";
import { BaseEdge, getSmoothStepPath, type EdgeProps } from "@xyflow/react";

function CanvasEdge(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props;
  const isAiSuggested = (data as { aiSuggested?: boolean })?.aiSuggested ?? false;

  const [edgePath] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition });

  return (
    <BaseEdge
      path={edgePath}
      style={{
        stroke: isAiSuggested ? "var(--color-muted-foreground)" : "var(--color-primary)",
        strokeWidth: isAiSuggested ? 1 : 2,
        strokeDasharray: isAiSuggested ? "5 5" : "none",
        opacity: isAiSuggested ? 0.5 : 1,
      }}
    />
  );
}

export default memo(CanvasEdge);
