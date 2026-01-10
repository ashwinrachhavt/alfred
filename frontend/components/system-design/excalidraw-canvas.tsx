"use client";

import dynamic from "next/dynamic";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

import type { ExcalidrawInitialDataState } from "@excalidraw/excalidraw/types";

import type { ExcalidrawData } from "@/lib/api/types/system-design";
import {
  SYSTEM_DESIGN_COMPONENT_DND_MIME,
  decodeSystemDesignComponentDragPayload,
} from "@/components/system-design/system-design-dnd";

type SerializeAsJSON = typeof import("@excalidraw/excalidraw").serializeAsJSON;
type ConvertToExcalidrawElements =
  typeof import("@excalidraw/excalidraw").convertToExcalidrawElements;
type Restore = typeof import("@excalidraw/excalidraw").restore;
type ExcalidrawAPI = import("@excalidraw/excalidraw/types").ExcalidrawImperativeAPI;
type ExcalidrawElementSkeleton = NonNullable<Parameters<ConvertToExcalidrawElements>[0]>[number];
type CaptureUpdateActionValue =
  (typeof import("@excalidraw/excalidraw").CaptureUpdateAction)[keyof typeof import("@excalidraw/excalidraw").CaptureUpdateAction];

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
  onSelectionChange?: (selectedElementIds: string[]) => void;
  onSelectionDetailsChange?: (selection: ExcalidrawCanvasSelection | null) => void;
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

export type ExcalidrawCanvasSelection = {
  elementId: string;
  name: string;
  category: string | null;
};

export type ExcalidrawCanvasHandle = {
  insertComponent: (component: { id: string; name: string; category?: string }) => void;
  updateComponentLabel: (elementId: string, name: string) => void;
  replaceWithMermaid: (definition: string) => Promise<void>;
  connectElements: (connection: {
    fromElementId: string;
    toElementId: string;
    label?: string;
  }) => void;
  getDiagram: () => ExcalidrawData | null;
  exportPng: (opts?: { maxWidthOrHeight?: number; background?: boolean }) => Promise<Blob | null>;
  exportSvg: (opts?: {
    embedScene?: boolean;
    width?: number;
    height?: number;
  }) => Promise<string | null>;
};

