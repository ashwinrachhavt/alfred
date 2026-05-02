import { create } from "zustand";
import { del, get as idbGet, set as idbSet } from "idb-keyval";

// ----- Types -----

export type BloomLevel = 1 | 2 | 3 | 4 | 5 | 6;

export type BloomSource =
  | "backfill"
  | "ai_inferred"
  | "user_set"
  | "review_updated";

export type BloomInference = {
  inferredLevel: BloomLevel;
  source: BloomSource;
  rationale?: string;
};

export type LinkSuggestion = {
  card_id: number;
  title: string;
  score: number;
  reason: string;
};

export type Enrichment = {
  suggested_title: string | null;
  summary: string | null;
  suggested_tags: string[];
  suggested_topic: string | null;
};

export type Decomposition = {
  is_atomic: boolean;
  reason: string;
  suggested_cards: Array<{ title: string; content: string }>;
};

export type BloomQuestion = {
  id: string; // stable client id for React keys
  level: BloomLevel;
  question: string; // e.g. "What mechanism produces this?"
};

export type AnalysisResult = {
  generatedAtWordCount: number;
  connections: LinkSuggestion[];
  enrichment: Enrichment | null;
  decomposition: Decomposition | null;
  bloomQuestions: BloomQuestion[];
};

export type StreamError = { step: string; message: string };

export type CardPhase =
  | "idle"
  | "typing"
  | "analyzing"
  | "ready"
  | "stale"
  | "retryable";

export type DraftState = {
  clientId: string; // uuid, generated once per draft
  content: string;
  title: string;
  bloom: BloomInference | null;
  lastLocalSaveAt: number;
};

export type SavedCardState = {
  id: number;
  phase: CardPhase;
  content: string;
  title: string;
  bloom: BloomInference;
  analysis: AnalysisResult | null;
  enrichmentLastError: string | null;
  archivedAt: string | null; // ISO string iff the card is archived
  lastSavedAt: number;
};

export type StackEntry =
  | { type: "saved"; id: number }
  | { type: "draft"; clientId: string };

export type SharedContext = {
  topic?: string;
  tags: string[];
  sourceContext?: string;
};

export type ZettelWorkspaceState = {
  // Session
  sessionId: number | null;
  sharedContext: SharedContext;

  // Cards
  savedCards: Map<number, SavedCardState>;
  activeDraft: DraftState | null;
  stackOrder: StackEntry[];

  // Which entry is currently focused in the WritingSurface.
  // Keeps SessionRail ↔ WritingSurface in sync without duplicating the draft.
  focusedEntry: StackEntry | null;

  // Cancellation registry (key = `card:<id>` or `draft:<clientId>`)
  abortControllers: Map<string, AbortController>;

  // Actions
  setSession: (id: number, shared: SharedContext) => void;
  clearSession: () => void;

  // Focus
  focusEntry: (entry: StackEntry | null) => void;

  // Draft lifecycle
  startDraft: () => string; // returns clientId
  updateDraftContent: (content: string) => void;
  updateDraftTitle: (title: string) => void;
  setDraftBloom: (bloom: BloomInference) => void;
  promoteDraftToSaved: (clientId: string, saved: SavedCardState) => void;
  discardDraft: (clientId: string) => void;

  // Saved cards
  addSavedCard: (card: SavedCardState) => void;
  updateSavedCard: (id: number, patch: Partial<SavedCardState>) => void;
  markSavedCardArchived: (id: number, archivedAt: string) => void;
  setSavedCardAnalysis: (id: number, analysis: AnalysisResult | null) => void;
  setSavedCardPhase: (id: number, phase: CardPhase) => void;
  setSavedCardEnrichmentError: (id: number, error: string | null) => void;

  // Cancellation
  registerAbortController: (key: string, controller: AbortController) => void;
  abortKey: (key: string) => void;
  abortAll: () => void;

  // IndexedDB local-first
  persistActiveDraft: () => Promise<void>;
  loadLocalDraft: (
    sessionId: number | null,
    clientId: string,
  ) => Promise<DraftState | null>;
  deleteLocalDraft: (
    sessionId: number | null,
    clientId: string,
  ) => Promise<void>;

  // Reset
  reset: () => void;
};

