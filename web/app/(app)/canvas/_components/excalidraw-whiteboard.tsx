"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

type ExcalidrawAPI = import("@excalidraw/excalidraw/types").ExcalidrawImperativeAPI;

const Excalidraw = dynamic(
  async () => (await import("@excalidraw/excalidraw")).Excalidraw,
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        Loading whiteboard...
      </div>
    ),
  }
);

const STORAGE_KEY = "alfred-canvas-state";

function loadSavedState(): { elements: unknown[]; appState: Record<string, unknown> } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveState(elements: readonly unknown[], appState: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  try {
    const minimal = {
      elements: elements.filter((el: unknown) => {
        const e = el as Record<string, unknown>;
        return !e.isDeleted;
      }),
      appState: {
        viewBackgroundColor: appState.viewBackgroundColor,
        gridSize: appState.gridSize,
      },
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(minimal));
  } catch {
    // Storage full or unavailable
  }
}

export function ExcalidrawWhiteboard() {
  const apiRef = useRef<ExcalidrawAPI | null>(null);
  const [initialData, setInitialData] = useState<{
    elements: unknown[];
    appState: Record<string, unknown>;
  } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const saved = loadSavedState();
    setInitialData(saved);
    setLoaded(true);
  }, []);

  const handleChange = useCallback(
    (elements: readonly unknown[], appState: Record<string, unknown>) => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = setTimeout(() => {
        saveState(elements, appState);
      }, 1000);
    },
    []
  );

  if (!loaded) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        Loading...
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <Excalidraw
        excalidrawAPI={(api: ExcalidrawAPI) => {
          apiRef.current = api;
        }}
        initialData={
          initialData
            ? {
                elements: initialData.elements as never,
                appState: {
                  ...initialData.appState,
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
        UIOptions={{
          canvasActions: {
            loadScene: true,
            export: { saveFileToDisk: true },
            saveToActiveFile: false,
          },
        }}
        aiEnabled={true}
      />
    </div>
  );
}
