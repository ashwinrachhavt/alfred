import { apiFetch, apiFetchText, apiPatchJson, apiPostJson } from "@/lib/api/client";
import type {
  AutosaveRequest,
  ComponentDefinition,
  ScaleEstimateRequest,
  ScaleEstimateResponse,
  SystemDesignKnowledgeDraft,
  SystemDesignPublishRequest,
  SystemDesignPublishResponse,
  SystemDesignShareUpdate,
  SystemDesignSession,
  SystemDesignSessionCreate,
  SystemDesignSessionSummary,
  SystemDesignSessionUpdate,
  SystemDesignTemplateCreate,
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

export async function listSystemDesignSessions(
  limit = 20,
): Promise<SystemDesignSessionSummary[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetch<SystemDesignSessionSummary[]>(`/api/system-design/sessions?${params.toString()}`, {
    cache: "no-store",
  });
}

export async function getSystemDesignSession(sessionId: string): Promise<SystemDesignSession> {
  return apiFetch<SystemDesignSession>(`/api/system-design/sessions/${sessionId}`, {
    cache: "no-store",
  });
}

export async function getSharedSystemDesignSession(
  shareId: string,
  options?: { password?: string | null },
): Promise<SystemDesignSession> {
  const headers: HeadersInit = {};
  if (options?.password) headers["X-Alfred-Share-Password"] = options.password;

  return apiFetch<SystemDesignSession>(`/api/system-design/sessions/share/${shareId}`, {
    cache: "no-store",
    headers,
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
  return apiFetch<TemplateDefinition[]>("/api/system-design/library/templates", {
    cache: "no-store",
  });
}

export async function createSystemDesignTemplate(
  payload: SystemDesignTemplateCreate,
): Promise<TemplateDefinition> {
  return apiPostJson<TemplateDefinition, SystemDesignTemplateCreate>(
    "/api/system-design/library/templates",
    payload,
    { cache: "no-store" },
  );
}

export async function updateSystemDesignShareSettings(
  sessionId: string,
  payload: SystemDesignShareUpdate,
): Promise<SystemDesignSession> {
  return apiPatchJson<SystemDesignSession, SystemDesignShareUpdate>(
    `/api/system-design/sessions/${sessionId}/share`,
    payload,
    { cache: "no-store" },
  );
}

export async function exportSystemDesignMermaid(sessionId: string): Promise<string> {
  return apiFetchText(`/api/system-design/sessions/${sessionId}/export/mermaid`, {
    cache: "no-store",
  });
}

export async function exportSystemDesignPlantUml(sessionId: string): Promise<string> {
  return apiFetchText(`/api/system-design/sessions/${sessionId}/export/plantuml`, {
    cache: "no-store",
  });
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

export async function scaleEstimate(payload: ScaleEstimateRequest): Promise<ScaleEstimateResponse> {
  return apiPostJson<ScaleEstimateResponse, ScaleEstimateRequest>(
    "/api/system-design/scale-estimate",
    payload,
    { cache: "no-store" },
  );
}
