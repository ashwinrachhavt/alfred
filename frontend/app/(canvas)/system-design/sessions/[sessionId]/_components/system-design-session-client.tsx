"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  analyzeSystemDesign,
  autosaveSystemDesignDiagram,
  evaluateSystemDesign,
  getSystemDesignKnowledgeDraft,
  getSystemDesignPrompt,
  getSystemDesignQuestions,
  getSystemDesignSession,
  getSystemDesignSuggestions,
  publishSystemDesignSession,
  scaleEstimate,
  updateSystemDesignNotes,
  updateSystemDesignSession,
} from "@/lib/api/system-design";
import type {
  DiagramAnalysis,
  DiagramEvaluation,
  DiagramQuestion,
  DiagramSuggestion,
  DesignPrompt,
  ExcalidrawData,
  ScaleEstimateRequest,
  ScaleEstimateResponse,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishRequest,
  SystemDesignPublishResponse,
  SystemDesignSession,
} from "@/lib/api/types/system-design";

import { ApiError } from "@/lib/api/client";

import { ExcalidrawCanvas, type ExcalidrawCanvasHandle } from "@/components/system-design/excalidraw-canvas";
import { SystemDesignNotesEditor, type SystemDesignNotesEditorHandle } from "@/components/system-design/system-design-notes-editor";
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
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type AutosaveState = "idle" | "dirty" | "saving" | "saved" | "error";

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function toShareUrl(shareId: string): string {
  return `/system-design/share/${shareId}`;
}

