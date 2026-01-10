"use client";

import * as React from "react";
import { toast } from "sonner";

import {
  followUpNotificationKey,
  loadFollowUps,
  loadNotifiedFollowUpKeys,
  saveFollowUps,
  saveNotifiedFollowUpKeys,
  type FollowUpItem,
  type FollowUpSource,
} from "@/features/follow-ups/follow-up-store";

type FollowUpCreateInput = {
  title: string;
  dueAt?: string | null;
  href?: string | null;
  notes?: string | null;
  source?: FollowUpSource;
  templateLabel?: string | null;
  meta?: Record<string, unknown>;
};

type FollowUpPatch = {
  title?: string;
  dueAt?: string | null;
  snoozedUntil?: string | null;
  completedAt?: string | null;
  href?: string | null;
  notes?: string | null;
  source?: FollowUpSource;
  templateLabel?: string | null;
  meta?: Record<string, unknown> | null;
};

type FollowUpsContextValue = {
  items: FollowUpItem[];
  openCount: number;
  dueNowCount: number;
  isFollowUpCenterOpen: boolean;
  setFollowUpCenterOpen: (open: boolean) => void;
  addFollowUp: (input: FollowUpCreateInput) => FollowUpItem | null;
  updateFollowUp: (id: string, patch: FollowUpPatch) => void;
  removeFollowUp: (id: string) => void;
  markDone: (id: string) => void;
  snooze: (id: string, minutes: number) => void;
  clearCompleted: () => void;
};

const FollowUpsContext = React.createContext<FollowUpsContextValue | null>(null);

function useFollowUpsContext(): FollowUpsContextValue {
  const ctx = React.useContext(FollowUpsContext);
  if (!ctx) throw new Error("useFollowUps must be used within FollowUpsProvider.");
  return ctx;
}

function nowIso(): string {
  return new Date().toISOString();
}

function normalizeMaybeDate(value: string | null | undefined): string | undefined {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return undefined;
  const date = new Date(trimmed);
  if (Number.isNaN(date.valueOf())) return undefined;
  return date.toISOString();
}

