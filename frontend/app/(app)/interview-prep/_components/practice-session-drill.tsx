"use client";

import * as React from "react";
import { Copy, Pause, Play, RotateCcw, Sparkles, Timer, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { copyTextToClipboard } from "@/lib/clipboard";
import { processUnifiedInterview } from "@/lib/api/interviews-unified";
import { ApiError } from "@/lib/api/client";
import type { UnifiedInterviewResponse } from "@/lib/api/types/interviews-unified";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  loadPracticeSessionTranscript,
  savePracticeSessionTranscript,
  upsertPracticeSessionSummary,
  type PracticeMessage,
  type PracticeMessageRole,
} from "@/features/interview-prep/practice-session-store";

type PracticeSessionDrillProps = {
  company: string;
  role: string;
  candidateBackground: string;
  threadId: string;
  onThreadIdChange: (nextThreadId: string) => void;
  sessionId: string;
  onSessionIdChange: (nextSessionId: string) => void;
};

type TimerState = {
  durationSeconds: number;
  remainingSeconds: number;
  isRunning: boolean;
  autoStartOnQuestion: boolean;
};

function nowIso(): string {
  return new Date().toISOString();
}

function newMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function extractThreadIdFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): string | null {
  if (!metadata) return null;
  const value = metadata.thread_id;
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function formatTimer(valueSeconds: number): string {
  const total = Math.max(0, Math.floor(valueSeconds));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function wordCount(text: string): number {
  const normalized = text.trim();
  if (!normalized) return 0;
  return normalized.split(/\s+/).length;
}

function formatTranscriptForClipboard({
  company,
  role,
  sessionId,
  messages,
}: {
  company: string;
  role: string;
  sessionId: string;
  messages: PracticeMessage[];
}): string {
  const normalizedCompany = company.trim() || "Company";
  const normalizedRole = role.trim() || "Software Engineer";

  const lines: string[] = [];
  lines.push(`# Practice Session — ${normalizedCompany} (${normalizedRole})`);
  if (sessionId) lines.push(`Session: ${sessionId}`);
  lines.push("");

  messages.forEach((message) => {
    const speaker =
      message.role === "candidate"
        ? "You"
        : message.role === "interviewer"
          ? "Interviewer"
          : "System";
    lines.push(`## ${speaker}`);
    lines.push(message.content.trim() || "—");
    lines.push("");
  });

  return `${lines.join("\n").trim()}\n`;
}

function roleLabel(role: PracticeMessageRole): string {
  if (role === "candidate") return "You";
  if (role === "interviewer") return "Interviewer";
  return "System";
}

function messageTone(role: PracticeMessageRole): string {
  if (role === "candidate") return "bg-primary text-primary-foreground";
  if (role === "interviewer") return "bg-muted";
  return "bg-background border";
}

export function PracticeSessionDrill({
  company,
  role,
  candidateBackground,
  threadId,
  onThreadIdChange,
  sessionId,
  onSessionIdChange,
}: PracticeSessionDrillProps) {
  const [messages, setMessages] = React.useState<PracticeMessage[]>([]);
  const [answerDraft, setAnswerDraft] = React.useState("");
  const [resumeSessionId, setResumeSessionId] = React.useState("");
  const [isSending, setIsSending] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);
  const [timer, setTimer] = React.useState<TimerState>(() => ({
    durationSeconds: 180,
    remainingSeconds: 180,
    isRunning: false,
    autoStartOnQuestion: true,
  }));

  const skipLoadRef = React.useRef<string | null>(null);
  const lastInterviewerMessageIdRef = React.useRef<string | null>(null);
  const transcriptCreatedAtRef = React.useRef<string>(nowIso());
  const scrollRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      setLocalError(null);
      return;
    }

    if (skipLoadRef.current === sessionId) {
      skipLoadRef.current = null;
      return;
    }

    const stored = loadPracticeSessionTranscript(sessionId);
    if (stored) {
      transcriptCreatedAtRef.current = stored.createdAt;
      setMessages(stored.messages);
      setLocalError(null);
    } else {
      transcriptCreatedAtRef.current = nowIso();
      setMessages([]);
      setLocalError(null);
    }
  }, [sessionId]);

  React.useEffect(() => {
    if (!sessionId) return;
    const createdAt = transcriptCreatedAtRef.current;
    const updatedAt = nowIso();

    const lastInterviewerPrompt = [...messages]
      .reverse()
      .find((message) => message.role === "interviewer")?.content;

    savePracticeSessionTranscript({
      version: 1,
      sessionId,
      company: company.trim() || "Company",
      role: role.trim() || "Software Engineer",
      createdAt,
      updatedAt,
      messages: messages.slice(-200),
    });

    upsertPracticeSessionSummary({
      id: sessionId,
      company: company.trim() || "Company",
      role: role.trim() || "Software Engineer",
      createdAt,
      updatedAt,
      lastInterviewerPrompt,
    });
  }, [company, messages, role, sessionId]);

  React.useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  React.useEffect(() => {
    if (!timer.isRunning) return;
    if (timer.remainingSeconds <= 0) return;

    const handle = window.setInterval(() => {
      setTimer((prev) => {
        if (!prev.isRunning) return prev;
        const next = Math.max(0, prev.remainingSeconds - 1);
        return { ...prev, remainingSeconds: next };
      });
    }, 1000);

    return () => window.clearInterval(handle);
  }, [timer.isRunning, timer.remainingSeconds]);

  React.useEffect(() => {
    if (!timer.isRunning) return;
    if (timer.remainingSeconds !== 0) return;
    setTimer((prev) => ({ ...prev, isRunning: false }));
    toast.message("Time", { description: "Timer finished." });
  }, [timer.isRunning, timer.remainingSeconds]);

  React.useEffect(() => {
    const lastInterviewerMessage = [...messages]
      .reverse()
      .find((message) => message.role === "interviewer");

    if (!lastInterviewerMessage) return;
    if (lastInterviewerMessageIdRef.current === lastInterviewerMessage.id) return;
    lastInterviewerMessageIdRef.current = lastInterviewerMessage.id;

    setTimer((prev) => {
      if (!prev.autoStartOnQuestion) return prev;
      return {
        ...prev,
        remainingSeconds: prev.durationSeconds,
        isRunning: true,
      };
    });
  }, [messages]);

  const sessionStatusLabel = sessionId ? `Session ${sessionId}` : "Not started";
  const isCompanyReady = company.trim().length > 0;

  async function copySessionId() {
    if (!sessionId) return;
    try {
      await copyTextToClipboard(sessionId);
      toast.success("Copied session id");
    } catch (err) {
      toast.error("Could not copy", { description: formatErrorMessage(err) });
    }
  }

  async function copyTranscript() {
    try {
      await copyTextToClipboard(
        formatTranscriptForClipboard({ company, role, sessionId, messages }),
      );
      toast.success("Copied transcript");
    } catch (err) {
      toast.error("Could not copy", { description: formatErrorMessage(err) });
    }
  }

  function resetSession() {
    onSessionIdChange("");
    setResumeSessionId("");
    setMessages([]);
    setAnswerDraft("");
    setLocalError(null);
    transcriptCreatedAtRef.current = nowIso();
    lastInterviewerMessageIdRef.current = null;
    setTimer((prev) => ({
      ...prev,
      remainingSeconds: prev.durationSeconds,
      isRunning: false,
    }));
  }

  function appendMessage(role: PracticeMessageRole, content: string): PracticeMessage {
    const next: PracticeMessage = {
      id: newMessageId(),
      role,
      content,
      createdAt: nowIso(),
    };
    setMessages((prev) => [...prev, next]);
    return next;
  }

  function coercePracticeSessionResponse(
    response: UnifiedInterviewResponse,
    submittedAnswer: string,
  ): { nextSessionId: string; nextQuestion: string | null } {
    const nextSessionId = response.session_id?.trim();
    if (!nextSessionId) {
      throw new Error("No session id returned. Please try again.");
    }

    const interviewerResponse = response.interviewer_response?.trim() || null;
    // Ensure we always store the user's answer, even when the server returns no question.
    if (submittedAnswer.trim()) {
      appendMessage("candidate", submittedAnswer.trim());
    }

    if (interviewerResponse) {
      appendMessage("interviewer", interviewerResponse);
    } else {
      appendMessage(
        "system",
        "No next question returned. Try answering again or reset the session.",
      );
    }

    const errors = (response.metadata?.errors as unknown) ?? null;
    if (Array.isArray(errors) && errors.length) {
      appendMessage(
        "system",
        `Practice session warnings:\n${errors
          .filter((entry) => typeof entry === "string")
          .map((entry) => `- ${entry}`)
          .join("\n")}`,
      );
    }

    return { nextSessionId, nextQuestion: interviewerResponse };
  }

  async function sendAnswer() {
    setLocalError(null);
    const answerText = answerDraft;
    const answer = answerText.trim();
    if (!answer) return;

    if (!isCompanyReady) {
      setLocalError("Company is required to run a practice session.");
      return;
    }

    if (!sessionId) {
      transcriptCreatedAtRef.current = nowIso();
    }

    setIsSending(true);
    setAnswerDraft("");

    try {
      const normalizedThreadId = threadId.trim();
      const response = await processUnifiedInterview({
        operation: "practice_session",
        company: company.trim(),
        role: role.trim() || "Software Engineer",
        candidate_background: candidateBackground.trim() || null,
        ...(normalizedThreadId ? { thread_id: normalizedThreadId } : {}),
        session_id: sessionId.trim() || null,
        candidate_response: answer,
      });

      if ("task_id" in response) {
        throw new Error(
          "Practice sessions can’t be queued. Disable background mode and try again.",
        );
      }

      const persistedThreadId = extractThreadIdFromMetadata(
        "metadata" in response && response.metadata && typeof response.metadata === "object"
          ? (response.metadata as Record<string, unknown>)
          : null,
      );
      if (persistedThreadId) onThreadIdChange(persistedThreadId);

      const { nextSessionId } = coercePracticeSessionResponse(response, answer);
      if (nextSessionId !== sessionId) {
        skipLoadRef.current = nextSessionId;
        onSessionIdChange(nextSessionId);
      }
    } catch (err) {
      setLocalError(formatErrorMessage(err));
      toast.error("Could not send", { description: formatErrorMessage(err) });
      setAnswerDraft(answerText);
    } finally {
      setIsSending(false);
    }
  }

  async function loadSession(nextId: string) {
    const normalized = nextId.trim();
    if (!normalized) return;
    skipLoadRef.current = null;
    onSessionIdChange(normalized);
  }

  return (
    <div className="space-y-4">
      <CardHeaderLite
        title="Practice Session"
        description="A timed, chat-style drill. Start with a short intro — the interviewer will ask the first question after your first message."
        right={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={sessionId ? "secondary" : "outline"}>{sessionStatusLabel}</Badge>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Copy session id"
              disabled={!sessionId}
              onClick={() => void copySessionId()}
            >
              <Copy className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Copy transcript"
              disabled={!messages.length}
              onClick={() => void copyTranscript()}
            >
              <Copy className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Reset session"
              onClick={resetSession}
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="bg-background flex min-h-[420px] flex-col rounded-lg border">
          <div className="flex items-center justify-between gap-3 border-b p-3">
            <div className="flex items-center gap-2">
              <Sparkles className="text-muted-foreground h-4 w-4" aria-hidden="true" />
              <p className="text-sm font-medium">Drill</p>
              <Separator orientation="vertical" className="h-4" />
              <p className="text-muted-foreground text-xs">
                {messages.length ? `${messages.length} messages` : "No messages yet"}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Timer className="text-muted-foreground h-4 w-4" aria-hidden="true" />
              <span className="font-mono text-sm">{formatTimer(timer.remainingSeconds)}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={timer.isRunning ? "Pause timer" : "Start timer"}
                onClick={() =>
                  setTimer((prev) => ({
                    ...prev,
                    isRunning: prev.remainingSeconds > 0 ? !prev.isRunning : false,
                  }))
                }
              >
                {timer.isRunning ? (
                  <Pause className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Play className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Reset timer"
                onClick={() =>
                  setTimer((prev) => ({
                    ...prev,
                    remainingSeconds: prev.durationSeconds,
                    isRunning: false,
                  }))
                }
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
            {!messages.length ? (
              <EmptyState
                icon={Sparkles}
                title="Start your drill"
                description="Write a 60-second intro, press Cmd/Ctrl+Enter, and the interviewer will ask the first question."
              />
            ) : (
              messages.map((message) => (
                <div key={message.id} className="space-y-1">
                  <p className="text-muted-foreground text-xs">{roleLabel(message.role)}</p>
                  <div className={`rounded-lg p-3 text-sm ${messageTone(message.role)}`}>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="space-y-2 border-t p-3">
            {localError ? (
              <Alert variant="destructive" className="px-3 py-2">
                <AlertDescription className="text-destructive">{localError}</AlertDescription>
              </Alert>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="practiceAnswer" className="sr-only">
                Your answer
              </Label>
              <Textarea
                id="practiceAnswer"
                value={answerDraft}
                onChange={(e) => setAnswerDraft(e.target.value)}
                rows={4}
                placeholder="Your answer… (Cmd/Ctrl+Enter to send)"
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    void sendAnswer();
                  }
                }}
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-muted-foreground text-xs">
                  {wordCount(answerDraft)} words •{" "}
                  {timer.autoStartOnQuestion ? "auto-timer on question" : "manual timer"}
                </p>
                <Button
                  type="button"
                  onClick={() => void sendAnswer()}
                  disabled={!answerDraft.trim() || isSending}
                >
                  {isSending ? "Sending..." : "Send"}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="bg-background space-y-3 rounded-lg border p-4">
            <h3 className="text-sm font-semibold">Session</h3>
            <div className="space-y-2">
              <Label htmlFor="resumeSession">Resume session id</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="resumeSession"
                  value={resumeSessionId}
                  onChange={(e) => setResumeSessionId(e.target.value)}
                  placeholder="Paste session id..."
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void loadSession(resumeSessionId)}
                  disabled={!resumeSessionId.trim()}
                >
                  Load
                </Button>
              </div>
              <p className="text-muted-foreground text-xs">
                Transcripts are saved locally. You can continue on a session id even if this device
                has no transcript yet.
              </p>
            </div>
          </div>

          <div className="bg-background space-y-3 rounded-lg border p-4">
            <h3 className="text-sm font-semibold">Timer</h3>
            <div className="space-y-2">
              <Label htmlFor="timerSeconds">Time per question (seconds)</Label>
              <Input
                id="timerSeconds"
                type="number"
                min={30}
                max={1800}
                value={timer.durationSeconds}
                onChange={(e) =>
                  setTimer((prev) => {
                    const duration = Math.max(30, Math.min(1800, Number(e.target.value)));
                    return {
                      ...prev,
                      durationSeconds: duration,
                      remainingSeconds: duration,
                      isRunning: false,
                    };
                  })
                }
              />
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  setTimer((prev) => ({ ...prev, autoStartOnQuestion: !prev.autoStartOnQuestion }))
                }
              >
                {timer.autoStartOnQuestion ? "Disable auto-start" : "Enable auto-start"}
              </Button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function CardHeaderLite({
  title,
  description,
  right,
}: {
  title: string;
  description: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-muted-foreground text-sm">{description}</p>
        </div>
        {right}
      </div>
    </div>
  );
}
