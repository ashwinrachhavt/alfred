"use client";

import dynamic from "next/dynamic";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef } from "react";

import type { ExcalidrawInitialDataState } from "@excalidraw/excalidraw/types";

import type { ExcalidrawData } from "@/lib/api/types/system-design";

type SerializeAsJSON = typeof import("@excalidraw/excalidraw").serializeAsJSON;
type ConvertToExcalidrawElements = typeof import("@excalidraw/excalidraw").convertToExcalidrawElements;
type ExcalidrawAPI = import("@excalidraw/excalidraw/types").ExcalidrawImperativeAPI;
type ExcalidrawElementSkeleton = NonNullable<Parameters<ConvertToExcalidrawElements>[0]>[number];

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
  serialize: SerializeAsJSON,
  elements: unknown,
  appState: unknown,
  files: unknown,
): ExcalidrawData {
  const serialized = serialize(
    elements as unknown as Parameters<typeof serialize>[0],
    appState as unknown as Parameters<typeof serialize>[1],
    files as unknown as Parameters<typeof serialize>[2],
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
  /**
   * Additional viewport scale applied on top of Excalidraw's own zoom.
   * Useful for "extra zoom out" without patching Excalidraw's MIN_ZOOM.
   *
   * `1` means no extra scaling. Values like `0.5` or `0.25` zoom the whole
   * editor out while keeping pointer coordinates aligned.
   */
  viewportScale?: number;
};

export type ExcalidrawCanvasHandle = {
  insertComponent: (component: { id: string; name: string; category?: string }) => void;
};

export const ExcalidrawCanvas = forwardRef<ExcalidrawCanvasHandle, ExcalidrawCanvasProps>(
  function ExcalidrawCanvasImpl(
    { initialDiagram, onDiagramChange, readOnly, viewportScale = 1 }: ExcalidrawCanvasProps,
    ref,
  ) {
    const serializeRef = useRef<SerializeAsJSON | null>(null);
    const convertRef = useRef<ConvertToExcalidrawElements | null>(null);
    const apiRef = useRef<ExcalidrawAPI | null>(null);

    useEffect(() => {
      // Important: Excalidraw touches `navigator` at module init, so avoid any
      // server evaluation by importing lazily on the client.
      import("@excalidraw/excalidraw")
        .then((mod) => {
          serializeRef.current = mod.serializeAsJSON;
          convertRef.current = mod.convertToExcalidrawElements;
        })
        .catch(() => {
          serializeRef.current = null;
          convertRef.current = null;
        });
    }, []);

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
        const serialize = serializeRef.current;
        if (!serialize) return;
        onDiagramChange(toPersistedDiagram(serialize, elements, appState, files));
      },
      [onDiagramChange],
    );

    const insertComponent = useCallback(
      (component: { id: string; name: string; category?: string }) => {
        if (readOnly) return;
        const api = apiRef.current;
        const convertToExcalidrawElements = convertRef.current;
        if (!api || !convertToExcalidrawElements) return;

        const appState = api.getAppState();
        const zoom = appState.zoom?.value ?? 1;
        const viewportCenterX = appState.width / 2;
        const viewportCenterY = appState.height / 2;
        const centerX = viewportCenterX / zoom - appState.scrollX;
        const centerY = viewportCenterY / zoom - appState.scrollY;

        const width = 260;
        const height = 120;

      const skeleton: ExcalidrawElementSkeleton[] = [
        {
          type: "rectangle",
          x: centerX - width / 2,
            y: centerY - height / 2,
            width,
            height,
            label: {
              text: component.name,
              textAlign: "center",
              verticalAlign: "middle",
            },
          },
        ];

      const newElements = convertToExcalidrawElements(skeleton, { regenerateIds: true });
      const existing = api.getSceneElementsIncludingDeleted();
      const nextElements = [...existing, ...newElements];
      const selectedElementIds = Object.fromEntries(
        newElements.map((el) => [el.id, true as const]),
      ) as Record<string, true>;

      api.updateScene({
        elements: nextElements,
        appState: {
            selectedElementIds,
          },
        });
      },
      [readOnly],
    );

    useImperativeHandle(
      ref,
      () => ({
        insertComponent,
      }),
      [insertComponent],
    );

    return (
      <div className="flex h-full w-full flex-col rounded-2xl border-2 bg-background p-2">
        <div className="min-h-0 flex-1 overflow-hidden rounded-xl">
          <div
            className="h-full w-full"
            style={{
              transform: viewportScale === 1 ? undefined : `scale(${viewportScale})`,
              transformOrigin: viewportScale === 1 ? undefined : "0 0",
              width: viewportScale === 1 ? undefined : `${100 / viewportScale}%`,
              height: viewportScale === 1 ? undefined : `${100 / viewportScale}%`,
            }}
          >
            <Excalidraw
              initialData={initialData}
              onChange={handleChange}
              viewModeEnabled={readOnly}
              excalidrawAPI={(api) => {
                apiRef.current = api;
              }}
            />
          </div>
        </div>
      </div>
    );
  },
);

ExcalidrawCanvas.displayName = "ExcalidrawCanvas";
