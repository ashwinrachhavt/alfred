"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Whiteboard } from "@/features/canvas/queries";
import { apiRoutes } from "@/lib/api/routes";

type ExcalidrawAPI = import("@excalidraw/excalidraw/types").ExcalidrawImperativeAPI;

const Excalidraw = dynamic(async () => (await import("@excalidraw/excalidraw")).Excalidraw, {
  ssr: false,
  loading: () => (
    <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
      Loading whiteboard...
    </div>
  ),
});

const ExcalidrawTTDDialog = dynamic(
  async () => (await import("@excalidraw/excalidraw")).TTDDialog,
  { ssr: false },
);

const ExcalidrawTTDDialogTrigger = dynamic(
  async () => (await import("@excalidraw/excalidraw")).TTDDialogTrigger,
  { ssr: false },
);

type ExcalidrawWhiteboardProps = {
  canvas: Whiteboard | null;
  onSaveScene: (scene: { elements: unknown[]; appState: Record<string, unknown> }) => void;
  onTitleChange: (title: string) => void;
  getCanvasContext?: () => string;
  onApiReady?: (api: ExcalidrawAPI) => void;
};

type NativeMermaidResponse = {
  mermaid?: string;
  error?: string;
  rateLimit?: number | null;
  rateLimitRemaining?: number | null;
};

function extractScene(canvas: Whiteboard | null): {
  elements: unknown[];
  appState: Record<string, unknown>;
} | null {
  const revision = canvas?.latest_revision;
  if (!revision?.scene_json) return null;
  const scene = revision.scene_json as Record<string, unknown>;
  return {
    elements: (scene.elements as unknown[]) ?? [],
    appState: (scene.appState as Record<string, unknown>) ?? {},
  };
}

export function ExcalidrawWhiteboard({
  canvas,
  onSaveScene,
  onTitleChange,
  getCanvasContext,
  onApiReady,
}: ExcalidrawWhiteboardProps) {
  const apiRef = useRef<ExcalidrawAPI | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const derivedTitle = useMemo(() => canvas?.title ?? "", [canvas?.title]);
  const canvasId = canvas?.id ?? null;

  const [titleDraft, setTitleDraft] = useState<{
    canvasId: number | null;
    value: string | null;
  }>({
    canvasId,
    value: null,
  });
  const titleOverride = titleDraft.canvasId === canvasId ? titleDraft.value : null;

  const title = titleOverride ?? derivedTitle;

  const handleChange = useCallback(
    (elements: readonly unknown[], appState: Record<string, unknown>) => {
      if (!canvas) return;
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = setTimeout(() => {
        const filteredElements = (elements as Array<Record<string, unknown>>).filter(
          (element) => !element.isDeleted,
        );
        onSaveScene({
          elements: filteredElements,
          appState: {
            viewBackgroundColor: appState.viewBackgroundColor,
            gridSize: appState.gridSize,
          },
        });
      }, 2000);
    },
    [canvas, onSaveScene],
  );

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState !== "hidden" || !saveTimeoutRef.current) {
        return;
      }

      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;

      const api = apiRef.current;
      if (!api || !canvas) return;

      const elements = (api.getSceneElements() as Array<Record<string, unknown>>).filter(
        (element) => !element.isDeleted,
      );
      const appState = api.getAppState();
      onSaveScene({
        elements,
        appState: {
          viewBackgroundColor: appState.viewBackgroundColor,
          gridSize: appState.gridSize,
        },
      });
    };

    window.addEventListener("visibilitychange", onVisibilityChange);
    return () => window.removeEventListener("visibilitychange", onVisibilityChange);
  }, [canvas, onSaveScene]);

  const handleNativeTextToDiagram = useCallback(
    async (prompt: string) => {
      try {
        const response = await fetch(apiRoutes.canvas.generateMermaid, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt,
            canvasTitle: derivedTitle,
            canvasContext: getCanvasContext?.() ?? "",
          }),
        });

        const payload = (await response.json().catch(() => null)) as NativeMermaidResponse | null;
        if (!response.ok) {
          return {
            generatedResponse: undefined,
            error: new Error(payload?.error || "Failed to generate diagram."),
            rateLimit: payload?.rateLimit ?? null,
            rateLimitRemaining: payload?.rateLimitRemaining ?? null,
          };
        }

        const mermaid = payload?.mermaid?.trim();
        if (!mermaid) {
          return {
            generatedResponse: undefined,
            error: new Error("Model did not return a diagram."),
            rateLimit: payload?.rateLimit ?? null,
            rateLimitRemaining: payload?.rateLimitRemaining ?? null,
          };
        }

        return {
          generatedResponse: mermaid,
          rateLimit: payload?.rateLimit ?? null,
          rateLimitRemaining: payload?.rateLimitRemaining ?? null,
        };
      } catch (error) {
        return {
          generatedResponse: undefined,
          error: error instanceof Error ? error : new Error("Request failed"),
          rateLimit: null,
          rateLimitRemaining: null,
        };
      }
    },
    [derivedTitle, getCanvasContext],
  );

  if (!canvas) {
    return null;
  }

  const initialScene = extractScene(canvas);

  return (
    <div className="flex h-full flex-col">
      <header className="bg-card flex items-center gap-3 border-b px-4 py-2">
        <input
          value={title}
          onChange={(e) => {
            setTitleDraft({
              canvasId,
              value: e.target.value,
            });
          }}
          onBlur={() => {
            const trimmed = title.trim();
            if (!trimmed) {
              setTitleDraft({
                canvasId,
                value: null,
              });
              return;
            }

            if (trimmed !== canvas.title) {
              onTitleChange(trimmed);
            }

            setTitleDraft({
              canvasId,
              value: trimmed,
            });
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              (e.target as HTMLInputElement).blur();
            }
          }}
          className="flex-1 bg-transparent text-xl tracking-tight outline-none placeholder:text-[var(--alfred-text-tertiary)]"
          placeholder="Untitled Canvas"
        />
        <span className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
          Canvas
        </span>
      </header>

      <div className="flex-1">
        <Excalidraw
          key={canvas.id}
          excalidrawAPI={(api: ExcalidrawAPI) => {
            apiRef.current = api;
            onApiReady?.(api);
          }}
          initialData={
            initialScene
              ? {
                  elements: initialScene.elements as never,
                  appState: {
                    ...initialScene.appState,
                    theme: "light",
                  } as never,
                }
              : {
                  appState: {
                    viewBackgroundColor: "#FAF8F5",
                    theme: "light",
                  } as never,
                }
          }
          onChange={handleChange as never}
          aiEnabled
          UIOptions={{
            canvasActions: {
              loadScene: true,
              export: { saveFileToDisk: true },
              saveToActiveFile: false,
            },
          }}
        >
          <ExcalidrawTTDDialogTrigger />
          <ExcalidrawTTDDialog onTextSubmit={handleNativeTextToDiagram} />
        </Excalidraw>
      </div>
    </div>
  );
}