export function SystemDesignSessionClient({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<SystemDesignSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionRunning, setIsActionRunning] = useState(false);

  const [prompt, setPrompt] = useState<DesignPrompt | null>(null);
  const [analysis, setAnalysis] = useState<DiagramAnalysis | null>(null);
  const [questions, setQuestions] = useState<DiagramQuestion[] | null>(null);
  const [suggestions, setSuggestions] = useState<DiagramSuggestion[]>([]);
  const [evaluation, setEvaluation] = useState<DiagramEvaluation | null>(null);
  const [knowledgeDraft, setKnowledgeDraft] = useState<SystemDesignKnowledgeDraft | null>(null);

  const [scaleInput, setScaleInput] = useState<ScaleEstimateRequest>({
    qps: 1000,
    avg_request_kb: 1,
    avg_response_kb: 10,
    write_percentage: 20,
  });
  const [scaleOutput, setScaleOutput] = useState<ScaleEstimateResponse | null>(null);

  const [problemStatement, setProblemStatement] = useState("");

  const [publishLearningTopics, setPublishLearningTopics] = useState(true);
  const [publishZettels, setPublishZettels] = useState(true);
  const [publishInterviewPrep, setPublishInterviewPrep] = useState(false);

  const [learningTopicId, setLearningTopicId] = useState("");
  const [topicTitle, setTopicTitle] = useState("");
  const [topicTags, setTopicTags] = useState("");
  const [zettelTags, setZettelTags] = useState("");
  const [interviewPrepId, setInterviewPrepId] = useState("");
  const [publishResult, setPublishResult] = useState<SystemDesignPublishResponse | null>(null);

  const canvasRef = useRef<ExcalidrawCanvasHandle | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);

  const [autosaveState, setAutosaveState] = useState<AutosaveState>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  const autosaveTimerRef = useRef<number | null>(null);
  const latestDiagramRef = useRef<ExcalidrawData | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);

  const [notesMarkdown, setNotesMarkdown] = useState<string>("");
  const [notesSaveState, setNotesSaveState] = useState<AutosaveState>("idle");
  const notesTimerRef = useRef<number | null>(null);
  const latestNotesRef = useRef<string>("");
  const notesEditorRef = useRef<SystemDesignNotesEditorHandle | null>(null);
  const notesInitializedRef = useRef(false);

  // Panel visibility state
  const [showDiagram, setShowDiagram] = useState(true); // Default to showing diagram
  const [showEditor, setShowEditor] = useState(true);
  const [showCoach, setShowCoach] = useState(false);

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
      setPrompt(null);
      setAnalysis(null);
      setQuestions(null);
      setSuggestions([]);
      setEvaluation(null);
      setKnowledgeDraft(null);
      setScaleOutput(null);
      setPublishResult(null);
      notesInitializedRef.current = false;
      latestNotesRef.current = "";
      setNotesMarkdown("");
      setNotesSaveState("idle");
      try {
        const next = await getSystemDesignSession(sessionId);
        setSession(next);
        setProblemStatement(next.problem_statement);
        setLastSavedAt(next.updated_at);
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

  const shareUrl = useMemo(
    () => (session ? toShareUrl(session.share_id) : null),
    [session],
  );

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
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleDiagramResize as any);
    document.addEventListener('mouseup', stopDiagramResize);
  };

  const stopDiagramResize = () => {
    isDraggingDiagram.current = false;
    setIsResizing(false);
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', handleDiagramResize as any);
    document.removeEventListener('mouseup', stopDiagramResize);
  };

  const startCoachResize = () => {
    isDraggingCoach.current = true;
    setIsResizing(true);
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleCoachResize as any);
    document.addEventListener('mouseup', stopCoachResize);
  };

  const stopCoachResize = () => {
    isDraggingCoach.current = false;
    setIsResizing(false);
    document.body.style.userSelect = '';
    document.removeEventListener('mousemove', handleCoachResize as any);
    document.removeEventListener('mouseup', stopCoachResize);
  };

  async function flushAutosave() {
    if (!latestDiagramRef.current) return;
    if (autosaveTimerRef.current) {
      window.clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    setAutosaveState("saving");
    try {
      const next = await autosaveSystemDesignDiagram(sessionId, {
        diagram: latestDiagramRef.current,
        label: null,
      });
      setSession((prev) => (prev ? { ...prev, updated_at: next.updated_at } : prev));
      setAutosaveState("saved");
      setLastSavedAt(next.updated_at);
    } catch (err) {
      setAutosaveState("error");
      throw err;
    }
  }

  function queueAutosave(diagram: ExcalidrawData) {
    latestDiagramRef.current = diagram;
    setAutosaveState("dirty");

    if (autosaveTimerRef.current) window.clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = window.setTimeout(() => {
      void flushAutosave().catch(() => { });
    }, 1200);
  }

  async function flushNotesSave() {
    const notes = latestNotesRef.current;
    if (notesTimerRef.current) {
      window.clearTimeout(notesTimerRef.current);
      notesTimerRef.current = null;
    }

    setNotesSaveState("saving");
    try {
      const next = await updateSystemDesignNotes(sessionId, { notes_markdown: notes });
      setSession((prev) => (prev ? { ...prev, updated_at: next.updated_at } : prev));
      setNotesSaveState("saved");
      setLastSavedAt(next.updated_at);
    } catch {
      setNotesSaveState("error");
    }
  }

  function queueNotesSave(nextMarkdown: string) {
    latestNotesRef.current = nextMarkdown;
    setNotesMarkdown(nextMarkdown);
    setNotesSaveState("dirty");

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

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore; copying is optional UX sugar
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
        Loading session…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-10 space-y-4">
        <h1 className="text-2xl font-semibold">System Design Session</h1>
        <p className="text-sm text-muted-foreground">
          {actionError ?? "Session not found."}
        </p>
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
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="secondary">id: {session.id}</Badge>
            <Badge variant="outline">share: {session.share_id}</Badge>
            <span className="text-muted-foreground">
              notes: <span className="font-mono">{notesSaveState}</span>
              {lastSavedAt ? ` • ${new Date(lastSavedAt).toLocaleString()}` : ""}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDiagramGenerationError(null);
              setIsAiDialogOpen(true);
            }}
            disabled={!showDiagram}
            title={!showDiagram ? "Enable Diagram to generate into the canvas." : undefined}
          >
            Generate Diagram
          </Button>
          <Button
            variant={showDiagram ? "default" : "outline"}
            size="sm"
            onClick={() => setShowDiagram(!showDiagram)}
          >
            {showDiagram ? "Hide" : "Show"} Diagram
          </Button>
          <Button
            variant={showEditor ? "default" : "outline"}
            size="sm"
            onClick={() => setShowEditor(!showEditor)}
          >
            {showEditor ? "Hide" : "Show"} Editor
          </Button>
          <Button
            variant={showCoach ? "default" : "outline"}
            size="sm"
            onClick={() => setShowCoach(!showCoach)}
          >
            {showCoach ? "Hide" : "Show"} Coach
          </Button>
          <Separator orientation="vertical" className="h-6" />
          {shareUrl ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void copyToClipboard(shareUrl)}
              >
                Share
              </Button>
            </>
          ) : null}
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
              <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
                {diagramGenerationError}
              </div>
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
          <div className="relative flex min-h-0 flex-col overflow-hidden rounded-xl border bg-background">
            {/* Overlay during resize to prevent event trapping */}
            {isResizing && <div className="absolute inset-0 z-50 bg-transparent" />}

            <div className="min-h-0 flex-1 p-0">
              <ExcalidrawCanvas
                ref={canvasRef}
                initialDiagram={session.diagram}
                onDiagramChange={queueAutosave}
                framed={false}
                viewportScale={1}
              />
            </div>
          </div>
        )}

        {/* Resize Handle for Diagram */}
        {showDiagram && showEditor && (
          <div
            className="group relative w-1 cursor-col-resize bg-border hover:bg-primary transition-colors"
            onMouseDown={startDiagramResize}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 z-10" />
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary p-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="h-8 w-0.5 bg-primary-foreground" />
            </div>
          </div>
        )}

        {/* Editor Panel - Collapsible */}
        {showEditor && (
          <div className="flex min-h-0 flex-col gap-3">
            <div className="flex flex-col gap-2 rounded-xl border bg-background px-4 py-3">
              <span className="text-sm font-medium">Problem Statement</span>
              <Textarea
                value={problemStatement}
                onChange={(e) => {
                  setProblemStatement(e.target.value);
                }}
                onBlur={() => {
                  if (problemStatement !== session.problem_statement) {
                    void runAction(() => updateSystemDesignSession(sessionId, { problem_statement: problemStatement }), (updated) => {
                      setSession(updated);
                      setLastSavedAt(updated.updated_at);
                    });
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
            className="group relative w-1 cursor-col-resize bg-border hover:bg-primary transition-colors"
            onMouseDown={startCoachResize}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 z-10" />
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary p-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <div className="h-8 w-0.5 bg-primary-foreground" />
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
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  {actionError}
                </div>
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
                          <p className="text-xs font-semibold text-muted-foreground">Hints</p>
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
                              <p className="text-xs text-muted-foreground">{q.rationale}</p>
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
                      void runAction(() => getSystemDesignKnowledgeDraft(sessionId), setKnowledgeDraft)
                    }
                    disabled={isActionRunning}
                    size="sm"
                  >
                    Generate Draft
                  </Button>

                  {knowledgeDraft?.notes.length ? (
                    <div className="space-y-2 rounded-lg border p-4">
                      <p className="text-xs font-semibold text-muted-foreground">Notes</p>
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
                        <p className="text-sm font-medium leading-none">Learning topics</p>
                        <p className="text-xs text-muted-foreground">
                          Save to learning library
                        </p>
                      </div>
                      <Switch checked={publishLearningTopics} onCheckedChange={setPublishLearningTopics} />
                    </div>

                    <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                      <div className="space-y-1">
                        <p className="text-sm font-medium leading-none">Zettels</p>
                        <p className="text-xs text-muted-foreground">
                          Create zettelkasten cards
                        </p>
                      </div>
                      <Switch checked={publishZettels} onCheckedChange={setPublishZettels} />
                    </div>
                  </div>

                  <div className="grid gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="topicTitle" className="text-xs">Topic title</Label>
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
                      void runAction(async () => {
                        const payload: SystemDesignPublishRequest = {
                          create_learning_topics: publishLearningTopics,
                          create_zettels: publishZettels,
                          create_interview_prep_items: false,
                          topic_title: topicTitle.trim() || null,
                          topic_tags: [],
                          zettel_tags: [],
                        };
                        return publishSystemDesignSession(sessionId, payload);
                      }, (result) => {
                        setPublishResult(result);
                        setSession(result.session);
                        setLastSavedAt(result.session.updated_at);
                      })
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
