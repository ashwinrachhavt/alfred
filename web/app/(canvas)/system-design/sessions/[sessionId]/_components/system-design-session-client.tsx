"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { formatErrorMessage } from "@/lib/utils";

import {
  autosaveSystemDesignDiagram,
  getSystemDesignSession,
  updateSystemDesignNotes,
  updateSystemDesignSession,
} from "@/lib/api/system-design";
import type {
  ExcalidrawData,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishResponse,
  SystemDesignSession,
} from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";

import type {
  ExcalidrawCanvasHandle,
  ExcalidrawCanvasSelection,
} from "@/components/system-design/excalidraw-canvas";
import {
  SystemDesignNotesEditor,
  type SystemDesignNotesEditorHandle,
} from "@/components/system-design/system-design-notes-editor";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

import { SessionHeader } from "./session-header";
import { SessionCanvas } from "./session-canvas";
import { SessionAiDialog } from "./session-dialogs";

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

export function SystemDesignSessionClient({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<SystemDesignSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [_isActionRunning, setIsActionRunning] = useState(false);

  const [_knowledgeDraft, setKnowledgeDraft] = useState<SystemDesignKnowledgeDraft | null>(null);

  const [problemStatement, setProblemStatement] = useState("");

  const [_publishLearningTopics] = useState(true);
  const [_publishZettels] = useState(true);

  const [_topicTitle, _setTopicTitle] = useState("");
  const [_publishResult, setPublishResult] = useState<SystemDesignPublishResponse | null>(null);

  const canvasRef = useRef<ExcalidrawCanvasHandle | null>(null);
  const [canvasSelection, setCanvasSelection] = useState<ExcalidrawCanvasSelection | null>(null);
  const [isPropertiesOpen, setIsPropertiesOpen] = useState(false);
  const [propertiesTarget, setPropertiesTarget] = useState<ExcalidrawCanvasSelection | null>(null);
  const [propertiesName, setPropertiesName] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  const [_autosaveState, setAutosaveState] = useState<AutosaveState>("idle");

  const autosaveTimerRef = useRef<number | null>(null);
  const latestDiagramRef = useRef<ExcalidrawData | null>(null);
  const autosaveInFlightRef = useRef<Promise<void> | null>(null);
  const autosaveFlushRef = useRef<Promise<void> | null>(null);
  const diagramRevisionRef = useRef(0);
  const lastSavedRevisionRef = useRef(0);
  const sessionVersionRef = useRef<number>(1);
  const templateAppliedSessionRef = useRef<string | null>(null);
  const isApplyingTemplateRef = useRef(false);

  const [actionError, setActionError] = useState<string | null>(null);
  const [, setAnalysis] = useState<unknown>(null);
  const [, setQuestions] = useState<unknown>(null);
  const [, setSuggestions] = useState<unknown[]>([]);
  const [, setEvaluation] = useState<unknown>(null);

  const [notesMarkdown, setNotesMarkdown] = useState<string>("");
  const notesTimerRef = useRef<number | null>(null);
  const latestNotesRef = useRef<string>("");
  const notesEditorRef = useRef<SystemDesignNotesEditorHandle | null>(null);
  const notesInitializedRef = useRef(false);

  // Panel visibility state
  const [showDiagram, setShowDiagram] = useState(true);
  const [showEditor, setShowEditor] = useState(true);

  const [isComponentPaletteOpen, setIsComponentPaletteOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [selectedElementIds, setSelectedElementIds] = useState<string[]>([]);

  const [isConnectMode, setIsConnectMode] = useState(false);
  const [connectSourceId, setConnectSourceId] = useState<string | null>(null);

  const [exportBackground, setExportBackground] = useState(true);
  const [pngMaxWidthOrHeight, setPngMaxWidthOrHeight] = useState<number>(3840);

  const [isAiDialogOpen, setIsAiDialogOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [isGeneratingDiagram, setIsGeneratingDiagram] = useState(false);
  const [diagramGenerationError, setDiagramGenerationError] = useState<string | null>(null);

  // Panel widths (percentages)
  const [diagramWidth, setDiagramWidth] = useState(60);

  const isDraggingDiagram = useRef(false);

  const generateDiagramFromPrompt = async () => {
    if (!aiPrompt.trim()) return;
    setIsGeneratingDiagram(true);
    setDiagramGenerationError(null);

    try {
      const response = await fetch("/api/ai/system-design-diagram", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          prompt: aiPrompt,
          problemStatement,
        }),
      });

      const payload = (await response.json()) as { mermaid?: string; error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "Failed to generate diagram.");
      }

      if (!payload.mermaid) {
        throw new Error("No diagram returned.");
      }

      await canvasRef.current?.replaceWithMermaid(payload.mermaid);
      setIsAiDialogOpen(false);
      setAiPrompt("");
    } catch (err) {
      setDiagramGenerationError(formatErrorMessage(err));
    } finally {
      setIsGeneratingDiagram(false);
    }
  };

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setActionError(null);
      setAnalysis(null);
      setQuestions(null);
      setSuggestions([]);
      setEvaluation(null);
      setKnowledgeDraft(null);
      setPublishResult(null);
      notesInitializedRef.current = false;
      latestNotesRef.current = "";
      setNotesMarkdown("");
      try {
        const next = await getSystemDesignSession(sessionId);
        setSession(next);
        sessionVersionRef.current = next.version;
        setProblemStatement(next.problem_statement);
        if (!notesInitializedRef.current) {
          const initialNotes = next.notes_markdown ?? "";
          notesInitializedRef.current = true;
          latestNotesRef.current = initialNotes;
          setNotesMarkdown(initialNotes);
        }
      } catch (err) {
        setActionError(formatErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [sessionId]);

  useEffect(() => {
    return () => {
      if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
      if (notesTimerRef.current) window.clearTimeout(notesTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!isConnectMode || !connectSourceId) return;
    if (selectedElementIds.length !== 1) return;

    const targetId = selectedElementIds[0];
    if (targetId === connectSourceId) return;

    canvasRef.current?.connectElements({
      fromElementId: connectSourceId,
      toElementId: targetId,
    });

    setIsConnectMode(false);
    setConnectSourceId(null);
  }, [connectSourceId, isConnectMode, selectedElementIds]);

  useEffect(() => {
    if (showDiagram) return;
    setIsConnectMode(false);
    setConnectSourceId(null);
    setIsComponentPaletteOpen(false);
    setIsExportOpen(false);
    setSelectedElementIds([]);
  }, [showDiagram]);

  useEffect(() => {
    if (!session) return;
    if (isApplyingTemplateRef.current) return;
    if (templateAppliedSessionRef.current === session.id) return;

    const metadata = session.diagram?.metadata;
    const mermaid =
      metadata && typeof metadata === "object" ? (metadata as Record<string, unknown>).mermaid : null;
    if (typeof mermaid !== "string" || !mermaid.trim()) return;
    if (session.diagram?.elements?.length) {
      templateAppliedSessionRef.current = session.id;
      return;
    }

    isApplyingTemplateRef.current = true;
    void (async () => {
      try {
        for (let attempt = 0; attempt < 50; attempt += 1) {
          const handle = canvasRef.current;
          if (handle) {
            await handle.replaceWithMermaid(mermaid);
            const nextDiagram = handle.getDiagram();
            if (nextDiagram && nextDiagram.elements.length) {
              queueAutosave(nextDiagram);
              await flushAutosave().catch(() => {});
              templateAppliedSessionRef.current = session.id;
              break;
            }
          }
          await new Promise((resolve) => window.setTimeout(resolve, 100));
        }
      } finally {
        isApplyingTemplateRef.current = false;
      }
    })();
  }, [session]);

  const mainGridTemplateColumns = useMemo(() => {
    const hasLeft = showDiagram;
    const hasMiddle = showEditor;

    if (hasLeft && hasMiddle) return `${diagramWidth}% auto 1fr`;
    if (hasLeft) return "1fr";
    if (hasMiddle) return "1fr";
    return "1fr";
  }, [diagramWidth, showDiagram, showEditor]);

  // Resize handlers
  const handleDiagramResize = (e: MouseEvent) => {
    if (!isDraggingDiagram.current || !containerRef.current) return;
    const containerWidth = containerRef.current.offsetWidth;
    const newWidth = (e.clientX / containerWidth) * 100;
    setDiagramWidth(Math.max(20, Math.min(80, newWidth)));
  };

  const startDiagramResize = () => {
    isDraggingDiagram.current = true;
    setIsResizing(true);
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", handleDiagramResize);
    document.addEventListener("mouseup", stopDiagramResize);
  };

  const stopDiagramResize = () => {
    isDraggingDiagram.current = false;
    setIsResizing(false);
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", handleDiagramResize);
    document.removeEventListener("mouseup", stopDiagramResize);
  };

  async function flushAutosave() {
    if (!latestDiagramRef.current) return;
    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }

    if (autosaveFlushRef.current) {
      return autosaveFlushRef.current;
    }

    const flushPromise = (async () => {
      while (latestDiagramRef.current && lastSavedRevisionRef.current < diagramRevisionRef.current) {
        if (autosaveInFlightRef.current) {
          await autosaveInFlightRef.current;
          continue;
        }

        const diagramToSave = latestDiagramRef.current;
        const expectedVersion = sessionVersionRef.current;
        const revisionToSave = diagramRevisionRef.current;

        setAutosaveState("saving");
        const savePromise = autosaveSystemDesignDiagram(sessionId, {
          diagram: diagramToSave,
          label: null,
          expected_version: expectedVersion,
        })
          .then((next) => {
            sessionVersionRef.current = next.version;
            lastSavedRevisionRef.current = revisionToSave;
            setSession((prev) =>
              prev ? { ...prev, updated_at: next.updated_at, version: next.version } : prev,
            );
            setAutosaveState("saved");
          })
          .catch((err) => {
            setAutosaveState("error");
            if (err instanceof ApiError && err.status === 409) {
              setActionError(formatErrorMessage(err));
            }
            throw err;
          })
          .finally(() => {
            autosaveInFlightRef.current = null;
          });

        autosaveInFlightRef.current = savePromise;
        await savePromise;
      }
    })().finally(() => {
      autosaveFlushRef.current = null;
    });

    autosaveFlushRef.current = flushPromise;
    return flushPromise;
  }

  function queueAutosave(diagram: ExcalidrawData) {
    latestDiagramRef.current = diagram;
    diagramRevisionRef.current += 1;
    setAutosaveState("dirty");

    if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = window.setTimeout(() => {
      void flushAutosave().catch(() => {});
    }, 1200);
  }

  async function flushNotesSave() {
    const notes = latestNotesRef.current;
    if (notesTimerRef.current) {
      window.clearTimeout(notesTimerRef.current);
      notesTimerRef.current = null;
    }

    try {
      const next = await updateSystemDesignNotes(sessionId, { notes_markdown: notes });
      setSession((prev) => (prev ? { ...prev, updated_at: next.updated_at } : prev));
    } catch {}
  }

  function queueNotesSave(nextMarkdown: string) {
    latestNotesRef.current = nextMarkdown;
    setNotesMarkdown(nextMarkdown);

    if (notesTimerRef.current) window.clearTimeout(notesTimerRef.current);
    notesTimerRef.current = window.setTimeout(() => {
      void flushNotesSave();
    }, 1200);
  }

  async function withFreshDiagram<T>(fn: () => Promise<T>): Promise<T> {
    setActionError(null);
    await flushAutosave();
    return fn();
  }

  async function runAction<T>(fn: () => Promise<T>, onSuccess: (value: T) => void) {
    setIsActionRunning(true);
    setActionError(null);
    try {
      const result = await withFreshDiagram(fn);
      onSuccess(result);
    } catch (err) {
      setActionError(formatErrorMessage(err));
    } finally {
      setIsActionRunning(false);
    }
  }

  function toExportBasename(title: string | null | undefined, id: string): string {
    const base = (title ?? "").trim();
    const raw = base.length ? base : `system-design-${id.slice(0, 8)}`;
    return raw
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "")
      .slice(0, 80);
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function downloadTextFile(text: string, filename: string, mimeType: string) {
    downloadBlob(new Blob([text], { type: mimeType }), filename);
  }

  async function copyToClipboard(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {}

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "true");
    textarea.style.position = "fixed";
    textarea.style.top = "0";
    textarea.style.left = "0";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
    } catch {
      // Ignore clipboard failures.
    } finally {
      textarea.remove();
    }
  }

  const handleConnectClick = () => {
    if (isConnectMode) {
      setIsConnectMode(false);
      setConnectSourceId(null);
      return;
    }

    const selected = selectedElementIds[0];
    if (!selected) return;
    setConnectSourceId(selected);
    setIsConnectMode(true);
  };

  const handleCanvasDoubleClick = () => {
    if (!canvasSelection) return;
    setPropertiesTarget(canvasSelection);
    setPropertiesName(canvasSelection.name);
    setIsPropertiesOpen(true);
  };

  const handleSelectionDetailsChange = (selection: ExcalidrawCanvasSelection | null) => {
    setCanvasSelection(selection);

    if (!isPropertiesOpen) return;
    if (!selection) {
      setIsPropertiesOpen(false);
      setPropertiesTarget(null);
      return;
    }

    setPropertiesTarget((prev) => {
      if (!prev || prev.elementId !== selection.elementId) {
        setPropertiesName(selection.name);
        return selection;
      }
      return prev;
    });
  };

  const handleApplyName = () => {
    const nextName = propertiesName.trim();
    if (!nextName) return;
    canvasRef.current?.updateComponentLabel(propertiesTarget!.elementId, nextName);
  };

  if (isLoading) {
    return (
      <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
        Loading session…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-10">
        <h1 className="text-2xl font-semibold">System Design Session</h1>
        <p className="text-muted-foreground text-sm">{actionError ?? "Session not found."}</p>
        <Button asChild variant="outline">
          <Link href="/system-design">Back</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 p-2">
      {/* Header */}
      <SessionHeader
        session={session}
        onSessionUpdated={setSession}
        showDiagram={showDiagram}
        showEditor={showEditor}
        onToggleDiagram={() => setShowDiagram((prev) => !prev)}
        onToggleEditor={() => setShowEditor((prev) => !prev)}
        isComponentPaletteOpen={isComponentPaletteOpen}
        onComponentPaletteOpenChange={setIsComponentPaletteOpen}
        isExportOpen={isExportOpen}
        onExportOpenChange={setIsExportOpen}
        isConnectMode={isConnectMode}
        selectedElementIds={selectedElementIds}
        onConnectClick={handleConnectClick}
        canvasRef={canvasRef}
        exportBackground={exportBackground}
        onExportBackgroundChange={setExportBackground}
        pngMaxWidthOrHeight={pngMaxWidthOrHeight}
        onPngMaxWidthOrHeightChange={setPngMaxWidthOrHeight}
        onOpenAiDialog={() => {
          setDiagramGenerationError(null);
          setIsAiDialogOpen(true);
        }}
        downloadBlob={downloadBlob}
        downloadTextFile={downloadTextFile}
        copyToClipboard={copyToClipboard}
        toExportBasename={toExportBasename}
      />

      <SessionAiDialog
        isOpen={isAiDialogOpen}
        onOpenChange={setIsAiDialogOpen}
        aiPrompt={aiPrompt}
        onAiPromptChange={setAiPrompt}
        isGenerating={isGeneratingDiagram}
        generationError={diagramGenerationError}
        onGenerate={() => void generateDiagramFromPrompt()}
      />

      {/* Main Content Grid */}
      <div
        ref={containerRef}
        className="grid min-h-0 flex-1 gap-0"
        style={{ gridTemplateColumns: mainGridTemplateColumns }}
      >
        {/* Excalidraw Panel - Collapsible */}
        {showDiagram && (
          <SessionCanvas
            canvasRef={canvasRef}
            initialDiagram={session.diagram}
            isResizing={isResizing}
            isPropertiesOpen={isPropertiesOpen}
            propertiesTarget={propertiesTarget}
            propertiesName={propertiesName}
            onDiagramChange={queueAutosave}
            onSelectionChange={setSelectedElementIds}
            onSelectionDetailsChange={handleSelectionDetailsChange}
            onCanvasDoubleClick={handleCanvasDoubleClick}
            onPropertiesNameChange={setPropertiesName}
            onPropertiesClose={() => setIsPropertiesOpen(false)}
            onApplyName={handleApplyName}
          />
        )}

        {/* Resize Handle for Diagram */}
        {showDiagram && showEditor && (
          <div
            className="group bg-border hover:bg-primary relative w-1 cursor-col-resize transition-colors"
            onMouseDown={startDiagramResize}
          >
            <div className="absolute inset-y-0 -right-1 -left-1 z-10" />
            <div className="bg-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full p-1 opacity-0 transition-opacity group-hover:opacity-100">
              <div className="bg-primary-foreground h-8 w-0.5" />
            </div>
          </div>
        )}

        {/* Editor Panel - Collapsible */}
        {showEditor && (
          <div className="flex min-h-0 flex-col gap-3">
            <div className="bg-background flex flex-col gap-2 rounded-xl border px-4 py-3">
              <span className="text-sm font-medium">Problem Statement</span>
              <Textarea
                value={problemStatement}
                onChange={(e) => {
                  setProblemStatement(e.target.value);
                }}
                onBlur={() => {
                  if (problemStatement !== session.problem_statement) {
                    void runAction(
                      () =>
                        updateSystemDesignSession(sessionId, {
                          problem_statement: problemStatement,
                        }),
                      setSession,
                    );
                  }
                }}
                readOnly={false}
                rows={4}
                className="resize-none"
                placeholder="Describe the system design problem..."
              />
            </div>

            <div className="min-h-0 flex-1">
              <SystemDesignNotesEditor
                ref={notesEditorRef}
                markdown={notesMarkdown}
                onMarkdownChange={queueNotesSave}
                placeholder="Write your notes, architecture decisions, and design thoughts here…"
              />
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