function safeUrl(value: string | null | undefined): string | undefined {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return undefined;
  try {
    // Accept absolute URLs and relative app routes.
    if (trimmed.startsWith("/")) return trimmed;
    const parsed = new URL(trimmed);
    return parsed.toString();
  } catch {
    return undefined;
  }
}

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `fu_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

function isCompleted(item: FollowUpItem): boolean {
  return Boolean(item.completedAt);
}

function isSnoozed(item: FollowUpItem, nowMs: number): boolean {
  if (!item.snoozedUntil) return false;
  const until = Date.parse(item.snoozedUntil);
  if (Number.isNaN(until)) return false;
  return until > nowMs;
}

function isDueNow(item: FollowUpItem, nowMs: number): boolean {
  if (!item.dueAt) return false;
  const due = Date.parse(item.dueAt);
  if (Number.isNaN(due)) return false;
  return due <= nowMs;
}

function formatDueLabel(dueAt: string): string | null {
  const due = new Date(dueAt);
  if (Number.isNaN(due.valueOf())) return null;
  const now = new Date();
  const sameDay = due.toDateString() === now.toDateString();
  if (sameDay) {
    return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(due);
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(due);
}

export function FollowUpsProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<FollowUpItem[]>(() => loadFollowUps());
  const [isFollowUpCenterOpen, setFollowUpCenterOpen] = React.useState(false);
  const [nowMs, setNowMs] = React.useState(0);

  const notifiedRef = React.useRef<Set<string>>(loadNotifiedFollowUpKeys());
  const lastSweepAtRef = React.useRef<number>(0);

  const persist = React.useCallback((updater: (prev: FollowUpItem[]) => FollowUpItem[]) => {
    setItems((prev) => {
      const next = updater(prev);
      saveFollowUps(next);
      return next;
    });
  }, []);

  const addFollowUp = React.useCallback(
    (input: FollowUpCreateInput): FollowUpItem | null => {
      const title = input.title.trim();
      if (!title) return null;

      const createdAt = nowIso();
      const dueAt = normalizeMaybeDate(input.dueAt ?? undefined);
      const href = safeUrl(input.href);
      const notes = input.notes?.trim() ? input.notes.trim() : undefined;
      const templateLabel = input.templateLabel?.trim() ? input.templateLabel.trim() : undefined;

      const next: FollowUpItem = {
        id: createId(),
        title,
        createdAt,
        dueAt,
        href,
        notes,
        source: input.source,
        meta: input.meta,
        templateLabel,
      };

      persist((prev) => [next, ...prev]);
      return next;
    },
    [persist],
  );

  const updateFollowUp = React.useCallback(
    (id: string, patch: FollowUpPatch) => {
      const normalizedId = id.trim();
      if (!normalizedId) return;

      persist((prev) =>
        prev.map((item) => {
          if (item.id !== normalizedId) return item;
          const next: FollowUpItem = { ...item };

          if (patch.title !== undefined) {
            const trimmed = patch.title.trim();
            next.title = trimmed ? trimmed : item.title;
          }
          if (patch.href !== undefined) {
            next.href = safeUrl(patch.href);
          }
          if (patch.notes !== undefined) {
            const trimmed = (patch.notes ?? "").trim();
            next.notes = trimmed ? trimmed : undefined;
          }
          if (patch.dueAt !== undefined) {
            next.dueAt = normalizeMaybeDate(patch.dueAt);
          }
          if (patch.snoozedUntil !== undefined) {
            next.snoozedUntil = normalizeMaybeDate(patch.snoozedUntil);
          }
          if (patch.completedAt !== undefined) {
            next.completedAt = normalizeMaybeDate(patch.completedAt);
          }
          if (patch.templateLabel !== undefined) {
            const trimmed = (patch.templateLabel ?? "").trim();
            next.templateLabel = trimmed ? trimmed : undefined;
          }
          if (patch.meta !== undefined) {
            next.meta = patch.meta ?? undefined;
          }
          if (patch.source !== undefined) {
            next.source = patch.source;
          }

          return next;
        }),
      );
    },
    [persist],
  );

  const removeFollowUp = React.useCallback(
    (id: string) => {
      const normalizedId = id.trim();
      if (!normalizedId) return;
      persist((prev) => prev.filter((item) => item.id !== normalizedId));
    },
    [persist],
  );

  const markDone = React.useCallback(
    (id: string) => {
      updateFollowUp(id, { completedAt: nowIso(), snoozedUntil: null });
    },
    [updateFollowUp],
  );

  const snooze = React.useCallback(
    (id: string, minutes: number) => {
      const mins = Number.isFinite(minutes) ? Math.max(5, Math.min(7 * 24 * 60, minutes)) : 60;
      const snoozedUntil = new Date(Date.now() + mins * 60_000).toISOString();
      updateFollowUp(id, { snoozedUntil });
    },
    [updateFollowUp],
  );

  const clearCompleted = React.useCallback(() => {
    persist((prev) => prev.filter((item) => !item.completedAt));
  }, [persist]);

  const openCount = React.useMemo(() => items.filter((item) => !isCompleted(item)).length, [items]);

  const dueNowCount = React.useMemo(() => {
    return items.reduce((count, item) => {
      if (isCompleted(item)) return count;
      if (isSnoozed(item, nowMs)) return count;
      return isDueNow(item, nowMs) ? count + 1 : count;
    }, 0);
  }, [items, nowMs]);

  const maybeNotifyDueFollowUps = React.useCallback(() => {
    const nowMs = Date.now();
    // Avoid repeated tight loops on fast re-renders.
    if (nowMs - lastSweepAtRef.current < 25_000) return;
    lastSweepAtRef.current = nowMs;

    items.forEach((item) => {
      if (isCompleted(item)) return;
      if (!item.dueAt) return;
      if (isSnoozed(item, nowMs)) return;
      if (!isDueNow(item, nowMs)) return;

      const key = followUpNotificationKey(item);
      if (!key) return;
      if (notifiedRef.current.has(key)) return;

      const dueLabel = formatDueLabel(item.dueAt);
      const descriptionParts: string[] = [];
      if (dueLabel) descriptionParts.push(`Due: ${dueLabel}`);
      if (item.templateLabel) descriptionParts.push(item.templateLabel);

      toast.message(item.title, {
        description: descriptionParts.join(" • ") || "Follow-up due.",
        action: {
          label: "Snooze 1h",
          onClick: () => snooze(item.id, 60),
        },
        cancel: {
          label: "Done",
          onClick: () => markDone(item.id),
        },
      });

      notifiedRef.current.add(key);
      saveNotifiedFollowUpKeys(notifiedRef.current);
    });
  }, [items, markDone, snooze]);

  React.useEffect(() => {
    const tick = () => {
      setNowMs(Date.now());
      maybeNotifyDueFollowUps();
    };

    tick();
    const interval = window.setInterval(tick, 30_000);
    return () => window.clearInterval(interval);
  }, [maybeNotifyDueFollowUps]);

  const value = React.useMemo<FollowUpsContextValue>(
    () => ({
      items,
      openCount,
      dueNowCount,
      isFollowUpCenterOpen,
      setFollowUpCenterOpen,
      addFollowUp,
      updateFollowUp,
      removeFollowUp,
      markDone,
      snooze,
      clearCompleted,
    }),
    [
      addFollowUp,
      clearCompleted,
      dueNowCount,
      isFollowUpCenterOpen,
      items,
      markDone,
      openCount,
      removeFollowUp,
      setFollowUpCenterOpen,
      snooze,
      updateFollowUp,
    ],
  );

  return <FollowUpsContext.Provider value={value}>{children}</FollowUpsContext.Provider>;
}

export function useFollowUps() {
  return useFollowUpsContext();
}
