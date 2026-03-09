import { safeGetItem, safeSetJSON } from "@/lib/storage";

export type PracticeMessageRole = "candidate" | "interviewer" | "system";

export type PracticeMessage = {
  id: string;
  role: PracticeMessageRole;
  content: string;
  createdAt: string;
};

export type PracticeSessionSummary = {
  id: string;
  company: string;
  role: string;
  createdAt: string;
  updatedAt: string;
  lastInterviewerPrompt?: string;
};

export type PracticeSessionTranscript = {
  version: 1;
  sessionId: string;
  company: string;
  role: string;
  createdAt: string;
  updatedAt: string;
  messages: PracticeMessage[];
};

export const PRACTICE_SESSION_INDEX_KEY = "alfred:interview-practice:sessions:v1";

function transcriptStorageKey(sessionId: string): string {
  return `alfred:interview-practice:session:${sessionId}:v1`;
}

function normalizeMessage(value: PracticeMessage): PracticeMessage | null {
  const role = value.role;
  if (role !== "candidate" && role !== "interviewer" && role !== "system") return null;
  const id = value.id?.trim();
  if (!id) return null;
  const content = value.content ?? "";
  const createdAt = value.createdAt?.trim();
  if (!createdAt) return null;
  return { id, role, content, createdAt };
}

function normalizeSessionSummary(value: PracticeSessionSummary): PracticeSessionSummary | null {
  const id = value.id?.trim();
  if (!id) return null;
  const company = value.company?.trim() || "Company";
  const role = value.role?.trim() || "Software Engineer";
  const createdAt = value.createdAt?.trim();
  const updatedAt = value.updatedAt?.trim();
  if (!createdAt || !updatedAt) return null;
  return {
    id,
    company,
    role,
    createdAt,
    updatedAt,
    lastInterviewerPrompt: value.lastInterviewerPrompt,
  };
}

function normalizeTranscript(value: PracticeSessionTranscript): PracticeSessionTranscript | null {
  if (!value || value.version !== 1) return null;
  const sessionId = value.sessionId?.trim();
  if (!sessionId) return null;
  const company = value.company?.trim() || "Company";
  const role = value.role?.trim() || "Software Engineer";
  const createdAt = value.createdAt?.trim();
  const updatedAt = value.updatedAt?.trim();
  if (!createdAt || !updatedAt) return null;
  const messages = Array.isArray(value.messages)
    ? value.messages
        .map(normalizeMessage)
        .filter((message): message is PracticeMessage => Boolean(message))
    : [];
  return {
    version: 1,
    sessionId,
    company,
    role,
    createdAt,
    updatedAt,
    messages,
  };
}

export function loadPracticeSessionIndex(): PracticeSessionSummary[] {
  if (typeof window === "undefined") return [];
  const raw = safeGetItem(PRACTICE_SESSION_INDEX_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return [];
    const sessions = (parsed as { sessions?: unknown }).sessions;
    if (!Array.isArray(sessions)) return [];
    return sessions
      .map((entry) => entry as PracticeSessionSummary)
      .map(normalizeSessionSummary)
      .filter((session): session is PracticeSessionSummary => Boolean(session))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  } catch {
    return [];
  }
}

export function savePracticeSessionIndex(sessions: PracticeSessionSummary[]): void {
  if (typeof window === "undefined") return;
  const payload = {
    version: 1,
    sessions,
  };
  safeSetJSON(PRACTICE_SESSION_INDEX_KEY, payload);
}

export function upsertPracticeSessionSummary(summary: PracticeSessionSummary): void {
  const normalized = normalizeSessionSummary(summary);
  if (!normalized) return;
  const existing = loadPracticeSessionIndex();
  const next = [normalized, ...existing.filter((entry) => entry.id !== normalized.id)].slice(0, 25);
  savePracticeSessionIndex(next);
}

export function loadPracticeSessionTranscript(sessionId: string): PracticeSessionTranscript | null {
  if (typeof window === "undefined") return null;
  const normalizedId = sessionId.trim();
  if (!normalizedId) return null;
  const raw = safeGetItem(transcriptStorageKey(normalizedId));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as PracticeSessionTranscript;
    return normalizeTranscript(parsed);
  } catch {
    return null;
  }
}

export function savePracticeSessionTranscript(transcript: PracticeSessionTranscript): void {
  if (typeof window === "undefined") return;
  const normalized = normalizeTranscript(transcript);
  if (!normalized) return;
  safeSetJSON(transcriptStorageKey(normalized.sessionId), normalized);
}
