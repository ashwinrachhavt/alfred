import { isRecord } from "@/lib/utils";

export type FollowUpSource = "manual" | "task" | "gmail" | "calendar";

export type FollowUpItem = {
  id: string;
  title: string;
  createdAt: string;
  dueAt?: string;
  snoozedUntil?: string;
  completedAt?: string;
  href?: string;
  notes?: string;
  source?: FollowUpSource;
  meta?: Record<string, unknown>;
  /**
   * Optional label shown in UI when we can infer the template/workflow used.
   */
  templateLabel?: string;
};

export const FOLLOW_UP_STORAGE_KEY = "alfred:follow-ups:v1";
export const FOLLOW_UP_NOTIFIED_KEY = "alfred:follow-ups:notified:v1";

type StoredPayload = {
  version: 1;
  items: FollowUpItem[];
};

function normalizeIsoString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const date = new Date(trimmed);
  if (Number.isNaN(date.valueOf())) return undefined;
  return date.toISOString();
}

function normalizeString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function normalizeFollowUpItem(value: unknown): FollowUpItem | null {
  if (!isRecord(value)) return null;
  const id = normalizeString(value.id);
  const title = normalizeString(value.title);
  const createdAt = normalizeIsoString(value.createdAt);
  if (!id || !title || !createdAt) return null;

  const dueAt = normalizeIsoString(value.dueAt);
  const snoozedUntil = normalizeIsoString(value.snoozedUntil);
  const completedAt = normalizeIsoString(value.completedAt);
  const href = normalizeString(value.href);
  const notes = normalizeString(value.notes);
  const templateLabel = normalizeString(value.templateLabel);

  const sourceRaw = normalizeString(value.source);
  const source: FollowUpSource | undefined =
    sourceRaw === "manual" ||
    sourceRaw === "task" ||
    sourceRaw === "gmail" ||
    sourceRaw === "calendar"
      ? sourceRaw
      : undefined;

  const meta = isRecord(value.meta) ? (value.meta as Record<string, unknown>) : undefined;

  return {
    id,
    title,
    createdAt,
    dueAt,
    snoozedUntil,
    completedAt,
    href,
    notes,
    source,
    meta,
    templateLabel,
  };
}

export function loadFollowUps(): FollowUpItem[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(FOLLOW_UP_STORAGE_KEY);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!isRecord(parsed)) return [];
    const payload = parsed as StoredPayload;
    if (payload.version !== 1 || !Array.isArray(payload.items)) return [];

    const normalized = payload.items
      .map(normalizeFollowUpItem)
      .filter((item): item is FollowUpItem => Boolean(item));

    const seen = new Set<string>();
    return normalized.filter((item) => {
      if (seen.has(item.id)) return false;
      seen.add(item.id);
      return true;
    });
  } catch {
    return [];
  }
}

export function saveFollowUps(items: FollowUpItem[]): void {
  if (typeof window === "undefined") return;

  const payload: StoredPayload = {
    version: 1,
    items,
  };

  window.localStorage.setItem(FOLLOW_UP_STORAGE_KEY, JSON.stringify(payload));
}

export function followUpNotificationKey(item: FollowUpItem): string | null {
  if (!item.dueAt) return null;
  return `${item.id}:${item.dueAt}:${item.snoozedUntil ?? ""}`;
}

export function loadNotifiedFollowUpKeys(): Set<string> {
  if (typeof window === "undefined") return new Set();
  const raw = window.localStorage.getItem(FOLLOW_UP_NOTIFIED_KEY);
  if (!raw) return new Set();

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((key) => typeof key === "string" && key.trim().length > 0));
  } catch {
    return new Set();
  }
}

export function saveNotifiedFollowUpKeys(keys: Set<string>): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FOLLOW_UP_NOTIFIED_KEY, JSON.stringify(Array.from(keys)));
}
