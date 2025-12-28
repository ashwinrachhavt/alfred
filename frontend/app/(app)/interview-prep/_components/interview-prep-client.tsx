"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { processUnifiedInterview } from "@/lib/api/interviews-unified";
import type { UnifiedInterviewOperation } from "@/lib/api/types/interviews-unified";
import type {
  EnqueueUnifiedInterviewTaskResponse,
  UnifiedInterviewRequest,
  UnifiedInterviewResponse,
} from "@/lib/api/types/interviews-unified";
import type { TaskStatusResponse } from "@/lib/api/types/tasks";

import { ApiError } from "@/lib/api/client";
import { getTaskStatus } from "@/lib/api/interviews-unified";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type PersistedInterviewPrepState = {
  company: string;
  role: string;
  candidateBackground: string;
  operation: UnifiedInterviewOperation;
  maxSources: number;
  maxQuestions: number;
  useFirecrawl: boolean;
  includeDeepResearch: boolean;
  targetLengthWords: number;
  practiceSessionId: string;
};

const STORAGE_KEY = "alfred:interview-prep:v1";

function parsePersistedState(raw: string | null): PersistedInterviewPrepState | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PersistedInterviewPrepState;
  } catch {
    return null;
  }
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function isQueuedResponse(
  response: UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse,
): response is EnqueueUnifiedInterviewTaskResponse {
  return "task_id" in response;
}

