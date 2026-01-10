"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Download,
  Link2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Shapes,
  WandSparkles,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";

import {
  analyzeSystemDesign,
  autosaveSystemDesignDiagram,
  evaluateSystemDesign,
  getSystemDesignKnowledgeDraft,
  getSystemDesignQuestions,
  getSystemDesignSession,
  getSystemDesignSuggestions,
  publishSystemDesignSession,
  updateSystemDesignNotes,
  updateSystemDesignSession,
} from "@/lib/api/system-design";
import type {
  DiagramAnalysis,
  DiagramEvaluation,
  DiagramQuestion,
  DiagramSuggestion,
  ExcalidrawData,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishRequest,
  SystemDesignPublishResponse,
  SystemDesignSession,
} from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";
import { diagramToMermaid, diagramToPlantUml } from "@/lib/system-design/code-export";

import {
  ExcalidrawCanvas,
  type ExcalidrawCanvasHandle,
  type ExcalidrawCanvasSelection,
} from "@/components/system-design/excalidraw-canvas";
import { SystemDesignComponentPalette } from "@/components/system-design/system-design-component-palette";
import {
  SystemDesignNotesEditor,
  type SystemDesignNotesEditorHandle,
} from "@/components/system-design/system-design-notes-editor";
import { SystemDesignShareDialog } from "@/components/system-design/system-design-share-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function SystemDesignSessionClient({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<SystemDesignSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionRunning, setIsActionRunning] = useState(false);

  const [analysis, setAnalysis] = useState<DiagramAnalysis | null>(null);
  const [questions, setQuestions] = useState<DiagramQuestion[] | null>(null);
  const [suggestions, setSuggestions] = useState<DiagramSuggestion[]>([]);
  const [evaluation, setEvaluation] = useState<DiagramEvaluation | null>(null);
  const [knowledgeDraft, setKnowledgeDraft] = useState<SystemDesignKnowledgeDraft | null>(null);

  const [problemStatement, setProblemStatement] = useState("");

  const [publishLearningTopics, setPublishLearningTopics] = useState(true);
  const [publishZettels, setPublishZettels] = useState(true);

  const [topicTitle, setTopicTitle] = useState("");
  const [publishResult, setPublishResult] = useState<SystemDesignPublishResponse | null>(null);

  const canvasRef = useRef<ExcalidrawCanvasHandle | null>(null);
  const [canvasSelection, setCanvasSelection] = useState<ExcalidrawCanvasSelection | null>(null);
  const [isPropertiesOpen, setIsPropertiesOpen] = useState(false);
  const [propertiesTarget, setPropertiesTarget] = useState<ExcalidrawCanvasSelection | null>(null);
  const [propertiesName, setPropertiesName] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  const [autosaveState, setAutosaveState] = useState<AutosaveState>("idle");

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

  const [notesMarkdown, setNotesMarkdown] = useState<string>("");
  const notesTimerRef = useRef<number | null>(null);
  const latestNotesRef = useRef<string>("");
  const notesEditorRef = useRef<SystemDesignNotesEditorHandle | null>(null);
  const notesInitializedRef = useRef(false);

  // Panel visibility state
  const [showDiagram, setShowDiagram] = useState(true); // Default to showing diagram
  const [showEditor, setShowEditor] = useState(true);
  const [showCoach, setShowCoach] = useState(false);

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
  const [diagramWidth, setDiagramWidth] = useState(60); // Excalidraw gets 60% by default
  const [coachWidth, setCoachWidth] = useState(400); // Coach panel fixed at 400px

  const isDraggingDiagram = useRef(false);
  const isDraggingCoach = useRef(false);

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
  }, [connectSourceId, isConnectMode, selectedElementIds]);

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
    // Account for resize handles (w-1 = 4px) in the grid columns.
    // Possible structure: [Left] [Handle] [Editor] [Handle] [Coach]
    const hasMiddle = showEditor;
    const hasLeft = showDiagram;
    const hasRight = showCoach;

    if (hasLeft && hasMiddle && hasRight) return `${diagramWidth}% auto 1fr auto ${coachWidth}px`;
    if (hasLeft && hasMiddle) return `${diagramWidth}% auto 1fr`;
    if (hasMiddle && hasRight) return `1fr auto ${coachWidth}px`;
    if (hasLeft && hasRight) return `1fr auto ${coachWidth}px`;
    if (hasLeft) return "1fr";
    if (hasMiddle) return "1fr";
    if (hasRight) return "1fr";
    return "1fr";
  }, [coachWidth, diagramWidth, showCoach, showDiagram, showEditor]);

  // Resize handlers
  const handleDiagramResize = (e: MouseEvent) => {
    if (!isDraggingDiagram.current || !containerRef.current) return;
    const containerWidth = containerRef.current.offsetWidth;
    const newWidth = (e.clientX / containerWidth) * 100;
    setDiagramWidth(Math.max(20, Math.min(80, newWidth))); // Clamp between 20% and 80%
  };

  const handleCoachResize = (e: MouseEvent) => {
    if (!isDraggingCoach.current) return;
    const newWidth = window.innerWidth - e.clientX;
    setCoachWidth(Math.max(300, Math.min(600, newWidth))); // Clamp between 300px and 600px
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

  const startCoachResize = () => {
    isDraggingCoach.current = true;
    setIsResizing(true);
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", handleCoachResize);
    document.addEventListener("mouseup", stopCoachResize);
  };

  const stopCoachResize = () => {
    isDraggingCoach.current = false;
    setIsResizing(false);
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", handleCoachResize);
    document.removeEventListener("mouseup", stopCoachResize);
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight">
            {session.title ?? "System Design Session"}
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            className="gap-2"
            onClick={() => {
              setDiagramGenerationError(null);
              setIsAiDialogOpen(true);
            }}
            disabled={!showDiagram}
            title={
              !showDiagram ? "Show Diagram to generate into the canvas." : "Generate a new diagram"
            }
          >
            <WandSparkles className="size-4" />
            Generate
          </Button>

          <Sheet open={isComponentPaletteOpen} onOpenChange={setIsComponentPaletteOpen}>
            <SheetTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={!showDiagram}
                title={!showDiagram ? "Show Diagram to insert components." : "Open component library"}
              >
                <Shapes className="size-4" />
                Components
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[420px] sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Component library</SheetTitle>
                <SheetDescription>
                  Click a component to drop it onto the canvas.
                </SheetDescription>
              </SheetHeader>
              <div className="min-h-0 flex-1 overflow-hidden">
                <SystemDesignComponentPalette
                  showHeader={false}
                  onInsert={(component) => {
                    canvasRef.current?.insertComponent(component);
                  }}
                />
              </div>
            </SheetContent>
          </Sheet>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={isConnectMode ? "secondary" : "outline"}
                size="sm"
                className="gap-2"
                disabled={!showDiagram || (!isConnectMode && selectedElementIds.length !== 1)}
                onClick={() => {
                  if (isConnectMode) {
                    setIsConnectMode(false);
                    setConnectSourceId(null);
                    return;
                  }

                  const selected = selectedElementIds[0];
                  if (!selected) return;
                  setConnectSourceId(selected);
                  setIsConnectMode(true);
                }}
              >
                <Link2 className="size-4" />
                {isConnectMode ? "Cancel connect" : "Connect"}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {isConnectMode
                ? "Select a target component on the canvas."
                : selectedElementIds.length === 1
                  ? "Connect selected component to another."
                  : "Select exactly one component to start a connection."}
            </TooltipContent>
          </Tooltip>

          <Sheet open={isExportOpen} onOpenChange={setIsExportOpen}>
            <SheetTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={!showDiagram}
                title={!showDiagram ? "Show Diagram to export." : "Export diagram"}
              >
                <Download className="size-4" />
                Export
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[420px] sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Export</SheetTitle>
                <SheetDescription>Download images or copy diagram code.</SheetDescription>
              </SheetHeader>

              <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
                <div className="space-y-3">
                  <div className="space-y-1">
                    <h3 className="text-sm font-medium">PNG</h3>
                    <p className="text-muted-foreground text-xs">
                      Exports the current canvas view as a PNG.
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <div className="space-y-1">
                      <Label htmlFor="sd-export-png-max">Max size</Label>
                      <select
                        id="sd-export-png-max"
                        className="bg-background h-9 rounded-md border px-3 text-sm"
                        value={pngMaxWidthOrHeight}
                        onChange={(e) => setPngMaxWidthOrHeight(Number(e.target.value))}
                      >
                        <option value={0}>Default</option>
                        <option value={1920}>1080p (max 1920px)</option>
                        <option value={3840}>4K (max 3840px)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor="sd-export-background">Background</Label>
                      <div className="flex h-9 items-center">
                        <Switch
                          id="sd-export-background"
                          checked={exportBackground}
                          onCheckedChange={setExportBackground}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      onClick={async () => {
                        const blob = await canvasRef.current?.exportPng({
                          maxWidthOrHeight: pngMaxWidthOrHeight || undefined,
                          background: exportBackground,
                        });
                        if (!blob) return;
                        downloadBlob(blob, `${toExportBasename(session.title, session.id)}.png`);
                      }}
                    >
                      Download PNG
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        const svg = await canvasRef.current?.exportSvg({ embedScene: true });
                        if (!svg) return;
                        downloadTextFile(
                          svg,
                          `${toExportBasename(session.title, session.id)}.svg`,
                          "image/svg+xml",
                        );
                      }}
                    >
                      Download SVG
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={async () => {
                        const svg = await canvasRef.current?.exportSvg({ embedScene: false });
                        if (!svg) return;
                        const win = window.open("", "_blank", "noopener,noreferrer");
                        if (!win) return;
                        win.document.open();
                        win.document.write(`<!doctype html><html><head><title>Export</title></head><body style="margin:0">${svg}</body></html>`);
                        win.document.close();
                        win.focus();
                        win.print();
                      }}
                    >
                      Print (PDF)
                    </Button>
                  </div>
                </div>

                <Separator />

                <div className="space-y-3">
                  <div className="space-y-1">
                    <h3 className="text-sm font-medium">Code</h3>
                    <p className="text-muted-foreground text-xs">
                      Generates a basic diagram graph from bound arrows.
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                        void copyToClipboard(diagramToMermaid(diagram));
                      }}
                    >
                      Copy Mermaid
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                        void copyToClipboard(diagramToPlantUml(diagram));
                      }}
                    >
                      Copy PlantUML
                    </Button>
                  </div>
                </div>

                <Separator />

                <div className="space-y-3">
                  <div className="space-y-1">
                    <h3 className="text-sm font-medium">Raw</h3>
                    <p className="text-muted-foreground text-xs">
                      Downloads the persisted Excalidraw JSON for version control.
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                      downloadTextFile(
                        JSON.stringify(diagram, null, 2),
                        `${toExportBasename(session.title, session.id)}.excalidraw.json`,
                        "application/json",
                      );
                    }}
                  >
                    Download JSON
                  </Button>
                </div>
              </div>
            </SheetContent>
          </Sheet>

          <div className="bg-background/70 flex items-center rounded-xl border p-1 shadow-sm backdrop-blur-sm">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className={cn(
                    "rounded-lg",
                    showDiagram ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                  )}
                  onClick={() => setShowDiagram((prev) => !prev)}
                >
                  {showDiagram ? (
                    <PanelLeftClose className="size-4" />
                  ) : (
                    <PanelLeftOpen className="size-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{showDiagram ? "Hide diagram" : "Show diagram"}</TooltipContent>
            </Tooltip>

            <div className="bg-border mx-1 h-6 w-px" />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className={cn(
                    "rounded-lg",
                    showEditor ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                  )}
                  onClick={() => setShowEditor((prev) => !prev)}
                >
                  {showEditor ? (
                    <PanelRightClose className="size-4" />
                  ) : (
                    <PanelRightOpen className="size-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{showEditor ? "Hide editor" : "Show editor"}</TooltipContent>
            </Tooltip>

            <div className="bg-border mx-1 h-6 w-px" />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className={cn(
                    "rounded-lg",
                    showCoach ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                  )}
                  onClick={() => setShowCoach((prev) => !prev)}
                >
                  {showCoach ? (
                    <PanelRightClose className="size-4" />
                  ) : (
                    <PanelRightOpen className="size-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{showCoach ? "Hide coach" : "Show coach"}</TooltipContent>
            </Tooltip>
          </div>

          <SystemDesignShareDialog session={session} onSessionUpdated={setSession} />
          <Button asChild variant="ghost" size="sm">
            <Link href="/system-design">Exit</Link>
          </Button>
        </div>
      </div>

      <Dialog open={isAiDialogOpen} onOpenChange={setIsAiDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate system diagram</DialogTitle>
            <DialogDescription>
              Describe the architecture you want. Alfred will generate a new Excalidraw diagram.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="ai-diagram-prompt">Prompt</Label>
            <Textarea
              id="ai-diagram-prompt"
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              rows={6}
              className="resize-none"
              placeholder="Example: Design a URL shortener with analytics, rate limiting, and a queue-based write path."
            />
            {diagramGenerationError ? (
              <Alert variant="destructive" className="px-3 py-2">
                <AlertDescription className="text-destructive">
                  {diagramGenerationError}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsAiDialogOpen(false)}
              disabled={isGeneratingDiagram}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void generateDiagramFromPrompt()}
              disabled={isGeneratingDiagram || !aiPrompt.trim()}
            >
              {isGeneratingDiagram ? "Generating…" : "Generate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Main Content Grid */}
      <div
        ref={containerRef}
        className="grid min-h-0 flex-1 gap-0"
        style={{ gridTemplateColumns: mainGridTemplateColumns }}
      >
        {/* Excalidraw Panel - Collapsible */}
        {showDiagram && (
          <div className="bg-background relative flex min-h-0 flex-col overflow-hidden rounded-xl border">
            {/* Overlay during resize to prevent event trapping */}
            {isResizing && <div className="absolute inset-0 z-50 bg-transparent" />}

            <div className="min-h-0 flex-1 p-0">
              <div
                className="relative h-full w-full"
                onDoubleClick={() => {
                  if (!canvasSelection) return;
                  setPropertiesTarget(canvasSelection);
                  setPropertiesName(canvasSelection.name);
                  setIsPropertiesOpen(true);
                }}
              >
                <ExcalidrawCanvas
                  ref={canvasRef}
                  initialDiagram={session.diagram}
                  onDiagramChange={queueAutosave}
                  onSelectionChange={setSelectedElementIds}
                  onSelectionDetailsChange={(selection) => {
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
                  }}
                  framed={false}
                  viewportScale={1}
                />

                {isPropertiesOpen && propertiesTarget ? (
                  <Card
                    className="bg-background/95 absolute top-3 right-3 z-20 w-80 border shadow-lg backdrop-blur"
                    onDoubleClick={(event) => event.stopPropagation()}
                  >
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 py-3">
                      <CardTitle className="text-sm">Properties</CardTitle>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => {
                          setIsPropertiesOpen(false);
                        }}
                      >
                        <X className="size-4" />
                      </Button>
                    </CardHeader>
                    <CardContent className="space-y-4 px-4 pb-4">
                      <div className="flex flex-wrap gap-2">
                        {propertiesTarget.category ? (
                          <Badge variant="secondary">
                            {propertiesTarget.category.replaceAll("_", " ")}
                          </Badge>
                        ) : (
                          <Badge variant="secondary">component</Badge>
                        )}
                        <Badge variant="outline">id: {propertiesTarget.elementId}</Badge>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="sd-component-name">Name</Label>
                        <Input
                          id="sd-component-name"
                          value={propertiesName}
                          onChange={(e) => setPropertiesName(e.target.value)}
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key !== "Enter") return;
                            const nextName = propertiesName.trim();
                            if (!nextName) return;
                            canvasRef.current?.updateComponentLabel(propertiesTarget.elementId, nextName);
                          }}
                        />
                      </div>

                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setIsPropertiesOpen(false)}
                        >
                          Close
                        </Button>
                        <Button
                          size="sm"
                          disabled={!propertiesName.trim()}
                          onClick={() => {
                            const nextName = propertiesName.trim();
                            if (!nextName) return;
                            canvasRef.current?.updateComponentLabel(propertiesTarget.elementId, nextName);
                          }}
                        >
                          Apply
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : null}
              </div>
            </div>
          </div>
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

        {/* Resize Handle for Coach */}
        {showCoach && (showDiagram || showEditor) && (
          <div
            className="group bg-border hover:bg-primary relative w-1 cursor-col-resize transition-colors"
            onMouseDown={startCoachResize}
          >
            <div className="absolute inset-y-0 -right-1 -left-1 z-10" />
            <div className="bg-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full p-1 opacity-0 transition-opacity group-hover:opacity-100">
              <div className="bg-primary-foreground h-8 w-0.5" />
            </div>
          </div>
        )}

        {/* Coach Panel - Collapsible */}
        {showCoach && (
          <Card className="flex min-h-0 flex-col">
            <CardHeader className="space-y-2">
              <CardTitle className="flex items-center justify-between">
                <span>Coach</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void flushAutosave()}
                  disabled={autosaveState === "saving"}
                >
                  Save diagram
                </Button>
              </CardTitle>
              {actionError ? (
                <Alert variant="destructive">
                  <AlertDescription className="text-destructive">{actionError}</AlertDescription>
                </Alert>
              ) : null}
            </CardHeader>

            <CardContent className="min-h-0 flex-1 overflow-auto">
              <Tabs defaultValue="analysis">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="analysis">Analyze</TabsTrigger>
                  <TabsTrigger value="qna">Q&A</TabsTrigger>
                  <TabsTrigger value="publish">Publish</TabsTrigger>
                </TabsList>

                <TabsContent value="analysis" className="space-y-6 pt-4">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() =>
                        void runAction(() => analyzeSystemDesign(sessionId), setAnalysis)
                      }
                      disabled={isActionRunning}
                      size="sm"
                    >
                      Analyze
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        void runAction(() => getSystemDesignQuestions(sessionId), setQuestions)
                      }
                      disabled={isActionRunning}
                    >
                      Questions
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        void runAction(() => getSystemDesignSuggestions(sessionId), setSuggestions)
                      }
                      disabled={isActionRunning}
                    >
                      Suggestions
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        void runAction(() => evaluateSystemDesign(sessionId), setEvaluation)
                      }
                      disabled={isActionRunning}
                    >
                      Evaluate
                    </Button>
                  </div>

                  {analysis ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <div className="flex items-center justify-between">
                        <p className="font-medium">Analysis</p>
                        <Badge variant="secondary">{analysis.completeness_score}/100</Badge>
                      </div>
                      <Separator />
                      {analysis.best_practices_hints.length ? (
                        <div className="space-y-1">
                          <p className="text-muted-foreground text-xs font-semibold">Hints</p>
                          <ul className="list-disc space-y-1 pl-5 text-sm">
                            {analysis.best_practices_hints.map((h) => (
                              <li key={h}>{h}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {questions?.length ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <p className="font-medium">Questions</p>
                      <ul className="space-y-2 text-sm">
                        {questions.map((q) => (
                          <li key={q.id} className="space-y-1">
                            <p>• {q.text}</p>
                            {q.rationale ? (
                              <p className="text-muted-foreground text-xs">{q.rationale}</p>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {suggestions.length ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <p className="font-medium">Suggestions</p>
                      <ul className="space-y-2 text-sm">
                        {suggestions.map((s) => (
                          <li key={s.id} className="flex items-start justify-between gap-3">
                            <p className="leading-6">• {s.text}</p>
                            {s.priority ? <Badge variant="outline">{s.priority}</Badge> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {evaluation ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <p className="font-medium">Evaluation</p>
                      <div className="grid gap-2 text-sm">
                        <p>Completeness: {evaluation.completeness}/100</p>
                        <p>Scalability: {evaluation.scalability}/100</p>
                        <p>Tradeoffs: {evaluation.tradeoffs}/100</p>
                      </div>
                    </div>
                  ) : null}
                </TabsContent>

                <TabsContent value="qna" className="space-y-6 pt-4">
                  <Button
                    onClick={() =>
                      void runAction(
                        () => getSystemDesignKnowledgeDraft(sessionId),
                        setKnowledgeDraft,
                      )
                    }
                    disabled={isActionRunning}
                    size="sm"
                  >
                    Generate Draft
                  </Button>

                  {knowledgeDraft?.notes.length ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <p className="text-muted-foreground text-xs font-semibold">Notes</p>
                      <ul className="list-disc space-y-1 pl-5 text-sm">
                        {knowledgeDraft.notes.map((n) => (
                          <li key={n}>{n}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </TabsContent>

                <TabsContent value="publish" className="space-y-4 pt-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                      <div className="space-y-1">
                        <p className="text-sm leading-none font-medium">Learning topics</p>
                        <p className="text-muted-foreground text-xs">Save to learning library</p>
                      </div>
                      <Switch
                        checked={publishLearningTopics}
                        onCheckedChange={setPublishLearningTopics}
                      />
                    </div>

                    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                      <div className="space-y-1">
                        <p className="text-sm leading-none font-medium">Zettels</p>
                        <p className="text-muted-foreground text-xs">Create zettelkasten cards</p>
                      </div>
                      <Switch checked={publishZettels} onCheckedChange={setPublishZettels} />
                    </div>
                  </div>

                  <div className="grid gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="topicTitle" className="text-xs">
                        Topic title
                      </Label>
                      <Input
                        id="topicTitle"
                        placeholder="Optional"
                        value={topicTitle}
                        onChange={(e) => setTopicTitle(e.target.value)}
                        className="h-8 text-xs"
                      />
                    </div>
                  </div>

                  <Button
                    onClick={() =>
                      void runAction(
                        async () => {
                          const payload: SystemDesignPublishRequest = {
                            create_learning_topics: publishLearningTopics,
                            create_zettels: publishZettels,
                            create_interview_prep_items: false,
                            topic_title: topicTitle.trim() || null,
                            topic_tags: [],
                            zettel_tags: [],
                          };
                          return publishSystemDesignSession(sessionId, payload);
                        },
                        (result) => {
                          setPublishResult(result);
                          setSession(result.session);
                        },
                      )
                    }
                    disabled={isActionRunning}
                    size="sm"
                  >
                    Publish
                  </Button>

                  {publishResult ? (
                    <div className="space-y-2 rounded-lg border p-4 text-sm">
                      <p className="font-medium">Published</p>
                      <p>Topics: {publishResult.artifacts.learning_topic_ids.length}</p>
                      <p>Zettels: {publishResult.artifacts.zettel_card_ids.length}</p>
                    </div>
                  ) : null}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
