"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ExcalidrawImperativeAPI } from "@excalidraw/excalidraw/types";
import { useRouter, useSearchParams } from "next/navigation";
import { Layers, Maximize2, Minimize2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ResizableColumns } from "@/components/ui/resizable-columns";
import {
  useCreateCanvas,
  useDeleteCanvas,
  useSaveCanvasScene,
  useUpdateCanvas,
} from "@/features/canvas/mutations";
import { useCanvas, useCanvasList } from "@/features/canvas/queries";
import { safeGetItem } from "@/lib/storage";

import { CanvasSidebar } from "./canvas-sidebar";
import { ExcalidrawWhiteboard } from "./excalidraw-whiteboard";

type SceneElementLike = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  isDeleted?: boolean;
  type?: string;
  text?: string;
};

function readStoredNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = safeGetItem(key);
    const parsed = raw ? Number(raw) : Number.NaN;
    return Number.isFinite(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function isSceneElementLike(value: unknown): value is SceneElementLike {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SceneElementLike>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.x === "number" &&
    typeof candidate.y === "number" &&
    typeof candidate.width === "number" &&
    typeof candidate.height === "number"
  );
}

function summarizeCanvasContext(api: ExcalidrawImperativeAPI | null, canvasTitle: string): string {
  if (!api) {
    return `Canvas: "${canvasTitle}"`;
  }

  const sceneElements = (api.getSceneElementsIncludingDeleted() as unknown[])
    .filter(isSceneElementLike)
    .filter((element) => !element.isDeleted);

  const nodeCount = sceneElements.filter((element) => element.type !== "arrow").length;
  const connectorCount = sceneElements.filter((element) => element.type === "arrow").length;

  const labels = Array.from(
    new Set(
      sceneElements
        .filter((element) => element.type === "text" && typeof element.text === "string")
        .map((element) => element.text?.trim() || "")
        .filter(Boolean),
    ),
  ).slice(0, 16);

  const selectedIds = Object.keys(api.getAppState().selectedElementIds ?? {});
  const selectedLabels = sceneElements
    .filter((element) => selectedIds.includes(element.id) && element.type === "text")
    .map((element) => element.text?.trim() || "")
    .filter(Boolean)
    .slice(0, 8);

  return [
    `Canvas: "${canvasTitle}"`,
    sceneElements.length
      ? `Current scene: ${nodeCount} nodes and ${connectorCount} connectors.`
      : "Canvas is currently empty.",
    labels.length ? `Visible labels: ${labels.join(", ")}` : null,
    selectedLabels.length ? `Selected labels: ${selectedLabels.join(", ")}` : null,
    !selectedLabels.length && selectedIds.length
      ? `Selected element ids: ${selectedIds.join(", ")}`
      : null,
  ]
    .filter(Boolean)
    .join("\n");
}

