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

type ApiFetchRetryOptions = {
  retries?: number;
  minDelayMs?: number;
  maxDelayMs?: number;
};

export type ApiFetchOptions = {
  timeoutMs?: number;
  retry?: ApiFetchRetryOptions;
};

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_RETRY: Required<ApiFetchRetryOptions> = {
  retries: 2,
  minDelayMs: 250,
  maxDelayMs: 2_500,
};

function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/+$/, "");
}

function isAbsoluteUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

function isFrontendApiPath(path: string): boolean {
  return path === "/api" || path.startsWith("/api/");
}

export function apiUrl(path: string): string {
  if (isAbsoluteUrl(path)) return path;

  // Prefer Next.js rewrites for internal API calls. This keeps the frontend
  // consistent (always calling `/api/*`) even when the backend mounts routers
  // outside `/api/*`.
  if (isFrontendApiPath(path)) return path;

  const base = getApiBaseUrl();
  if (!base) return path;
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

function createTimeoutSignal(
  signal: AbortSignal | null | undefined,
  timeoutMs: number,
): { signal: AbortSignal | undefined; cleanup: () => void; timedOut: () => boolean } {
  const upstreamSignal = signal ?? undefined;
  if (timeoutMs <= 0) {
    return { signal: upstreamSignal, cleanup: () => {}, timedOut: () => false };
  }

  const controller = new AbortController();
  let didTimeout = false;

  const cleanupFns: Array<() => void> = [];

  if (upstreamSignal) {
    if (upstreamSignal.aborted) {
      controller.abort(upstreamSignal.reason);
    } else {
      const onAbort = () => controller.abort(upstreamSignal.reason);
      upstreamSignal.addEventListener("abort", onAbort, { once: true });
      cleanupFns.push(() => upstreamSignal.removeEventListener("abort", onAbort));
    }
  }

  const timeout = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);
  cleanupFns.push(() => clearTimeout(timeout));

  return {
    signal: controller.signal,
    cleanup: () => cleanupFns.forEach((fn) => fn()),
    timedOut: () => didTimeout,
  };
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

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function isRetryableStatus(status: number): boolean {
  return status === 408 || status === 429 || status === 502 || status === 503 || status === 504;
}

function clampRetryOptions(
  retry: ApiFetchRetryOptions | undefined,
): Required<ApiFetchRetryOptions> {
  const providedRetries = retry?.retries ?? DEFAULT_RETRY.retries;
  const retries = Math.max(0, Math.min(5, providedRetries));
  const minDelayMs = Math.max(0, retry?.minDelayMs ?? DEFAULT_RETRY.minDelayMs);
  const maxDelayMs = Math.max(minDelayMs, retry?.maxDelayMs ?? DEFAULT_RETRY.maxDelayMs);
  return { retries, minDelayMs, maxDelayMs };
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function computeBackoffMs(attempt: number, opts: Required<ApiFetchRetryOptions>): number {
  const base = opts.minDelayMs * 2 ** Math.max(0, attempt);
  return Math.min(opts.maxDelayMs, Math.floor(base));
}

function parseRetryAfterMs(retryAfter: string | null): number | null {
  if (!retryAfter) return null;
  const raw = retryAfter.trim();
  if (!raw) return null;

  if (/^\\d+$/.test(raw)) {
    return Number(raw) * 1_000;
  }

  const parsed = Date.parse(raw);
  if (Number.isNaN(parsed)) return null;

  return Math.max(0, parsed - Date.now());
}

export async function apiFetch<TResponse>(
  path: string,
  init?: RequestInit,
  options?: ApiFetchOptions,
): Promise<TResponse> {
  const url = apiUrl(path);
  const method = (init?.method ?? "GET").toUpperCase();
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  const retryOpts = clampRetryOptions(options?.retry);
  const shouldRetry = method === "GET" || method === "HEAD";

  for (let attempt = 0; attempt <= (shouldRetry ? retryOpts.retries : 0); attempt += 1) {
    const { signal, cleanup, timedOut } = createTimeoutSignal(init?.signal, timeoutMs);

    try {
      const response = await fetch(url, { ...init, signal });
      const payload = await safeReadJson(response);

      if (!response.ok) {
        if (shouldRetry && attempt < retryOpts.retries && isRetryableStatus(response.status)) {
          const retryAfterMs = parseRetryAfterMs(response.headers.get("Retry-After"));
          const backoffMs = retryAfterMs ?? computeBackoffMs(attempt, retryOpts);
          await sleep(backoffMs);
          continue;
        }

        throw new ApiError(
          response.status,
          coerceErrorMessage(payload, response.statusText),
          payload,
        );
      }

      return payload as TResponse;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      if (isAbortError(error)) {
        if (timedOut()) {
          throw new ApiError(408, "Request timed out");
        }
        throw error;
      }

      if (shouldRetry && attempt < retryOpts.retries) {
        await sleep(computeBackoffMs(attempt, retryOpts));
        continue;
      }

      throw new ApiError(0, "Network request failed", error);
    } finally {
      cleanup();
    }
  }

  throw new ApiError(0, "Network request failed");
}

export async function apiPostJson<TResponse, TBody>(
  path: string,
  body: TBody,
  init?: Omit<RequestInit, "body" | "method">,
  options?: ApiFetchOptions,
): Promise<TResponse> {
  return apiFetch<TResponse>(
    path,
    {
      ...init,
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(init?.headers ?? {}),
      },
      body: JSON.stringify(body as unknown as JsonValue),
    },
    options,
  );
}

export async function apiPatchJson<TResponse, TBody>(
  path: string,
  body: TBody,
  init?: Omit<RequestInit, "body" | "method">,
  options?: ApiFetchOptions,
): Promise<TResponse> {
  return apiFetch<TResponse>(
    path,
    {
      ...init,
      method: "PATCH",
      headers: {
        "content-type": "application/json",
        ...(init?.headers ?? {}),
      },
      body: JSON.stringify(body as unknown as JsonValue),
    },
    options,
  );
}
