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
} from "@/lib/api/system-design";
import type {
  DiagramAnalysis,
  DiagramEvaluation,
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

import { ExcalidrawCanvas } from "@/components/system-design/excalidraw-canvas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  const [autosaveState, setAutosaveState] = useState<AutosaveState>("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);

  const autosaveTimerRef = useRef<number | null>(null);
  const latestDiagramRef = useRef<ExcalidrawData | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);

  const [prompt, setPrompt] = useState<DesignPrompt | null>(null);
  const [analysis, setAnalysis] = useState<DiagramAnalysis | null>(null);
  const [questions, setQuestions] = useState<Array<{ id: string; text: string; rationale?: string | null }> | null>(
    null,
  );
  const [suggestions, setSuggestions] = useState<Array<{ id: string; text: string; priority?: string }>>(
    [],
  );
  const [evaluation, setEvaluation] = useState<DiagramEvaluation | null>(null);
  const [knowledgeDraft, setKnowledgeDraft] = useState<SystemDesignKnowledgeDraft | null>(null);
  const [publishResult, setPublishResult] = useState<SystemDesignPublishResponse | null>(null);

  const [isActionRunning, setIsActionRunning] = useState(false);

  const [publishLearningTopics, setPublishLearningTopics] = useState(true);
  const [publishZettels, setPublishZettels] = useState(true);
  const [publishInterviewPrep, setPublishInterviewPrep] = useState(false);
  const [learningTopicId, setLearningTopicId] = useState<string>("");
  const [interviewPrepId, setInterviewPrepId] = useState<string>("");
  const [topicTitle, setTopicTitle] = useState<string>("");
  const [topicTags, setTopicTags] = useState<string>("");
  const [zettelTags, setZettelTags] = useState<string>("");

  const [scaleInput, setScaleInput] = useState<ScaleEstimateRequest>({
    qps: 1000,
    avg_request_kb: 5,
    avg_response_kb: 20,
    write_percentage: 20,
    storage_per_write_kb: 2,
    retention_days: 30,
    replication_factor: 3,
  });
  const [scaleOutput, setScaleOutput] = useState<ScaleEstimateResponse | null>(null);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setActionError(null);
      try {
        const next = await getSystemDesignSession(sessionId);
        setSession(next);
        setLastSavedAt(next.updated_at);
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
    };
  }, []);

  const shareUrl = useMemo(
    () => (session ? toShareUrl(session.share_id) : null),
    [session],
  );

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
      void flushAutosave().catch(() => {});
    }, 1200);
  }

  async function withFreshDiagram<T>(fn: () => Promise<T>): Promise<T> {
    setActionError(null);
    await flushAutosave();
    return fn();
  }

  async function runAction<T>(fn: () => Promise<T>, onSuccess: (data: T) => void) {
    setIsActionRunning(true);
    setActionError(null);
    try {
      const data = await withFreshDiagram(fn);
      onSuccess(data);
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
    <div className="grid h-full grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[1fr_420px]">
      <div className="flex min-h-0 flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight">
              {session.title ?? "System Design Session"}
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary">id: {session.id}</Badge>
              <Badge variant="outline">share: {session.share_id}</Badge>
              <span className="text-muted-foreground">
                autosave:{" "}
                <span className="font-mono">
                  {autosaveState}
                  {lastSavedAt ? ` • ${new Date(lastSavedAt).toLocaleString()}` : ""}
                </span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {shareUrl ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => void copyToClipboard(shareUrl)}
                >
                  Copy share link
                </Button>
                <Button asChild variant="secondary">
                  <Link href={shareUrl}>Open share view</Link>
                </Button>
              </>
            ) : null}
            <Button asChild variant="ghost">
              <Link href="/system-design">Exit</Link>
            </Button>
          </div>
        </div>

        <Textarea
          value={session.problem_statement}
          readOnly
          rows={3}
          className="resize-none"
        />

        <div className="min-h-0 flex-1">
          <ExcalidrawCanvas
            initialDiagram={session.diagram}
            onDiagramChange={queueAutosave}
          />
        </div>
      </div>

      <div className="min-h-0">
        <Card className="flex h-full flex-col">
          <CardHeader className="space-y-2">
            <CardTitle className="flex items-center justify-between">
              <span>Coach</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void flushAutosave()}
                disabled={autosaveState === "saving"}
              >
                Save now
              </Button>
            </CardTitle>
            {actionError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                {actionError}
              </div>
            ) : null}
          </CardHeader>

          <CardContent className="min-h-0 flex-1 overflow-auto">
            <Tabs defaultValue="prompt">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="prompt">Prompt</TabsTrigger>
                <TabsTrigger value="analysis">Analyze</TabsTrigger>
                <TabsTrigger value="qna">Q&A</TabsTrigger>
                <TabsTrigger value="publish">Publish</TabsTrigger>
              </TabsList>

              <TabsContent value="prompt" className="space-y-4 pt-4">
                <Button
                  onClick={() =>
                    void runAction(() => getSystemDesignPrompt(sessionId), setPrompt)
                  }
                  disabled={isActionRunning}
                >
                  Generate interviewer prompt
                </Button>
                {prompt ? (
                  <div className="space-y-3 rounded-lg border p-4">
                    <p className="font-medium">{prompt.problem}</p>
                    {prompt.target_scale ? (
                      <p className="text-xs text-muted-foreground">
                        Target scale: {prompt.target_scale}
                      </p>
                    ) : null}
                    {prompt.constraints.length ? (
                      <ul className="list-disc space-y-1 pl-5 text-sm">
                        {prompt.constraints.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </TabsContent>

              <TabsContent value="analysis" className="space-y-6 pt-4">
                <div className="flex flex-wrap gap-2">
                  <Button
                    onClick={() =>
                      void runAction(() => analyzeSystemDesign(sessionId), setAnalysis)
                    }
                    disabled={isActionRunning}
                  >
                    Analyze
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      void runAction(() => getSystemDesignQuestions(sessionId), setQuestions)
                    }
                    disabled={isActionRunning}
                  >
                    Probing questions
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      void runAction(() => getSystemDesignSuggestions(sessionId), setSuggestions)
                    }
                    disabled={isActionRunning}
                  >
                    Suggestions
                  </Button>
                  <Button
                    variant="secondary"
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
                    {analysis.bottlenecks.length ? (
                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-muted-foreground">Bottlenecks</p>
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {analysis.bottlenecks.map((b) => (
                            <li key={b}>{b}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {questions?.length ? (
                  <div className="space-y-2 rounded-lg border p-4">
                    <p className="font-medium">Probing questions</p>
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
                    <div className="grid gap-2 sm:grid-cols-2 text-sm">
                      <p>Completeness: {evaluation.completeness}/100</p>
                      <p>Scalability: {evaluation.scalability}/100</p>
                      <p>Tradeoffs: {evaluation.tradeoffs}/100</p>
                      <p>Communication: {evaluation.communication}/100</p>
                      <p>Technical depth: {evaluation.technical_depth}/100</p>
                    </div>
                    {evaluation.notes.length ? (
                      <>
                        <Separator />
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {evaluation.notes.map((n) => (
                            <li key={n}>{n}</li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </TabsContent>

              <TabsContent value="qna" className="space-y-6 pt-4">
                <Button
                  onClick={() =>
                    void runAction(() => getSystemDesignKnowledgeDraft(sessionId), setKnowledgeDraft)
                  }
                  disabled={isActionRunning}
                >
                  Generate knowledge draft
                </Button>

                {knowledgeDraft ? (
                  <div className="space-y-4 rounded-lg border p-4">
                    {knowledgeDraft.notes.length ? (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground">Notes</p>
                        <ul className="list-disc space-y-1 pl-5 text-sm">
                          {knowledgeDraft.notes.map((n) => (
                            <li key={n}>{n}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {knowledgeDraft.topics.length ? (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground">Topics</p>
                        <ul className="space-y-2 text-sm">
                          {knowledgeDraft.topics.map((t) => (
                            <li key={t.title} className="rounded-md border p-3">
                              <p className="font-medium">{t.title}</p>
                              {t.description ? (
                                <p className="text-xs text-muted-foreground">{t.description}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {knowledgeDraft.interview_prep?.likely_questions?.length ? (
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground">Likely questions</p>
                        <ul className="space-y-2 text-sm">
                          {knowledgeDraft.interview_prep.likely_questions.map((q) => (
                            <li key={q.question} className="rounded-md border p-3">
                              <p className="font-medium">{q.question}</p>
                              <p className="text-xs text-muted-foreground">{q.suggested_answer}</p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <Separator />

                <div className="space-y-3">
                  <p className="text-sm font-medium">Scale estimate</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="qps">QPS</Label>
                      <Input
                        id="qps"
                        type="number"
                        value={scaleInput.qps}
                        onChange={(e) =>
                          setScaleInput((prev) => ({ ...prev, qps: Number(e.target.value) }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="writePct">Write %</Label>
                      <Input
                        id="writePct"
                        type="number"
                        value={scaleInput.write_percentage ?? 20}
                        onChange={(e) =>
                          setScaleInput((prev) => ({
                            ...prev,
                            write_percentage: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="reqKb">Avg request (KB)</Label>
                      <Input
                        id="reqKb"
                        type="number"
                        value={scaleInput.avg_request_kb}
                        onChange={(e) =>
                          setScaleInput((prev) => ({
                            ...prev,
                            avg_request_kb: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="resKb">Avg response (KB)</Label>
                      <Input
                        id="resKb"
                        type="number"
                        value={scaleInput.avg_response_kb}
                        onChange={(e) =>
                          setScaleInput((prev) => ({
                            ...prev,
                            avg_response_kb: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    onClick={() =>
                      void runAction(() => scaleEstimate(scaleInput), setScaleOutput)
                    }
                    disabled={isActionRunning}
                  >
                    Estimate scale
                  </Button>

                  {scaleOutput ? (
                    <div className="rounded-lg border p-4 text-sm space-y-1">
                      <p>Inbound: {scaleOutput.inbound_mbps.toFixed(2)} Mbps</p>
                      <p>Outbound: {scaleOutput.outbound_mbps.toFixed(2)} Mbps</p>
                      <p>Writes/day: {scaleOutput.writes_per_day.toLocaleString()}</p>
                      <p>Storage/day: {scaleOutput.storage_gb_per_day.toFixed(2)} GB</p>
                      <p>Retained: {scaleOutput.retained_storage_gb.toFixed(2)} GB</p>
                    </div>
                  ) : null}
                </div>
              </TabsContent>

              <TabsContent value="publish" className="space-y-4 pt-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">Create learning topics</p>
                      <p className="text-xs text-muted-foreground">
                        Saves topics/resources in the learning library.
                      </p>
                    </div>
                    <Switch checked={publishLearningTopics} onCheckedChange={setPublishLearningTopics} />
                  </div>

                  <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">Create zettels</p>
                      <p className="text-xs text-muted-foreground">
                        Converts insights into zettelkasten cards.
                      </p>
                    </div>
                    <Switch checked={publishZettels} onCheckedChange={setPublishZettels} />
                  </div>

                  <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium leading-none">Update interview prep</p>
                      <p className="text-xs text-muted-foreground">
                        Appends likely questions/technical topics to an existing prep record.
                      </p>
                    </div>
                    <Switch checked={publishInterviewPrep} onCheckedChange={setPublishInterviewPrep} />
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="learningTopicId">Learning topic ID (optional)</Label>
                    <Input
                      id="learningTopicId"
                      placeholder="e.g. 12"
                      value={learningTopicId}
                      onChange={(e) => setLearningTopicId(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="topicTitle">Topic title override (optional)</Label>
                    <Input
                      id="topicTitle"
                      placeholder="Defaults to session title/problem."
                      value={topicTitle}
                      onChange={(e) => setTopicTitle(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="topicTags">Topic tags (comma-separated)</Label>
                    <Input
                      id="topicTags"
                      placeholder="e.g. system-design, caching"
                      value={topicTags}
                      onChange={(e) => setTopicTags(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="zettelTags">Zettel tags (comma-separated)</Label>
                    <Input
                      id="zettelTags"
                      placeholder="e.g. interviews, distributed-systems"
                      value={zettelTags}
                      onChange={(e) => setZettelTags(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="interviewPrepId">Interview prep ID (optional)</Label>
                    <Input
                      id="interviewPrepId"
                      placeholder="Required if 'Update interview prep' is enabled."
                      value={interviewPrepId}
                      onChange={(e) => setInterviewPrepId(e.target.value)}
                    />
                  </div>
                </div>

                <Button
                  onClick={() =>
                    void runAction(async () => {
                      const payload: SystemDesignPublishRequest = {
                        create_learning_topics: publishLearningTopics,
                        create_zettels: publishZettels,
                        create_interview_prep_items: publishInterviewPrep,
                        topic_title: topicTitle.trim() || null,
                        topic_tags: topicTags
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                        zettel_tags: zettelTags
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                      };

                      const ltId = Number(learningTopicId);
                      if (!Number.isNaN(ltId) && learningTopicId.trim().length) {
                        payload.learning_topic_id = ltId;
                      }

                      if (interviewPrepId.trim().length) payload.interview_prep_id = interviewPrepId.trim();

                      return publishSystemDesignSession(sessionId, payload);
                    }, setPublishResult)
                  }
                  disabled={isActionRunning}
                >
                  Publish artifacts
                </Button>

                {publishResult ? (
                  <div className="space-y-2 rounded-lg border p-4 text-sm">
                    <p className="font-medium">Published</p>
                    <p>
                      Learning topics: {publishResult.artifacts.learning_topic_ids.length}
                    </p>
                    <p>
                      Learning resources: {publishResult.artifacts.learning_resource_ids.length}
                    </p>
                    <p>Zettels: {publishResult.artifacts.zettel_card_ids.length}</p>
                    {publishResult.artifacts.interview_prep_id ? (
                      <p>Interview prep: {publishResult.artifacts.interview_prep_id}</p>
                    ) : null}
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
