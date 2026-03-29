"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Whiteboard } from "@/features/canvas/queries";

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
 },
);

type ExcalidrawWhiteboardProps = {
 canvas: Whiteboard | null;
 onSaveScene: (scene: { elements: unknown[]; appState: Record<string, unknown> }) => void;
 onTitleChange: (title: string) => void;
 onApiReady?: (api: ExcalidrawAPI) => void;
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
 onApiReady,
}: ExcalidrawWhiteboardProps) {
 const apiRef = useRef<ExcalidrawAPI | null>(null);
 const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
 const lastCanvasIdRef = useRef<number | null>(null);

 // Derive title from canvas prop; local edits override until blur commits
 const derivedTitle = useMemo(() => canvas?.title ?? "", [canvas?.title]);
 const canvasId = canvas?.id ?? null;

 // Reset local title when switching to a different canvas
 const [titleOverride, setTitleOverride] = useState<string | null>(null);
 if (canvasId !== lastCanvasIdRef.current) {
 lastCanvasIdRef.current = canvasId;
 setTitleOverride(null);
 }

 const title = titleOverride ?? derivedTitle;

 const handleChange = useCallback(
 (elements: readonly unknown[], appState: Record<string, unknown>) => {
 if (!canvas) return;
 if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
 saveTimeoutRef.current = setTimeout(() => {
 const filteredElements = (elements as Array<Record<string, unknown>>).filter(
 (el) => !el.isDeleted,
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

 // Cleanup debounce on unmount
 useEffect(() => {
 return () => {
 if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
 };
 }, []);

 // Flush save on visibility change
 useEffect(() => {
 const onVisChange = () => {
 if (document.visibilityState === "hidden" && saveTimeoutRef.current) {
 clearTimeout(saveTimeoutRef.current);
 saveTimeoutRef.current = null;
 const api = apiRef.current;
 if (api && canvas) {
 const els = api.getSceneElements();
 const state = api.getAppState();
 const filteredElements = (els as unknown as Array<Record<string, unknown>>).filter(
 (el) => !el.isDeleted,
 );
 onSaveScene({
 elements: filteredElements,
 appState: {
 viewBackgroundColor: state.viewBackgroundColor,
 gridSize: state.gridSize,
 },
 });
 }
 }
 };
 window.addEventListener("visibilitychange", onVisChange);
 return () => window.removeEventListener("visibilitychange", onVisChange);
 }, [canvas, onSaveScene]);

 if (!canvas) {
 return null;
 }

 const initialScene = extractScene(canvas);

 return (
 <div className="flex h-full flex-col">
 {/* Title bar */}
 <header className="flex items-center gap-3 border-b bg-card px-4 py-2">
 <input
 value={title}
 onChange={(e) => {
 setTitleOverride(e.target.value);
 }}
 onBlur={() => {
 const trimmed = title.trim();
 if (trimmed && trimmed !== canvas.title) {
 onTitleChange(trimmed);
 }
 }}
 onKeyDown={(e) => {
 if (e.key === "Enter") {
 (e.target as HTMLInputElement).blur();
 }
 }}
 className="flex-1 bg-transparent text-xl tracking-tight outline-none placeholder:text-[var(--alfred-text-tertiary)]"
 placeholder="Untitled Canvas"
 />
 <span className="font-medium text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
 Canvas
 </span>
 </header>

 {/* Excalidraw */}
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
 UIOptions={{
 canvasActions: {
 loadScene: true,
 export: { saveFileToDisk: true },
 saveToActiveFile: false,
 },
 }}
 />
 </div>
 </div>
 );
}
