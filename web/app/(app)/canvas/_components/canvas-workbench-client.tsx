"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, Layers, Maximize2, Minimize2 } from "lucide-react";
import { toast } from "sonner";

import { safeGetItem } from "@/lib/storage";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ResizableColumns } from "@/components/ui/resizable-columns";
import { useCanvasList, useCanvas } from "@/features/canvas/queries";
import {
  useCreateCanvas,
  useUpdateCanvas,
  useSaveCanvasScene,
  useDeleteCanvas,
} from "@/features/canvas/mutations";

import { CanvasSidebar } from "./canvas-sidebar";
import { ExcalidrawWhiteboard } from "./excalidraw-whiteboard";
import { CanvasAIPanel } from "./canvas-ai-panel";

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

export function CanvasWorkbenchClient({ initialCanvasId }: { initialCanvasId: number | null }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sidebarSearch, setSidebarSearch] = useState("");
  const [leftWidthPx, setLeftWidthPx] = useState(() =>
    readStoredNumber("alfred:canvas:left-width:v1", 280),
  );
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Derived selected canvas ID from URL
  const urlCanvasParam = searchParams.get("id");
  const selectedCanvasId = urlCanvasParam ? Number(urlCanvasParam) : initialCanvasId;

  // Queries
  const listQuery = useCanvasList();
  const canvases = useMemo(() => listQuery.data ?? [], [listQuery.data]);
  const canvasQuery = useCanvas(selectedCanvasId);
  const activeCanvas = canvasQuery.data ?? null;

  // Mutations
  const createCanvasMutation = useCreateCanvas();
  const updateCanvasMutation = useUpdateCanvas(selectedCanvasId);
  const saveSceneMutation = useSaveCanvasScene(selectedCanvasId);
  const deleteCanvasMutation = useDeleteCanvas();

  // Track whether we've auto-selected the first canvas
  const didAutoSelectRef = useRef(false);

  // Auto-select first canvas when list loads and nothing is selected
  useEffect(() => {
    if (selectedCanvasId) return;
    if (didAutoSelectRef.current) return;
    if (!canvases.length) return;
    didAutoSelectRef.current = true;
    router.replace(`/canvas?id=${canvases[0].id}`);
  }, [selectedCanvasId, canvases, router]);

  // Keyboard shortcuts for fullscreen
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      // Escape exits fullscreen
      if (e.key === "Escape" && isFullscreen) {
        e.preventDefault();
        setIsFullscreen(false);
        return;
      }
      // F11 or Cmd+Shift+F toggles fullscreen
      if (
        e.key === "F11" ||
        ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "f")
      ) {
        e.preventDefault();
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
        if (selectedCanvasId === id) {
          const remaining = canvases.filter((c) => c.id !== id);
          if (remaining.length > 0) {
            router.replace(`/canvas?id=${remaining[0].id}`);
          } else {
            router.replace("/canvas");
          }
        }
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to delete canvas.");
      }
    },
    [deleteCanvasMutation, selectedCanvasId, canvases, router],
  );

  const onSaveScene = useCallback(
    (scene: { elements: unknown[]; appState: Record<string, unknown> }) => {
      if (!selectedCanvasId) return;
      saveSceneMutation.mutate({ scene_json: scene as Record<string, unknown> });
    },
    [selectedCanvasId, saveSceneMutation],
  );

  const onTitleChange = useCallback(
    (title: string) => {
      if (!selectedCanvasId) return;
      updateCanvasMutation.mutate({ title });
    },
    [selectedCanvasId, updateCanvasMutation],
  );

  const handleInsertText = useCallback((text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success("Copied to clipboard — paste onto your canvas (Ctrl+V)");
    }).catch(() => {
      toast("Response copied. Paste onto your canvas.");
    });
  }, []);

  // --- Fullscreen canvas overlay ---
  if (isFullscreen && selectedCanvasId) {
    return (
      <div
        className="fixed inset-0 z-50 bg-background"
        style={{ transition: "opacity 200ms ease-out" }}
      >
        <ExcalidrawWhiteboard
          canvas={activeCanvas}
          onSaveScene={onSaveScene}
          onTitleChange={onTitleChange}
        />

        {/* Exit fullscreen button */}
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="fixed top-3 right-3 z-[60] size-8 rounded-md bg-card/80 shadow-md backdrop-blur-sm border"
          onClick={() => setIsFullscreen(false)}
          title="Exit full screen (Esc)"
        >
          <Minimize2 className="size-4" />
        </Button>

        {/* AI toggle in fullscreen */}
        {!aiPanelOpen && (
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="fixed right-4 bottom-4 z-[60] size-10 rounded-full shadow-lg bg-card"
            onClick={() => setAiPanelOpen(true)}
            title="Ask Alfred (AI)"
          >
            <Bot className="size-4" />
          </Button>
        )}

        {/* Floating AI panel in fullscreen */}
        {aiPanelOpen && activeCanvas && (
          <CanvasAIPanel
            canvasTitle={activeCanvas.title}
            onInsertText={handleInsertText}
            onClose={() => setAiPanelOpen(false)}
          />
        )}
      </div>
    );
  }

  // --- Normal layout ---
  const mainContent = selectedCanvasId ? (
    <div className="relative flex h-full">
      <div className="flex-1 min-h-0">
        <ExcalidrawWhiteboard
          canvas={activeCanvas}
          onSaveScene={onSaveScene}
          onTitleChange={onTitleChange}
        />
      </div>

      {/* Fullscreen toggle — top-right of the canvas area */}
      <Button
        type="button"
        size="icon"
        variant="ghost"
        className="absolute top-2 right-2 z-30 size-8 rounded-md bg-card/80 shadow-sm backdrop-blur-sm border"
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
        <Button type="button" onClick={onCreateCanvas} className="font-mono text-xs">
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

      {/* Floating AI toggle button */}
      {selectedCanvasId && !aiPanelOpen && (
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="fixed right-4 bottom-4 z-50 size-10 rounded-full shadow-lg bg-card"
          onClick={() => setAiPanelOpen(true)}
          title="Ask Alfred (AI)"
        >
          <Bot className="size-4" />
        </Button>
      )}

      {/* Floating AI panel (draggable + resizable) */}
      {aiPanelOpen && activeCanvas && (
        <CanvasAIPanel
          canvasTitle={activeCanvas.title}
          onInsertText={handleInsertText}
          onClose={() => setAiPanelOpen(false)}
        />
      )}
    </div>
  );
}