export function InterviewPrepClient() {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("Software Engineer");
  const [candidateBackground, setCandidateBackground] = useState("");

  const [operation, setOperation] = useState<UnifiedInterviewOperation>("collect_questions");

  const [maxSources, setMaxSources] = useState(12);
  const [maxQuestions, setMaxQuestions] = useState(60);
  const [useFirecrawl, setUseFirecrawl] = useState(true);

  const [includeDeepResearch, setIncludeDeepResearch] = useState(true);
  const [targetLengthWords, setTargetLengthWords] = useState(1000);

  const [practiceSessionId, setPracticeSessionId] = useState("");
  const [candidateResponse, setCandidateResponse] = useState("");

  const [runInBackground, setRunInBackground] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UnifiedInterviewResponse | null>(null);

  const [queued, setQueued] = useState<EnqueueUnifiedInterviewTaskResponse | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);

  const pollerRef = useRef<number | null>(null);

  useEffect(() => {
    const persisted = parsePersistedState(window.localStorage.getItem(STORAGE_KEY));
    if (!persisted) return;
    setCompany(persisted.company);
    setRole(persisted.role);
    setCandidateBackground(persisted.candidateBackground);
    setOperation(persisted.operation);
    setMaxSources(persisted.maxSources);
    setMaxQuestions(persisted.maxQuestions);
    setUseFirecrawl(persisted.useFirecrawl);
    setIncludeDeepResearch(persisted.includeDeepResearch);
    setTargetLengthWords(persisted.targetLengthWords);
    setPracticeSessionId(persisted.practiceSessionId);
  }, []);

  useEffect(() => {
    const nextState: PersistedInterviewPrepState = {
      company,
      role,
      candidateBackground,
      operation,
      maxSources,
      maxQuestions,
      useFirecrawl,
      includeDeepResearch,
      targetLengthWords,
      practiceSessionId,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
  }, [
    company,
    role,
    candidateBackground,
    operation,
    maxSources,
    maxQuestions,
    useFirecrawl,
    includeDeepResearch,
    targetLengthWords,
    practiceSessionId,
  ]);

  useEffect(() => {
    return () => {
      if (pollerRef.current) window.clearInterval(pollerRef.current);
    };
  }, []);

  const canRun = useMemo(() => company.trim().length > 0, [company]);

  async function pollStatus(statusUrl: string) {
    const status = await getTaskStatus<TaskStatusResponse>(statusUrl);
    setTaskStatus(status);
    if (!status.ready) return;

    if (pollerRef.current) window.clearInterval(pollerRef.current);
    pollerRef.current = null;

    if (status.successful && status.result && typeof status.result === "object") {
      setResult(status.result as UnifiedInterviewResponse);
      const maybeSessionId = (status.result as { session_id?: unknown }).session_id;
      if (typeof maybeSessionId === "string") setPracticeSessionId(maybeSessionId);
    } else if (status.failed) {
      setError(status.error ?? "Background task failed.");
    }
    setIsRunning(false);
  }

  async function onRun() {
    setError(null);
    setResult(null);
    setQueued(null);
    setTaskStatus(null);
    setIsRunning(true);

    const payload: UnifiedInterviewRequest = {
      operation,
      company: company.trim(),
      role: (role || "Software Engineer").trim(),
      candidate_background: candidateBackground.trim() || null,
    };

    if (operation === "collect_questions") {
      payload.max_sources = maxSources;
      payload.max_questions = maxQuestions;
      payload.use_firecrawl = useFirecrawl;
    }

    if (operation === "deep_research") {
      payload.include_deep_research = includeDeepResearch;
      payload.target_length_words = targetLengthWords;
    }

    if (operation === "practice_session") {
      payload.session_id = practiceSessionId.trim() || null;
      payload.candidate_response = candidateResponse.trim() || null;
    }

    try {
      const response = await processUnifiedInterview(payload, { background: runInBackground });
      if (isQueuedResponse(response)) {
        setQueued(response);
        pollerRef.current = window.setInterval(() => {
          void pollStatus(response.status_url);
        }, 2000);
        return;
      }

      setResult(response);
      if (response.session_id) setPracticeSessionId(response.session_id);
    } catch (err) {
      setError(formatErrorMessage(err));
    } finally {
      if (!runInBackground) setIsRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Interview Prep</h1>
        <p className="text-muted-foreground">
          Generate targeted questions, research the company, and run practice sessions.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Inputs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="company">Company</Label>
              <Input
                id="company"
                placeholder="e.g. Stripe"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                placeholder="e.g. Software Engineer"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="candidateBackground">Your context (optional)</Label>
            <Textarea
              id="candidateBackground"
              placeholder="A few bullets about your background/projects so Alfred can tailor guidance."
              value={candidateBackground}
              onChange={(e) => setCandidateBackground(e.target.value)}
              rows={4}
            />
          </div>

          <Tabs value={operation} onValueChange={(v) => setOperation(v as UnifiedInterviewOperation)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="collect_questions">Collect Questions</TabsTrigger>
              <TabsTrigger value="deep_research">Deep Research</TabsTrigger>
              <TabsTrigger value="practice_session">Practice Session</TabsTrigger>
            </TabsList>

            <TabsContent value="collect_questions" className="pt-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="maxSources">Max sources</Label>
                  <Input
                    id="maxSources"
                    type="number"
                    min={1}
                    max={30}
                    value={maxSources}
                    onChange={(e) => setMaxSources(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="maxQuestions">Max questions</Label>
                  <Input
                    id="maxQuestions"
                    type="number"
                    min={1}
                    max={200}
                    value={maxQuestions}
                    onChange={(e) => setMaxQuestions(Number(e.target.value))}
                  />
                </div>
                <div className="flex items-end justify-between gap-4 rounded-lg border p-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">Use Firecrawl</p>
                    <p className="text-xs text-muted-foreground">
                      Adds Firecrawl search alongside SearxNG/DDG.
                    </p>
                  </div>
                  <Switch checked={useFirecrawl} onCheckedChange={setUseFirecrawl} />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="deep_research" className="pt-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="flex items-end justify-between gap-4 rounded-lg border p-3 sm:col-span-1">
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">Include deep research</p>
                    <p className="text-xs text-muted-foreground">
                      Include a company deep research section.
                    </p>
                  </div>
                  <Switch checked={includeDeepResearch} onCheckedChange={setIncludeDeepResearch} />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="targetLengthWords">Target length (words)</Label>
                  <Input
                    id="targetLengthWords"
                    type="number"
                    min={300}
                    max={3000}
                    value={targetLengthWords}
                    onChange={(e) => setTargetLengthWords(Number(e.target.value))}
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="practice_session" className="pt-4 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="practiceSessionId">Session ID (optional)</Label>
                  <Input
                    id="practiceSessionId"
                    placeholder="Leave empty to start a new practice session."
                    value={practiceSessionId}
                    onChange={(e) => setPracticeSessionId(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="candidateResponse">Your response (optional)</Label>
                <Textarea
                  id="candidateResponse"
                  placeholder="Paste your answer here to get feedback and follow-up questions."
                  value={candidateResponse}
                  onChange={(e) => setCandidateResponse(e.target.value)}
                  rows={7}
                />
              </div>
            </TabsContent>
          </Tabs>

          <Separator />

          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Switch checked={runInBackground} onCheckedChange={setRunInBackground} />
              <div className="space-y-0.5">
                <p className="text-sm font-medium leading-none">Run in background</p>
                <p className="text-xs text-muted-foreground">
                  Returns immediately and updates when the task completes.
                </p>
              </div>
            </div>
            <Button onClick={onRun} disabled={!canRun || isRunning}>
              {isRunning ? "Running..." : "Run"}
            </Button>
          </div>

          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}
        </CardContent>

        {queued ? (
          <CardFooter className="flex flex-col items-start gap-2">
            <p className="text-sm">
              Background task queued: <span className="font-mono">{queued.task_id}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Status URL: <span className="font-mono">{queued.status_url}</span>
            </p>
            {taskStatus ? (
              <p className="text-xs text-muted-foreground">
                Status: <span className="font-mono">{taskStatus.status}</span>
              </p>
            ) : null}
          </CardFooter>
        ) : null}
      </Card>

      {result ? (
        <Card>
          <CardHeader className="space-y-2">
            <CardTitle>Result</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{result.operation}</Badge>
              {typeof result.sources_scraped === "number" ? (
                <Badge variant="outline">{result.sources_scraped} sources</Badge>
              ) : null}
              {result.session_id ? (
                <Badge variant="outline">session: {result.session_id}</Badge>
              ) : null}
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            {result.operation === "collect_questions" && result.questions?.length ? (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground">Questions</h3>
                <div className="space-y-3">
                  {result.questions.map((q) => (
                    <div key={q.question} className="rounded-lg border p-4">
                      <div className="flex flex-col gap-2">
                        <p className="font-medium leading-6">{q.question}</p>
                        {q.categories?.length ? (
                          <div className="flex flex-wrap gap-2">
                            {q.categories.map((c) => (
                              <Badge key={c} variant="secondary">
                                {c}
                              </Badge>
                            ))}
                          </div>
                        ) : null}
                        {q.solution?.approach ? (
                          <div className="text-sm text-muted-foreground">
                            <span className="font-medium text-foreground">Approach:</span>{" "}
                            {q.solution.approach}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {result.operation === "deep_research" ? (
              <div className="space-y-6">
                {result.key_insights?.length ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-muted-foreground">Key insights</h3>
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {result.key_insights.map((insight) => (
                        <li key={insight}>{insight}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {result.research_report ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-muted-foreground">Report</h3>
                    <pre className="max-h-[520px] overflow-auto rounded-lg border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
                      {result.research_report}
                    </pre>
                  </div>
                ) : null}
              </div>
            ) : null}

            {result.operation === "practice_session" ? (
              <div className="space-y-6">
                {result.interviewer_response ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-muted-foreground">
                      Interviewer response
                    </h3>
                    <pre className="max-h-[520px] overflow-auto rounded-lg border bg-muted/30 p-4 text-sm whitespace-pre-wrap">
                      {result.interviewer_response}
                    </pre>
                  </div>
                ) : null}
                {result.feedback ? (
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-muted-foreground">Feedback</h3>
                    <pre className="max-h-[520px] overflow-auto rounded-lg border bg-muted/30 p-4 text-sm">
                      {JSON.stringify(result.feedback, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
