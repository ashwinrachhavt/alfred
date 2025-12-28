"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo } from "react";

import { serializeAsJSON } from "@excalidraw/excalidraw";
import type { ExcalidrawInitialDataState } from "@excalidraw/excalidraw/types";

import type { ExcalidrawData } from "@/lib/api/types/system-design";

const Excalidraw = dynamic(
  async () => (await import("@excalidraw/excalidraw")).Excalidraw,
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        Loading canvas…
      </div>
    ),
  },
);

function toPersistedDiagram(
  elements: unknown,
  appState: unknown,
  files: unknown,
): ExcalidrawData {
  const serialized = serializeAsJSON(
    elements as unknown as Parameters<typeof serializeAsJSON>[0],
    appState as unknown as Parameters<typeof serializeAsJSON>[1],
    files as unknown as Parameters<typeof serializeAsJSON>[2],
    "database",
  );

  const parsed = JSON.parse(serialized) as Partial<{
    elements: unknown;
    appState: unknown;
    files: unknown;
  }>;

  return {
    elements: (parsed.elements ?? []) as Record<string, unknown>[],
    appState: (parsed.appState ?? {}) as Record<string, unknown>,
    files: (parsed.files ?? {}) as Record<string, unknown>,
  };
}

export type ExcalidrawCanvasProps = {
  initialDiagram: ExcalidrawData;
  onDiagramChange?: (diagram: ExcalidrawData) => void;
  readOnly?: boolean;
};

export function ExcalidrawCanvas({
  initialDiagram,
  onDiagramChange,
  readOnly,
}: ExcalidrawCanvasProps) {
  const initialData = useMemo<ExcalidrawInitialDataState>(
    () => ({
      elements: initialDiagram.elements as unknown as ExcalidrawInitialDataState["elements"],
      appState: initialDiagram.appState as unknown as ExcalidrawInitialDataState["appState"],
      files: initialDiagram.files as unknown as ExcalidrawInitialDataState["files"],
    }),
    [initialDiagram],
  );

  const handleChange = useCallback(
    (elements: unknown, appState: unknown, files: unknown) => {
      if (!onDiagramChange) return;
      onDiagramChange(toPersistedDiagram(elements, appState, files));
    },
    [onDiagramChange],
  );

  return (
    <div className="h-full w-full overflow-hidden rounded-xl border bg-background">
      <Excalidraw initialData={initialData} onChange={handleChange} viewModeEnabled={readOnly} />
    </div>
  );
}