export function CanvasWorkbenchClient({ initialCanvasId }: { initialCanvasId: number | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sidebarSearch, setSidebarSearch] = useState("");
  const [leftWidthPx, setLeftWidthPx] = useState(() =>
    readStoredNumber("alfred:canvas:left-width:v1", 280),
  );
  const [isFullscreen, setIsFullscreen] = useState(false);
  const excalidrawApiRef = useRef<ExcalidrawImperativeAPI | null>(null);

  const urlCanvasParam = searchParams.get("id");
  const selectedCanvasId = urlCanvasParam ? Number(urlCanvasParam) : initialCanvasId;

  const listQuery = useCanvasList();
  const canvases = useMemo(() => listQuery.data ?? [], [listQuery.data]);
  const canvasQuery = useCanvas(selectedCanvasId);
  const activeCanvas = canvasQuery.data ?? null;

  const createCanvasMutation = useCreateCanvas();
  const updateCanvasMutation = useUpdateCanvas(selectedCanvasId);
  const saveSceneMutation = useSaveCanvasScene(selectedCanvasId);
  const deleteCanvasMutation = useDeleteCanvas();

  const didAutoSelectRef = useRef(false);

  useEffect(() => {
    if (selectedCanvasId) return;
    if (didAutoSelectRef.current) return;
    if (!canvases.length) return;
    didAutoSelectRef.current = true;
    router.replace(`/canvas?id=${canvases[0].id}`);
  }, [canvases, router, selectedCanvasId]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isFullscreen) {
        event.preventDefault();
        setIsFullscreen(false);
        return;
      }

      if (
        event.key === "F11" ||
        ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "f")
      ) {
        event.preventDefault();
        setIsFullscreen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isFullscreen]);

  const onSelectCanvas = useCallback(
    (id: number) => {
      router.push(`/canvas?id=${id}`);
    },
    [router],
  );

  const onCreateCanvas = useCallback(async () => {
    try {
      const created = await createCanvasMutation.mutateAsync({
        title: "Untitled Canvas",
        initial_scene: {
          elements: [],
          appState: { viewBackgroundColor: "#FAF8F5" },
        },
      });
      router.push(`/canvas?id=${created.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create canvas.");
    }
  }, [createCanvasMutation, router]);

  const onDeleteCanvas = useCallback(
    async (id: number) => {
      try {
        await deleteCanvasMutation.mutateAsync(id);
        toast.success("Canvas archived");

        if (selectedCanvasId !== id) return;

        const remaining = canvases.filter((canvas) => canvas.id !== id);
        if (remaining.length > 0) {
          router.replace(`/canvas?id=${remaining[0].id}`);
        } else {
          router.replace("/canvas");
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to delete canvas.");
      }
    },
    [canvases, deleteCanvasMutation, router, selectedCanvasId],
  );

  const onSaveScene = useCallback(
    (scene: { elements: unknown[]; appState: Record<string, unknown> }) => {
      if (!selectedCanvasId) return;
      saveSceneMutation.mutate({ scene_json: scene as Record<string, unknown> });
    },
    [saveSceneMutation, selectedCanvasId],
  );

  const onTitleChange = useCallback(
    (title: string) => {
      if (!selectedCanvasId) return;
      updateCanvasMutation.mutate({ title });
    },
    [selectedCanvasId, updateCanvasMutation],
  );

  const getCanvasContext = useCallback(
    () =>
      summarizeCanvasContext(excalidrawApiRef.current, activeCanvas?.title ?? "Untitled Canvas"),
    [activeCanvas?.title],
  );

  if (isFullscreen && selectedCanvasId) {
    return (
      <div
        className="bg-background fixed inset-0 z-50"
        style={{ transition: "opacity 200ms ease-out" }}
      >
        <ExcalidrawWhiteboard
          canvas={activeCanvas}
          onSaveScene={onSaveScene}
          onTitleChange={onTitleChange}
          getCanvasContext={getCanvasContext}
          onApiReady={(api) => {
            excalidrawApiRef.current = api;
          }}
        />

        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="bg-card/80 fixed top-3 right-16 z-[60] size-8 rounded-md border shadow-md backdrop-blur-sm"
          onClick={() => setIsFullscreen(false)}
          title="Exit full screen (Esc)"
        >
          <Minimize2 className="size-4" />
        </Button>
      </div>
    );
  }

  const mainContent = selectedCanvasId ? (
    <div className="relative flex h-full">
      <div className="min-h-0 flex-1">
        <ExcalidrawWhiteboard
          canvas={activeCanvas}
          onSaveScene={onSaveScene}
          onTitleChange={onTitleChange}
          getCanvasContext={getCanvasContext}
          onApiReady={(api) => {
            excalidrawApiRef.current = api;
          }}
        />
      </div>

      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="bg-card/80 absolute top-2 right-14 z-30 size-8 rounded-md border shadow-sm backdrop-blur-sm"
        onClick={() => setIsFullscreen(true)}
        title="Full screen (Cmd+Shift+F)"
      >
        <Maximize2 className="size-4" />
      </Button>
    </div>
  ) : (
    <EmptyState
      icon={Layers}
      title="Pick a canvas"
      description="Select a canvas on the left, or create a new one."
      action={
        <Button type="button" onClick={onCreateCanvas} className="text-xs">
          New canvas
        </Button>
      }
      className="h-full"
    />
  );

  return (
    <div className="relative h-full w-full">
      <ResizableColumns
        storageKey="alfred:canvas:left-width:v1"
        leftWidthPx={leftWidthPx}
        onLeftWidthPxChange={setLeftWidthPx}
        minLeftPx={220}
        left={
          <CanvasSidebar
            canvases={canvases}
            selectedCanvasId={selectedCanvasId}
            search={sidebarSearch}
            onSearchChange={setSidebarSearch}
            onSelectCanvas={onSelectCanvas}
            onCreateCanvas={onCreateCanvas}
            onDeleteCanvas={onDeleteCanvas}
            isLoading={listQuery.isPending}
          />
        }
        right={mainContent}
      />
    </div>
  );
}
