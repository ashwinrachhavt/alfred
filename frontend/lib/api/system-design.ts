import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import type {
  AutosaveRequest,
  ComponentDefinition,
  DesignPrompt,
  DiagramAnalysis,
  DiagramEvaluation,
  DiagramQuestion,
  DiagramSuggestion,
  ScaleEstimateRequest,
  ScaleEstimateResponse,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishRequest,
  SystemDesignPublishResponse,
  SystemDesignSession,
  SystemDesignSessionCreate,
  SystemDesignSessionUpdate,
  TemplateDefinition,
} from "@/lib/api/types/system-design";

export async function createSystemDesignSession(
  payload: SystemDesignSessionCreate,
): Promise<SystemDesignSession> {
  return apiPostJson<SystemDesignSession, SystemDesignSessionCreate>(
    "/api/system-design/sessions",
    payload,
    {
      cache: "no-store",
    },
  );
}

export async function getSystemDesignSession(sessionId: string): Promise<SystemDesignSession> {
  return apiFetch<SystemDesignSession>(`/api/system-design/sessions/${sessionId}`, {
    cache: "no-store",
  });
}

export async function getSharedSystemDesignSession(shareId: string): Promise<SystemDesignSession> {
  return apiFetch<SystemDesignSession>(`/api/system-design/sessions/share/${shareId}`, {
    cache: "no-store",
  });
}

export async function autosaveSystemDesignDiagram(
  sessionId: string,
  payload: AutosaveRequest,
): Promise<SystemDesignSession> {
  return apiPatchJson<SystemDesignSession, AutosaveRequest>(
    `/api/system-design/sessions/${sessionId}/diagram`,
    payload,
    { cache: "no-store" },
  );
}

export async function updateSystemDesignSession(
  sessionId: string,
  payload: SystemDesignSessionUpdate,
): Promise<SystemDesignSession> {
  return apiPatchJson<SystemDesignSession, SystemDesignSessionUpdate>(
    `/api/system-design/sessions/${sessionId}`,
    payload,
    { cache: "no-store" },
  );
}

export async function updateSystemDesignNotes(
  sessionId: string,
  payload: { notes_markdown: string },
): Promise<SystemDesignSession> {
  return apiPatchJson<SystemDesignSession, { notes_markdown: string }>(
    `/api/system-design/sessions/${sessionId}/notes`,
    payload,
    { cache: "no-store" },
  );
}

export async function getSystemDesignComponents(): Promise<ComponentDefinition[]> {
  return apiFetch<ComponentDefinition[]>("/api/system-design/library/components", {
    cache: "no-store",
  });
}

export async function getSystemDesignTemplates(): Promise<TemplateDefinition[]> {
  return apiFetch<TemplateDefinition[]>("/api/system-design/library/templates", { cache: "no-store" });
}

export async function getSystemDesignPrompt(sessionId: string): Promise<DesignPrompt> {
  return apiPostJson<DesignPrompt, Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/prompt`,
    {},
    { cache: "no-store" },
  );
}

export async function analyzeSystemDesign(sessionId: string): Promise<DiagramAnalysis> {
  return apiPostJson<DiagramAnalysis, Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/analyze`,
    {},
    { cache: "no-store" },
  );
}

export async function getSystemDesignQuestions(
  sessionId: string,
): Promise<DiagramQuestion[]> {
  return apiPostJson<DiagramQuestion[], Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/questions`,
    {},
    { cache: "no-store" },
  );
}

export async function getSystemDesignSuggestions(
  sessionId: string,
): Promise<DiagramSuggestion[]> {
  return apiPostJson<DiagramSuggestion[], Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/suggestions`,
    {},
    { cache: "no-store" },
  );
}

export async function evaluateSystemDesign(sessionId: string): Promise<DiagramEvaluation> {
  return apiPostJson<DiagramEvaluation, Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/evaluate`,
    {},
    { cache: "no-store" },
  );
}

export async function getSystemDesignKnowledgeDraft(
  sessionId: string,
): Promise<SystemDesignKnowledgeDraft> {
  return apiPostJson<SystemDesignKnowledgeDraft, Record<string, never>>(
    `/api/system-design/sessions/${sessionId}/knowledge`,
    {},
    { cache: "no-store" },
  );
}

export async function publishSystemDesignSession(
  sessionId: string,
  payload: SystemDesignPublishRequest,
): Promise<SystemDesignPublishResponse> {
  return apiPostJson<SystemDesignPublishResponse, SystemDesignPublishRequest>(
    `/api/system-design/sessions/${sessionId}/publish`,
    payload,
    { cache: "no-store" },
  );
}

export async function scaleEstimate(
  payload: ScaleEstimateRequest,
): Promise<ScaleEstimateResponse> {
  return apiPostJson<ScaleEstimateResponse, ScaleEstimateRequest>(
    "/api/system-design/scale-estimate",
    payload,
    { cache: "no-store" },
  );
}