export const ExcalidrawCanvas = forwardRef<ExcalidrawCanvasHandle, ExcalidrawCanvasProps>(
  function ExcalidrawCanvasImpl(
    {
      initialDiagram,
      onDiagramChange,
      onSelectionChange,
      onSelectionDetailsChange,
      readOnly,
      framed = true,
      viewportScale = 1,
    }: ExcalidrawCanvasProps,
    ref,
  ) {
    const serializeRef = useRef<SerializeAsJSON | null>(null);
    const convertRef = useRef<ConvertToExcalidrawElements | null>(null);
    const restoreRef = useRef<Restore | null>(null);
    const captureUpdateRef = useRef<CaptureUpdateActionValue | null>(null);
    const apiRef = useRef<ExcalidrawAPI | null>(null);
    const metadataRef = useRef<Record<string, unknown> | undefined>(initialDiagram.metadata);
    const [helpersReady, setHelpersReady] = useState(false);
    const [normalizedInitialData, setNormalizedInitialData] =
      useState<ExcalidrawInitialDataState | null>(null);
    const viewportRef = useRef<HTMLDivElement | null>(null);
    const lastSelectionKeyRef = useRef<string | null>(null);

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
          captureUpdateRef.current = mod.CaptureUpdateAction.IMMEDIATELY;
          setHelpersReady(true);
        })
        .catch(() => {
          serializeRef.current = null;
          convertRef.current = null;
          restoreRef.current = null;
          captureUpdateRef.current = null;
          setHelpersReady(true);
        });
    }, []);

    useEffect(() => {
      if (!helpersReady) return;
      metadataRef.current = initialDiagram.metadata;
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

    const readSelection = useCallback((elements: unknown, appState: unknown) => {
      if (!Array.isArray(elements)) return null;
      if (!appState || typeof appState !== "object") return null;

      const appStateRecord = appState as Record<string, unknown>;
      const selectedElementIds = appStateRecord.selectedElementIds;
      if (!selectedElementIds || typeof selectedElementIds !== "object") return null;

      const selectedId = Object.entries(selectedElementIds as Record<string, unknown>).find(
        ([, value]) => value === true,
      )?.[0];
      if (!selectedId) return null;

      const sceneElements = elements.filter(
        (el): el is Record<string, unknown> => !!el && typeof el === "object",
      );
      const selectedElement = sceneElements.find((el) => el.id === selectedId);
      if (!selectedElement) return null;

      let containerId = selectedId;
      if (selectedElement.type === "text" && typeof selectedElement.containerId === "string") {
        containerId = selectedElement.containerId;
      }

      const containerElement = sceneElements.find((el) => el.id === containerId) ?? selectedElement;

      let labelText = "";
      let boundTextId: string | null = null;

      const boundElements = containerElement.boundElements;
      if (Array.isArray(boundElements)) {
        const binding = boundElements.find(
          (item): item is Record<string, unknown> =>
            !!item && typeof item === "object" && item.type === "text" && typeof item.id === "string",
        );
        if (binding) boundTextId = binding.id as string;
      }

      if (!boundTextId) {
        const containerText = sceneElements.find(
          (el) => el.type === "text" && el.containerId === containerId && typeof el.text === "string",
        );
        if (containerText && typeof containerText.id === "string") boundTextId = containerText.id;
      }

      if (boundTextId) {
        const textElement = sceneElements.find((el) => el.id === boundTextId);
        if (textElement && typeof textElement.text === "string") {
          labelText = textElement.text;
        }
      } else if (selectedElement.type === "text" && typeof selectedElement.text === "string") {
        labelText = selectedElement.text;
      }

      let category: string | null = null;
      const customData = containerElement.customData;
      if (customData && typeof customData === "object") {
        const record = customData as Record<string, unknown>;
        const alfred = record.alfred;
        if (alfred && typeof alfred === "object") {
          const alfredRecord = alfred as Record<string, unknown>;
          if (typeof alfredRecord.category === "string") category = alfredRecord.category;
        }
      }

      return { elementId: containerId, name: labelText, category } satisfies ExcalidrawCanvasSelection;
    }, []);

    const handleChange = useCallback(
      (elements: unknown, appState: unknown, files: unknown) => {
        if (onSelectionChange) {
          const selectedIds = new Set<string>();
          if (appState && typeof appState === "object") {
            const rawSelected = (appState as Record<string, unknown>).selectedElementIds;
            if (rawSelected && typeof rawSelected === "object") {
              for (const [id, selected] of Object.entries(rawSelected as Record<string, unknown>)) {
                if (selected) selectedIds.add(id);
              }
            }
          }

          const elementTypes = new Map<string, string>();
          if (Array.isArray(elements)) {
            for (const el of elements) {
              if (!el || typeof el !== "object") continue;
              const id = (el as Record<string, unknown>).id;
              const type = (el as Record<string, unknown>).type;
              if (typeof id === "string" && typeof type === "string") elementTypes.set(id, type);
            }
          }

          const connectable = Array.from(selectedIds).filter((id) => {
            const type = elementTypes.get(id);
            if (!type) return false;
            return type !== "text" && type !== "arrow" && type !== "line";
          });

          onSelectionChange(connectable);
        }

        if (!onDiagramChange) return;
        const serialize = serializeRef.current;
        if (!serialize) return;
        const next = toPersistedDiagram(serialize, elements, appState, files);
        if (metadataRef.current) next.metadata = metadataRef.current;
        onDiagramChange(next);
      },
      [onDiagramChange, onSelectionChange],
    );

    const handleSelectionDetails = useCallback(
      (elements: unknown, appState: unknown) => {
        if (!onSelectionDetailsChange) return;
        const selection = readSelection(elements, appState);
        const key = selection ? `${selection.elementId}:${selection.name}:${selection.category ?? ""}` : null;
        if (key !== lastSelectionKeyRef.current) {
          lastSelectionKeyRef.current = key;
          onSelectionDetailsChange(selection);
        }
      },
      [onSelectionDetailsChange, readSelection],
    );

    const getDiagram = useCallback((): ExcalidrawData | null => {
      const api = apiRef.current;
      const serialize = serializeRef.current;
      if (!api || !serialize) return null;

      const elements =
        "getSceneElementsIncludingDeleted" in api
          ? (api as unknown as { getSceneElementsIncludingDeleted: () => unknown }).getSceneElementsIncludingDeleted()
          : api.getSceneElements();
      const files =
        "getFiles" in api ? (api as unknown as { getFiles: () => unknown }).getFiles() : {};

      const next = toPersistedDiagram(serialize, elements, api.getAppState(), files);
      if (metadataRef.current) next.metadata = metadataRef.current;
      return next;
    }, []);

    const connectElements = useCallback(
      (connection: { fromElementId: string; toElementId: string; label?: string }) => {
        if (readOnly) return;
        const api = apiRef.current;
        const convertToExcalidrawElements = convertRef.current;
        if (!api || !convertToExcalidrawElements) return;

        const elements = api.getSceneElements();
        const from = elements.find((el) => el.id === connection.fromElementId);
        const to = elements.find((el) => el.id === connection.toElementId);
        if (!from || !to) return;

        const fromCenter = { x: from.x + from.width / 2, y: from.y + from.height / 2 };
        const toCenter = { x: to.x + to.width / 2, y: to.y + to.height / 2 };
        const dx = toCenter.x - fromCenter.x;
        const dy = toCenter.y - fromCenter.y;

        const skeleton: ExcalidrawElementSkeleton[] = [
          {
            type: "arrow",
            x: Math.min(fromCenter.x, toCenter.x),
            y: Math.min(fromCenter.y, toCenter.y),
            width: Math.max(10, Math.abs(dx)),
            height: Math.max(10, Math.abs(dy)),
            start: { id: connection.fromElementId },
            end: { id: connection.toElementId },
            ...(connection.label
              ? {
                  label: {
                    text: connection.label,
                  },
                }
              : {}),
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
          captureUpdate: captureUpdateRef.current ?? undefined,
        });
      },
      [readOnly],
    );

    const exportPng = useCallback(
      async (opts?: { maxWidthOrHeight?: number; background?: boolean }): Promise<Blob | null> => {
        const api = apiRef.current;
        if (!api) return null;

        const { exportToBlob } = await import("@excalidraw/excalidraw");
        return exportToBlob({
          elements: api.getSceneElements(),
          appState: {
            ...api.getAppState(),
            exportWithDarkMode: false,
            exportBackground: opts?.background ?? true,
          },
          files: api.getFiles(),
          mimeType: "image/png",
          maxWidthOrHeight: opts?.maxWidthOrHeight,
          exportPadding: 20,
        });
      },
      [],
    );

    const exportSvg = useCallback(
      async (opts?: {
        embedScene?: boolean;
        width?: number;
        height?: number;
      }): Promise<string | null> => {
        const api = apiRef.current;
        if (!api) return null;

        const { exportToSvg } = await import("@excalidraw/excalidraw");
        const svg = await exportToSvg({
          elements: api.getSceneElements(),
          appState: {
            ...api.getAppState(),
            exportWithDarkMode: false,
            exportEmbedScene: opts?.embedScene ?? true,
            ...(opts?.width ? { width: opts.width } : {}),
            ...(opts?.height ? { height: opts.height } : {}),
          },
          files: api.getFiles(),
        });
        return svg.outerHTML;
      },
      [],
    );

    const insertComponentAt = useCallback(
      (component: { id: string; name: string; category?: string }, center: { x: number; y: number }) => {
        if (readOnly) return;
        const api = apiRef.current;
        const convertToExcalidrawElements = convertRef.current;
        if (!api || !convertToExcalidrawElements) return;

        const width = 260;
        const height = 120;

        const category = component.category ?? "other";
        const style =
          category === "client"
            ? { strokeColor: "#1d4ed8", backgroundColor: "#dbeafe" }
            : category === "load_balancer"
              ? { strokeColor: "#a16207", backgroundColor: "#fef9c3" }
              : category === "api_gateway"
                ? { strokeColor: "#0f766e", backgroundColor: "#ccfbf1" }
                : category === "microservice"
                  ? { strokeColor: "#6d28d9", backgroundColor: "#ede9fe" }
                  : category === "cache"
                    ? { strokeColor: "#be185d", backgroundColor: "#fce7f3" }
                    : category === "database"
                      ? { strokeColor: "#b91c1c", backgroundColor: "#fee2e2" }
                      : category === "message_queue"
                        ? { strokeColor: "#c2410c", backgroundColor: "#ffedd5" }
                        : category === "cdn"
                          ? { strokeColor: "#1e40af", backgroundColor: "#e0f2fe" }
                          : { strokeColor: "#334155", backgroundColor: "#f1f5f9" };

        const skeleton: ExcalidrawElementSkeleton[] = [
          {
            type: "rectangle",
            x: center.x - width / 2,
            y: center.y - height / 2,
            width,
            height,
            ...style,
            label: {
              text: component.name,
              textAlign: "center",
              verticalAlign: "middle",
            },
            customData: {
              alfred: {
                kind: "system_design_component",
                componentId: component.id,
                category: component.category ?? null,
              },
            },
          } as unknown as ExcalidrawElementSkeleton,
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
          captureUpdate: captureUpdateRef.current ?? undefined,
        });
      },
      [readOnly],
    );

    const insertComponent = useCallback(
      (component: { id: string; name: string; category?: string }) => {
        if (readOnly) return;
        const api = apiRef.current;
        if (!api) return;

        const appState = api.getAppState();
        const zoom = appState.zoom?.value ?? 1;
        const viewportCenterX = appState.width / 2;
        const viewportCenterY = appState.height / 2;
        const centerX = viewportCenterX / zoom - appState.scrollX;
        const centerY = viewportCenterY / zoom - appState.scrollY;

        insertComponentAt(component, { x: centerX, y: centerY });
      },
      [insertComponentAt, readOnly],
    );

    const handleCanvasDragOver = useCallback(
      (event: React.DragEvent<HTMLDivElement>) => {
        if (readOnly) return;
        if (!event.dataTransfer.types.includes(SYSTEM_DESIGN_COMPONENT_DND_MIME)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
      },
      [readOnly],
    );

    const handleCanvasDrop = useCallback(
      (event: React.DragEvent<HTMLDivElement>) => {
        if (readOnly) return;
        const payload = decodeSystemDesignComponentDragPayload(
          event.dataTransfer.getData(SYSTEM_DESIGN_COMPONENT_DND_MIME),
        );
        if (!payload) return;

        event.preventDefault();
        event.stopPropagation();

        const api = apiRef.current;
        const viewport = viewportRef.current;
        if (!api || !viewport) return;

        const rect = viewport.getBoundingClientRect();
        const localX = (event.clientX - rect.left) / viewportScale;
        const localY = (event.clientY - rect.top) / viewportScale;

        const appState = api.getAppState();
        const zoom = appState.zoom?.value ?? 1;
        const centerX = localX / zoom - appState.scrollX;
        const centerY = localY / zoom - appState.scrollY;

        insertComponentAt(payload, { x: centerX, y: centerY });
      },
      [insertComponentAt, readOnly, viewportScale],
    );

    const handleCanvasChange = useCallback(
      (elements: unknown, appState: unknown, files: unknown) => {
        handleChange(elements, appState, files);
        handleSelectionDetails(elements, appState);
      },
      [handleChange, handleSelectionDetails],
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
          captureUpdate: captureUpdateRef.current ?? undefined,
        });

        api.scrollToContent(nextElements, { fitToContent: true, animate: true });
      },
      [readOnly],
    );

    const updateComponentLabel = useCallback(
      (elementId: string, name: string) => {
        if (readOnly) return;
        const api = apiRef.current;
        if (!api) return;

        const nextName = name.trim();
        if (!nextName) return;

        const elements = api.getSceneElementsIncludingDeleted() as unknown[];
        const sceneElements = elements.filter(
          (el): el is Record<string, unknown> => !!el && typeof el === "object",
        );

        const container = sceneElements.find((el) => el.id === elementId);
        if (!container) return;

        let textId: string | null = null;
        const boundElements = container.boundElements;
        if (Array.isArray(boundElements)) {
          const binding = boundElements.find(
            (item): item is Record<string, unknown> =>
              !!item && typeof item === "object" && item.type === "text" && typeof item.id === "string",
          );
          if (binding) textId = binding.id as string;
        }

        if (!textId) {
          const containerText = sceneElements.find(
            (el) => el.type === "text" && el.containerId === elementId && typeof el.id === "string",
          );
          if (containerText) textId = containerText.id as string;
        }

        if (!textId) return;

        const nextElements = elements.map((el) => {
          if (!el || typeof el !== "object") return el;
          const record = el as Record<string, unknown>;
          if (record.id !== textId) return el;

          return {
            ...record,
            text: nextName,
            originalText: nextName,
            rawText: nextName,
          };
        });

        const restore = restoreRef.current;
        if (restore) {
          try {
            const restored = restore(
              {
                elements: nextElements as unknown as ExcalidrawInitialDataState["elements"],
                appState: api.getAppState() as unknown as ExcalidrawInitialDataState["appState"],
                files: api.getFiles() as unknown as ExcalidrawInitialDataState["files"],
              },
              null,
              null,
              { refreshDimensions: true, repairBindings: true },
            );

            api.updateScene({
              elements: restored.elements as unknown as ExcalidrawInitialDataState["elements"],
            });
            return;
          } catch {
            // Fall back to raw update below.
          }
        }

        api.updateScene({
          elements: nextElements as unknown as ExcalidrawInitialDataState["elements"],
        });
      },
      [readOnly],
    );

    useImperativeHandle(
      ref,
      () => ({
        insertComponent,
        updateComponentLabel,
        replaceWithMermaid,
        connectElements,
        getDiagram,
        exportPng,
        exportSvg,
      }),
      [
        connectElements,
        exportPng,
        exportSvg,
        getDiagram,
        insertComponent,
        replaceWithMermaid,
        updateComponentLabel,
      ],
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
            ref={viewportRef}
            onDragOver={handleCanvasDragOver}
            onDrop={handleCanvasDrop}
          >
            {normalizedInitialData ? (
              <Excalidraw
                initialData={normalizedInitialData}
                onChange={handleCanvasChange}
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