// ----- Helpers -----

function idbKey(sessionId: number | null, clientId: string): string {
  return `alfred:draft:${sessionId ?? "anon"}:${clientId}`;
}

function uuid(): string {
  // Prefer native crypto.randomUUID when available (modern browsers, Node 19+)
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for older environments. Not cryptographically strong but unique enough.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

// ----- Store -----

export const useZettelWorkspaceStore = create<ZettelWorkspaceState>(
  (set, get) => ({
    sessionId: null,
    sharedContext: { tags: [] },
    savedCards: new Map(),
    activeDraft: null,
    stackOrder: [],
    focusedEntry: null,
    abortControllers: new Map(),

    setSession: (id, shared) =>
      set({
        sessionId: id,
        sharedContext: { ...shared, tags: shared.tags ?? [] },
      }),

    clearSession: () => {
      get().abortAll();
      set({
        sessionId: null,
        sharedContext: { tags: [] },
        savedCards: new Map(),
        activeDraft: null,
        stackOrder: [],
        focusedEntry: null,
        abortControllers: new Map(),
      });
    },

    focusEntry: (entry) => set({ focusedEntry: entry }),

    startDraft: () => {
      const clientId = uuid();
      const now = Date.now();
      const draft: DraftState = {
        clientId,
        content: "",
        title: "",
        bloom: null,
        lastLocalSaveAt: now,
      };
      set((state) => ({
        activeDraft: draft,
        stackOrder: [{ type: "draft", clientId }, ...state.stackOrder],
        focusedEntry: { type: "draft", clientId },
      }));
      return clientId;
    },

    updateDraftContent: (content) =>
      set((state) =>
        state.activeDraft
          ? { activeDraft: { ...state.activeDraft, content } }
          : state,
      ),

    updateDraftTitle: (title) =>
      set((state) =>
        state.activeDraft
          ? { activeDraft: { ...state.activeDraft, title } }
          : state,
      ),

    setDraftBloom: (bloom) =>
      set((state) =>
        state.activeDraft
          ? { activeDraft: { ...state.activeDraft, bloom } }
          : state,
      ),

    promoteDraftToSaved: (clientId, saved) =>
      set((state) => {
        if (!state.activeDraft || state.activeDraft.clientId !== clientId) {
          return state;
        }
        const newSaved = new Map(state.savedCards);
        newSaved.set(saved.id, saved);
        // Replace the draft entry in stackOrder with a saved entry.
        const newStack = state.stackOrder.map((entry) =>
          entry.type === "draft" && entry.clientId === clientId
            ? { type: "saved" as const, id: saved.id }
            : entry,
        );
        // If the focused entry was this draft, migrate the focus to the new saved id.
        const focusedEntry =
          state.focusedEntry &&
          state.focusedEntry.type === "draft" &&
          state.focusedEntry.clientId === clientId
            ? { type: "saved" as const, id: saved.id }
            : state.focusedEntry;
        return {
          savedCards: newSaved,
          activeDraft: null,
          stackOrder: newStack,
          focusedEntry,
        };
      }),

    discardDraft: (clientId) =>
      set((state) => {
        if (!state.activeDraft || state.activeDraft.clientId !== clientId) {
          return state;
        }
        const focusedEntry =
          state.focusedEntry &&
          state.focusedEntry.type === "draft" &&
          state.focusedEntry.clientId === clientId
            ? null
            : state.focusedEntry;
        return {
          activeDraft: null,
          stackOrder: state.stackOrder.filter(
            (entry) =>
              !(entry.type === "draft" && entry.clientId === clientId),
          ),
          focusedEntry,
        };
      }),

    addSavedCard: (card) =>
      set((state) => {
        const newSaved = new Map(state.savedCards);
        newSaved.set(card.id, card);
        // Insert at top of stack if not already present
        const alreadyInStack = state.stackOrder.some(
          (e) => e.type === "saved" && e.id === card.id,
        );
        const newStack = alreadyInStack
          ? state.stackOrder
          : [{ type: "saved" as const, id: card.id }, ...state.stackOrder];
        return { savedCards: newSaved, stackOrder: newStack };
      }),

    updateSavedCard: (id, patch) =>
      set((state) => {
        const existing = state.savedCards.get(id);
        if (!existing) return state;
        const newSaved = new Map(state.savedCards);
        newSaved.set(id, { ...existing, ...patch });
        return { savedCards: newSaved };
      }),

    markSavedCardArchived: (id, archivedAt) => {
      const update = get().updateSavedCard;
      update(id, { archivedAt });
    },

    setSavedCardAnalysis: (id, analysis) => {
      const update = get().updateSavedCard;
      update(id, { analysis });
    },

    setSavedCardPhase: (id, phase) => {
      const update = get().updateSavedCard;
      update(id, { phase });
    },

    setSavedCardEnrichmentError: (id, error) => {
      const update = get().updateSavedCard;
      update(id, { enrichmentLastError: error });
    },

    registerAbortController: (key, controller) =>
      set((state) => {
        // If one already exists for this key, abort it first (caller intent is to replace)
        const existing = state.abortControllers.get(key);
        if (existing) {
          try {
            existing.abort();
          } catch {
            // noop
          }
        }
        const next = new Map(state.abortControllers);
        next.set(key, controller);
        return { abortControllers: next };
      }),

    abortKey: (key) =>
      set((state) => {
        const existing = state.abortControllers.get(key);
        if (!existing) return state;
        try {
          existing.abort();
        } catch {
          // noop
        }
        const next = new Map(state.abortControllers);
        next.delete(key);
        return { abortControllers: next };
      }),

    abortAll: () =>
      set((state) => {
        for (const controller of state.abortControllers.values()) {
          try {
            controller.abort();
          } catch {
            // noop
          }
        }
        return { abortControllers: new Map() };
      }),

    persistActiveDraft: async () => {
      const state = get();
      if (!state.activeDraft) return;
      const draft = state.activeDraft;
      // Skip the noise writes: too-short content isn't worth persisting.
      if (draft.content.trim().length < 10) return;
      try {
        await idbSet(idbKey(state.sessionId, draft.clientId), {
          ...draft,
          lastLocalSaveAt: Date.now(),
        });
        set((s) =>
          s.activeDraft && s.activeDraft.clientId === draft.clientId
            ? {
                activeDraft: {
                  ...s.activeDraft,
                  lastLocalSaveAt: Date.now(),
                },
              }
            : s,
        );
      } catch (err) {
        // IDB can fail in private-browsing or storage-full situations.
        // Don't crash the editor over a mirror failure.
        console.warn("persistActiveDraft: IDB write failed", err);
      }
    },

    loadLocalDraft: async (sessionId, clientId) => {
      try {
        const stored = await idbGet<DraftState>(idbKey(sessionId, clientId));
        return stored ?? null;
      } catch (err) {
        console.warn("loadLocalDraft: IDB read failed", err);
        return null;
      }
    },

    deleteLocalDraft: async (sessionId, clientId) => {
      try {
        await del(idbKey(sessionId, clientId));
      } catch (err) {
        console.warn("deleteLocalDraft: IDB delete failed", err);
      }
    },

    reset: () => {
      get().abortAll();
      set({
        sessionId: null,
        sharedContext: { tags: [] },
        savedCards: new Map(),
        activeDraft: null,
        stackOrder: [],
        focusedEntry: null,
        abortControllers: new Map(),
      });
    },
  }),
);
