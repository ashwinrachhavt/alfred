"use client";

/**
 * COLOR BUDGET — Today Page (Midnight Editorial)
 *
 * Accent color #E8590C (via bg-primary / text-primary / border-primary) is
 * limited to these surfaces only:
 *   1. Active view toggle in TodayHeader
 *   2. Priority=3 row indicator
 *   3. Save / Create CTA in EntryDrawer
 *   4. Selected-row left border when drawer is open for that id
 *
 * Everywhere else: warm monochrome via --alfred-* vars. Status expressed via
 * typography (strikethrough, opacity, italic), NOT semantic colors.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { X } from "lucide-react";
import { toast } from "sonner";

import { useQueryClient, type Query } from "@tanstack/react-query";

import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  useCreateTodayEntry,
  useDeleteTodayEntry,
  useUpdateTodayEntry,
} from "@/features/today/mutations";
import { toIsoDay } from "@/features/today/queries";
import type {
  DailyEntriesResponse,
  DailyEntryItem,
  DailyEntryUpdate,
  TodayEntryKind,
  TodayEntryStatus,
} from "@/features/today/types";

type EditableKind = Exclude<TodayEntryKind, "artifact_ref">;

const EDITABLE_KINDS: { value: EditableKind; label: string }[] = [
  { value: "todo", label: "Todo" },
  { value: "note", label: "Note" },
  { value: "learning", label: "Learning" },
];

const PRIORITIES: { value: number; label: string }[] = [
  { value: 0, label: "None" },
  { value: 1, label: "Low" },
  { value: 2, label: "Med" },
  { value: 3, label: "High" },
];

const LABEL_CLS =
  "text-[10px] font-medium uppercase tracking-widest text-[var(--alfred-text-tertiary)]";
const FIELD_ROW = "space-y-1.5";

interface DraftState {
  title: string;
  kind: EditableKind;
  entry_date: string; // YYYY-MM-DD
  status: TodayEntryStatus;
  priority: number;
  tags: string[];
  body_md: string;
}

function draftFromEntry(entry: DailyEntryItem): DraftState {
  return {
    title: entry.title,
    kind: (entry.kind === "artifact_ref" ? "note" : entry.kind) as EditableKind,
    entry_date: entry.entry_date,
    status: ((entry.status ?? "open") as TodayEntryStatus),
    priority: entry.priority,
    tags: [...entry.tags],
    body_md: entry.body_md,
  };
}

function emptyDraft(today: string): DraftState {
  return {
    title: "",
    kind: "todo",
    entry_date: today,
    status: "open",
    priority: 0,
    tags: [],
    body_md: "",
  };
}

function diffPatch(before: DraftState, after: DraftState): DailyEntryUpdate {
  const patch: DailyEntryUpdate = {};
  if (before.title !== after.title) patch.title = after.title;
  if (before.kind !== after.kind) patch.kind = after.kind;
  if (before.entry_date !== after.entry_date) patch.entry_date = after.entry_date;
  if (before.status !== after.status) patch.status = after.status;
  if (before.priority !== after.priority) patch.priority = after.priority;
  if (before.body_md !== after.body_md) patch.body_md = after.body_md;
  if (
    before.tags.length !== after.tags.length ||
    before.tags.some((t, i) => t !== after.tags[i])
  ) {
    patch.tags = [...after.tags];
  }
  return patch;
}

export function EntryDrawer({
  open,
  entryId,
  onOpenChange,
}: {
  open: boolean;
  entryId: number | "create" | null;
  onOpenChange: (open: boolean) => void;
}) {
  const today = toIsoDay(new Date());
  const queryClient = useQueryClient();

  const isEdit = typeof entryId === "number";

  // Pull the target entry from whichever ``["today", "entries", ...]`` cache
  // already has it — the table view keeps at least one such cache alive.
  const cachedEntry = useMemo<DailyEntryItem | null>(() => {
    if (!isEdit || entryId == null) return null;
    const queries = queryClient.getQueryCache().findAll({
      predicate: (query: Query) => {
        const key = query.queryKey;
        return (
          Array.isArray(key) &&
          key.length >= 2 &&
          key[0] === "today" &&
          key[1] === "entries"
        );
      },
    });
    for (const query of queries) {
      const data = query.state.data as DailyEntriesResponse | undefined;
      if (!data) continue;
      const hit = data.entries.find((e) => e.id === entryId);
      if (hit) return hit;
    }
    return null;
    // React Query updates mutate cache in-place; we re-run when entryId or
    // open changes (drawer remounts). For in-session updates the optimistic
    // patch will flow through because we hold a reference into that cache.
  }, [isEdit, entryId, queryClient]);

  // State machine for the drawer's edit draft.
  //
  // React 19 disallows both "setState inside an effect" and "ref-access during
  // render", so we store the last-seen target-identity alongside the draft
  // itself and reset during render when the identity changes. See
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders
  interface DraftStoreState {
    draft: DraftState;
    initial: DraftState;
    tagDraft: string;
    savedRecently: boolean;
    seenTargetKey: string;
  }
  const computeTargetKey = (): string =>
    `${open ? 1 : 0}|${String(entryId)}|${cachedEntry?.updated_at ?? ""}`;
  const targetKey = computeTargetKey();
  const resetFor = (): DraftStoreState => {
    let next: DraftState;
    if (!open) {
      next = emptyDraft(today);
    } else if (entryId === "create") {
      next = emptyDraft(today);
    } else if (typeof entryId === "number" && cachedEntry) {
      next = draftFromEntry(cachedEntry);
    } else {
      next = emptyDraft(today);
    }
    return {
      draft: next,
      initial: next,
      tagDraft: "",
      savedRecently: false,
      seenTargetKey: targetKey,
    };
  };
  const [store, setStore] = useState<DraftStoreState>(() => resetFor());
  // Reconcile on target change (render-phase setState is the React 19 idiom).
  let activeStore = store;
  if (store.seenTargetKey !== targetKey) {
    activeStore = resetFor();
    setStore(activeStore);
  }
  const draft = activeStore.draft;
  const initialBaseline = activeStore.initial;
  const tagDraft = activeStore.tagDraft;
  const savedRecently = activeStore.savedRecently;
  const setDraft = useCallback(
    (updater: DraftState | ((prev: DraftState) => DraftState)) => {
      setStore((prev) => ({
        ...prev,
        draft:
          typeof updater === "function"
            ? (updater as (p: DraftState) => DraftState)(prev.draft)
            : updater,
      }));
    },
    [],
  );
  const setTagDraft = useCallback((v: string) => {
    setStore((prev) => ({ ...prev, tagDraft: v }));
  }, []);
  const setSavedRecently = useCallback((v: boolean) => {
    setStore((prev) => ({ ...prev, savedRecently: v }));
  }, []);
  const setInitial = useCallback((v: DraftState) => {
    setStore((prev) => ({ ...prev, initial: v }));
  }, []);
  const savedFlagTimerRef = useRef<number | null>(null);
  const autoSaveTimerRef = useRef<number | null>(null);

  const createMutation = useCreateTodayEntry();
  const updateMutation = useUpdateTodayEntry();
  const deleteMutation = useDeleteTodayEntry();

  const flushAutoSave = useCallback(
    async (next: DraftState) => {
      if (!isEdit || typeof entryId !== "number") return;
      const patch = diffPatch(initialBaseline, next);
      if (Object.keys(patch).length === 0) return;
      try {
        await updateMutation.mutateAsync({ id: entryId, patch });
        setInitial(next);
        setSavedRecently(true);
        if (savedFlagTimerRef.current !== null) {
          window.clearTimeout(savedFlagTimerRef.current);
        }
        savedFlagTimerRef.current = window.setTimeout(() => {
          setSavedRecently(false);
        }, 3000);
      } catch {
        toast.error("Failed to save changes");
      }
    },
    [entryId, initialBaseline, isEdit, setInitial, setSavedRecently, updateMutation],
  );

  const scheduleAutoSave = useCallback(
    (next: DraftState) => {
      if (!isEdit) return;
      if (autoSaveTimerRef.current !== null) {
        window.clearTimeout(autoSaveTimerRef.current);
      }
      autoSaveTimerRef.current = window.setTimeout(() => {
        void flushAutoSave(next);
      }, 500);
    },
    [flushAutoSave, isEdit],
  );

  useEffect(
    () => () => {
      if (autoSaveTimerRef.current !== null) {
        window.clearTimeout(autoSaveTimerRef.current);
      }
      if (savedFlagTimerRef.current !== null) {
        window.clearTimeout(savedFlagTimerRef.current);
      }
    },
    [],
  );

  const updateDraft = useCallback(
    (patch: Partial<DraftState>) => {
      setDraft((prev) => {
        const next = { ...prev, ...patch };
        scheduleAutoSave(next);
        return next;
      });
    },
    [scheduleAutoSave, setDraft],
  );

  const onAddTag = useCallback(() => {
    const cleaned = tagDraft.trim().toLowerCase();
    if (!cleaned) return;
    if (draft.tags.includes(cleaned)) {
      setTagDraft("");
      return;
    }
    updateDraft({ tags: [...draft.tags, cleaned] });
    setTagDraft("");
  }, [draft.tags, setTagDraft, tagDraft, updateDraft]);

  const onRemoveTag = useCallback(
    (tag: string) => {
      updateDraft({ tags: draft.tags.filter((t) => t !== tag) });
    },
    [draft.tags, updateDraft],
  );

  const onCreate = useCallback(async () => {
    if (!draft.title.trim()) {
      toast.error("Title is required");
      return;
    }
    try {
      await createMutation.mutateAsync({
        entry_date: draft.entry_date,
        kind: draft.kind,
        title: draft.title.trim(),
        body_md: draft.body_md,
        status: draft.status,
        priority: draft.priority,
        tags: draft.tags,
      });
      toast.success("Entry created");
      onOpenChange(false);
    } catch {
      toast.error("Failed to create entry");
    }
  }, [createMutation, draft, onOpenChange]);

  const onDelete = useCallback(async () => {
    if (typeof entryId !== "number") return;
    if (!window.confirm("Delete this entry? This cannot be undone.")) return;
    try {
      await deleteMutation.mutateAsync(entryId);
      toast.success("Entry deleted");
      onOpenChange(false);
    } catch {
      toast.error("Failed to delete entry");
    }
  }, [deleteMutation, entryId, onOpenChange]);

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (isEdit) {
          void flushAutoSave(draft);
        } else {
          void onCreate();
        }
      }
    },
    [draft, flushAutoSave, isEdit, onCreate],
  );

  const showSaved = savedRecently || updateMutation.isPending;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 p-0 sm:max-w-[480px]"
        onKeyDown={onKeyDown}
      >
        <div className="flex h-full flex-col">
          {/* Header */}
          <header className="flex items-start justify-between gap-3 border-b border-[var(--alfred-ruled-line)] px-5 pb-3 pt-5">
            <div className="min-w-0 flex-1">
              {entryId === "create" ? (
                <p className="font-serif text-lg text-foreground">New entry</p>
              ) : (
                <p className={LABEL_CLS}>Edit entry</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {isEdit && (
                <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
                  {updateMutation.isPending ? "Saving…" : showSaved ? "Saved ·" : ""}
                </span>
              )}
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded-sm p-1 text-[var(--alfred-text-tertiary)] hover:text-foreground"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
          </header>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
            {/* Title */}
            <input
              type="text"
              value={draft.title}
              onChange={(e) => setDraft((p) => ({ ...p, title: e.target.value }))}
              onBlur={() => scheduleAutoSave(draft)}
              placeholder="Untitled"
              className="w-full border-0 bg-transparent p-0 text-2xl text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus-visible:outline-none"
              aria-label="Title"
            />

            {/* Kind */}
            <div className={FIELD_ROW}>
              <p className={LABEL_CLS}>Kind</p>
              <div className="flex gap-1.5">
                {EDITABLE_KINDS.map((opt) => {
                  const active = draft.kind === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => updateDraft({ kind: opt.value })}
                      aria-pressed={active}
                      className={cn(
                        "rounded-sm border border-[var(--alfred-ruled-line)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest transition-colors",
                        active
                          ? "bg-[var(--alfred-accent-subtle)] text-foreground border-[var(--alfred-accent-muted)]"
                          : "text-[var(--alfred-text-tertiary)] hover:text-foreground",
                      )}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Date */}
            <div className={FIELD_ROW}>
              <p className={LABEL_CLS}>Date</p>
              <input
                type="date"
                value={draft.entry_date}
                onChange={(e) => updateDraft({ entry_date: e.target.value })}
                className="rounded-sm border border-[var(--alfred-ruled-line)] bg-transparent px-2 py-1 font-mono text-sm text-foreground focus-visible:border-ring focus-visible:outline-none"
              />
            </div>

            {/* Status (not shown in create mode — defaults to open) */}
            {isEdit && (
              <div className={FIELD_ROW}>
                <p className={LABEL_CLS}>Status</p>
                <div className="flex gap-1.5">
                  {(["open", "doing", "done", "skipped"] as TodayEntryStatus[]).map((s) => {
                    const active = draft.status === s;
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => updateDraft({ status: s })}
                        aria-pressed={active}
                        className={cn(
                          "rounded-sm border border-[var(--alfred-ruled-line)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest transition-colors",
                          active
                            ? "bg-[var(--alfred-accent-subtle)] text-foreground border-[var(--alfred-accent-muted)]"
                            : "text-[var(--alfred-text-tertiary)] hover:text-foreground",
                        )}
                      >
                        {s}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Priority */}
            <div className={FIELD_ROW}>
              <p className={LABEL_CLS}>Priority</p>
              <div className="flex gap-1.5">
                {PRIORITIES.map((p) => {
                  const active = draft.priority === p.value;
                  return (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => updateDraft({ priority: p.value })}
                      aria-pressed={active}
                      className={cn(
                        "rounded-sm border border-[var(--alfred-ruled-line)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest transition-colors",
                        active
                          ? "bg-[var(--alfred-accent-subtle)] text-foreground border-[var(--alfred-accent-muted)]"
                          : "text-[var(--alfred-text-tertiary)] hover:text-foreground",
                      )}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Tags */}
            <div className={FIELD_ROW}>
              <p className={LABEL_CLS}>Tags</p>
              <div className="flex flex-wrap items-center gap-1.5">
                {draft.tags.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1 rounded-sm bg-[var(--alfred-accent-muted)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-foreground"
                  >
                    {t}
                    <button
                      type="button"
                      onClick={() => onRemoveTag(t)}
                      aria-label={`Remove tag ${t}`}
                      className="text-[var(--alfred-text-tertiary)] hover:text-foreground"
                    >
                      <X className="size-3" aria-hidden="true" />
                    </button>
                  </span>
                ))}
                <input
                  type="text"
                  value={tagDraft}
                  onChange={(e) => setTagDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === ",") {
                      e.preventDefault();
                      onAddTag();
                    } else if (e.key === "Backspace" && tagDraft.length === 0 && draft.tags.length > 0) {
                      onRemoveTag(draft.tags[draft.tags.length - 1]);
                    }
                  }}
                  onBlur={onAddTag}
                  placeholder="add tag…"
                  className="h-6 w-24 rounded-sm border border-[var(--alfred-ruled-line)] bg-transparent px-2 font-mono text-[11px] text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus-visible:border-ring focus-visible:outline-none"
                />
              </div>
            </div>

            {/* Body */}
            <div className={FIELD_ROW}>
              <p className={LABEL_CLS}>Body</p>
              <textarea
                value={draft.body_md}
                onChange={(e) => setDraft((p) => ({ ...p, body_md: e.target.value }))}
                onBlur={() => scheduleAutoSave(draft)}
                placeholder="Write markdown…"
                rows={10}
                className="w-full resize-y rounded-sm border border-[var(--alfred-ruled-line)] bg-transparent p-3 font-mono text-sm text-foreground placeholder:text-[var(--alfred-text-tertiary)] focus-visible:border-ring focus-visible:outline-none"
              />
            </div>
          </div>

          {/* Footer */}
          <footer className="flex items-center justify-between gap-2 border-t border-[var(--alfred-ruled-line)] px-5 py-3">
            {isEdit ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onDelete}
                disabled={deleteMutation.isPending}
                className="text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)] hover:text-foreground"
              >
                Delete
              </Button>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-2">
              <span className="hidden font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)] sm:inline">
                ⌘↵ save
              </span>
              {isEdit ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void flushAutoSave(draft)}
                  disabled={updateMutation.isPending}
                  className="text-xs uppercase tracking-widest"
                >
                  Save
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void onCreate()}
                  disabled={createMutation.isPending}
                  className="text-xs uppercase tracking-widest"
                >
                  Create
                </Button>
              )}
            </div>
          </footer>
        </div>
      </SheetContent>
    </Sheet>
  );
}

// Backwards-compatible default shape for files that imported a prop-less stub.
export default EntryDrawer;
