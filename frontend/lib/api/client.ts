export class ApiError extends Error {
  readonly name = "ApiError";

  constructor(
    readonly status: number,
    message: string,
    readonly payload?: unknown,
  ) {
    super(message);
  }
}

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, "");
}

function isAbsoluteUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

export function apiUrl(path: string): string {
  if (isAbsoluteUrl(path)) return path;
  const base = getApiBaseUrl();
  if (!base) return path;
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function safeReadJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function coerceErrorMessage(payload: unknown, fallback: string): string {
  if (!payload) return fallback;
  if (typeof payload === "string") return payload;
  if (typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export async function apiFetch<TResponse>(
  path: string,
  init?: RequestInit,
): Promise<TResponse> {
  const url = apiUrl(path);
  const response = await fetch(url, init);
  const payload = await safeReadJson(response);

  if (!response.ok) {
    throw new ApiError(
      response.status,
      coerceErrorMessage(payload, response.statusText),
      payload,
    );
  }

  return payload as TResponse;
}

export async function apiPostJson<TResponse, TBody>(
  path: string,
  body: TBody,
  init?: Omit<RequestInit, "body" | "method">,
): Promise<TResponse> {
  return apiFetch<TResponse>(path, {
    ...init,
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    body: JSON.stringify(body as unknown as JsonValue),
  });
}

export async function apiPatchJson<TResponse, TBody>(
  path: string,
  body: TBody,
  init?: Omit<RequestInit, "body" | "method">,
): Promise<TResponse> {
  return apiFetch<TResponse>(path, {
    ...init,
    method: "PATCH",
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    body: JSON.stringify(body as unknown as JsonValue),
  });
}
