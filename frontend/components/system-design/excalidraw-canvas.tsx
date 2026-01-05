"use client";

import dynamic from "next/dynamic";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

import type { ExcalidrawInitialDataState } from "@excalidraw/excalidraw/types";

import type { ExcalidrawData } from "@/lib/api/types/system-design";

type SerializeAsJSON = typeof import("@excalidraw/excalidraw").serializeAsJSON;
type ConvertToExcalidrawElements =
  typeof import("@excalidraw/excalidraw").convertToExcalidrawElements;
type Restore = typeof import("@excalidraw/excalidraw").restore;
type ExcalidrawAPI = import("@excalidraw/excalidraw/types").ExcalidrawImperativeAPI;
type ExcalidrawElementSkeleton = NonNullable<Parameters<ConvertToExcalidrawElements>[0]>[number];

const Excalidraw = dynamic(async () => (await import("@excalidraw/excalidraw")).Excalidraw, {
  ssr: false,
  loading: () => (
    <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
      Loading canvas…
    </div>
  ),
});

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

  let parsed: Partial<{ elements: unknown; appState: unknown; files: unknown }> = {};
  try {
    parsed = JSON.parse(serialized) as Partial<{
      elements: unknown;
      appState: unknown;
      files: unknown;
    }>;
  } catch {
    parsed = {};
  }

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
   * When enabled, renders a bordered container around the Excalidraw editor.
   * Disable this when the parent already provides the panel chrome.
   */
  framed?: boolean;
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
  replaceWithMermaid: (definition: string) => Promise<void>;
};

export const ExcalidrawCanvas = forwardRef<ExcalidrawCanvasHandle, ExcalidrawCanvasProps>(
  function ExcalidrawCanvasImpl(
    {
      initialDiagram,
      onDiagramChange,
      readOnly,
      framed = true,
      viewportScale = 1,
    }: ExcalidrawCanvasProps,
    ref,
  ) {
    const serializeRef = useRef<SerializeAsJSON | null>(null);
    const convertRef = useRef<ConvertToExcalidrawElements | null>(null);
    const restoreRef = useRef<Restore | null>(null);
    const apiRef = useRef<ExcalidrawAPI | null>(null);
    const [helpersReady, setHelpersReady] = useState(false);
    const [normalizedInitialData, setNormalizedInitialData] =
      useState<ExcalidrawInitialDataState | null>(null);

    const normalizeFallback = useCallback((diagram: ExcalidrawData): ExcalidrawInitialDataState => {
      const rawElements = Array.isArray(diagram.elements) ? diagram.elements : [];
      const safeElements = rawElements.filter((el) => {
        if (!el || typeof el !== "object") return false;
        const type = (el as Record<string, unknown>).type;
        if (type !== "line" && type !== "arrow") return true;
        const points = (el as Record<string, unknown>).points;
        if (!Array.isArray(points) || points.length < 2) return false;
        return points.every(
          (p) =>
            Array.isArray(p) &&
            p.length === 2 &&
            typeof p[0] === "number" &&
            Number.isFinite(p[0]) &&
            typeof p[1] === "number" &&
            Number.isFinite(p[1]),
        );
      });

      return {
        elements: safeElements as unknown as ExcalidrawInitialDataState["elements"],
        appState: (diagram.appState ?? {}) as unknown as ExcalidrawInitialDataState["appState"],
        files: (diagram.files ?? {}) as unknown as ExcalidrawInitialDataState["files"],
      };
    }, []);

    useEffect(() => {
      // Important: Excalidraw touches `navigator` at module init, so avoid any
      // server evaluation by importing lazily on the client.
      import("@excalidraw/excalidraw")
        .then((mod) => {
          serializeRef.current = mod.serializeAsJSON;
          convertRef.current = mod.convertToExcalidrawElements;
          restoreRef.current = mod.restore;
          setHelpersReady(true);
        })
        .catch(() => {
          serializeRef.current = null;
          convertRef.current = null;
          restoreRef.current = null;
          setHelpersReady(true);
        });
    }, []);

    useEffect(() => {
      if (!helpersReady) return;
      const restore = restoreRef.current;
      if (!restore) {
        setNormalizedInitialData(normalizeFallback(initialDiagram));
        return;
      }

      try {
        const restored = restore(
          {
            elements: initialDiagram.elements as unknown as ExcalidrawInitialDataState["elements"],
            appState: initialDiagram.appState as unknown as ExcalidrawInitialDataState["appState"],
            files: initialDiagram.files as unknown as ExcalidrawInitialDataState["files"],
          },
          null,
          null,
          { refreshDimensions: true, repairBindings: true },
        );

        setNormalizedInitialData({
          elements: restored.elements as unknown as ExcalidrawInitialDataState["elements"],
          appState: restored.appState as unknown as ExcalidrawInitialDataState["appState"],
          files: restored.files as unknown as ExcalidrawInitialDataState["files"],
        });
      } catch {
        setNormalizedInitialData(normalizeFallback(initialDiagram));
      }
    }, [helpersReady, initialDiagram, normalizeFallback]);

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

    const replaceWithMermaid = useCallback(
      async (definition: string) => {
        if (readOnly) return;
        const api = apiRef.current;
        const convertToExcalidrawElements = convertRef.current;
        if (!api || !convertToExcalidrawElements) return;

        const { parseMermaidToExcalidraw } = await import("@excalidraw/mermaid-to-excalidraw");
        const parsed = await parseMermaidToExcalidraw(definition);
        const nextElements = convertToExcalidrawElements(parsed.elements, { regenerateIds: true });

        api.updateScene({
          elements: nextElements,
          appState: {
            ...api.getAppState(),
            selectedElementIds: {},
          },
        });

        api.scrollToContent(nextElements, { fitToContent: true, animate: true });
      },
      [readOnly],
    );

    useImperativeHandle(
      ref,
      () => ({
        insertComponent,
        replaceWithMermaid,
      }),
      [insertComponent, replaceWithMermaid],
    );

    return (
      <div
        className={
          framed
            ? "bg-background flex h-full w-full flex-col overflow-hidden rounded-2xl border-2 p-2"
            : "h-full w-full"
        }
      >
        <div
          className={
            framed
              ? `min-h-0 flex-1 overflow-hidden rounded-xl ${viewportScale === 1 ? "" : "p-2"}`
              : "h-full w-full"
          }
        >
          <div
            className="h-full w-full"
            style={{
              transform: viewportScale === 1 ? undefined : `scale(${viewportScale})`,
              transformOrigin: viewportScale === 1 ? undefined : "0 0",
              width: viewportScale === 1 ? undefined : `${100 / viewportScale}%`,
              height: viewportScale === 1 ? undefined : `${100 / viewportScale}%`,
            }}
          >
            {normalizedInitialData ? (
              <Excalidraw
                initialData={normalizedInitialData}
                onChange={handleChange}
                viewModeEnabled={readOnly}
                excalidrawAPI={(api) => {
                  apiRef.current = api;
                }}
              />
            ) : (
              <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
                Preparing canvas…
              </div>
            )}
          </div>
        </div>
      </div>
    );
  },
);

ExcalidrawCanvas.displayName = "ExcalidrawCanvas";
