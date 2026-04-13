import { create } from "zustand";

// --- Types ---

type StreamPhase = "idle" | "streaming" | "complete" | "error";

type LinkSuggestion = {
  card_id: number;
  title: string;
  score: number;
  reason: string;
};

type CreatedLink = {
  id: number;
  source_id: number;
  target_id: number;
  type: string;
};

type Enrichment = {
  suggested_title: string | null;
  summary: string | null;
  suggested_tags: string[];
  suggested_topic: string | null;
};

type Decomposition = {
  is_atomic: boolean;
  reason: string;
  suggested_cards: { title: string; content: string }[];
};

type Gaps = {
  missing_topics: string[];
  weak_areas: { topic: string; existing_count: number; note: string }[];
};

type CompletedSteps = {
  card_saved: boolean;
  embedding_done: boolean;
  links_searched: boolean;
  ai_complete: boolean;
};

// --- State ---

type ZettelCreationState = {
  phase: StreamPhase;
  cardId: number | null;
  cardTitle: string;

  thinkingBuffer: string;
  steps: CompletedSteps;

  enrichment: Enrichment | null;
  linkSuggestions: LinkSuggestion[];
  createdLinks: CreatedLink[];
  decomposition: Decomposition | null;
  gaps: Gaps | null;
  finalCard: Record<string, unknown> | null;

  acceptedEnrichments: Set<string>;
  rejectedLinkIds: Set<number>;
  errors: { step: string; message: string }[];
};

type ZettelCreationActions = {
  startStream: () => void;
  handleEvent: (event: string, data: Record<string, unknown>) => void;
  toggleEnrichment: (key: string) => void;
  toggleLink: (linkId: number) => void;
  reset: () => void;
};

// --- Initial State ---

const initialState: ZettelCreationState = {
  phase: "idle",
  cardId: null,
  cardTitle: "",
  thinkingBuffer: "",
  steps: {
    card_saved: false,
    embedding_done: false,
    links_searched: false,
    ai_complete: false,
  },
  enrichment: null,
  linkSuggestions: [],
  createdLinks: [],
  decomposition: null,
  gaps: null,
  finalCard: null,
  acceptedEnrichments: new Set(["title", "summary", "tags", "topic"]),
  rejectedLinkIds: new Set(),
  errors: [],
};

// --- Token Buffer ---
// Buffer thinking tokens for 80ms to reduce re-renders.

let thinkingFlushTimer: ReturnType<typeof setTimeout> | null = null;
let pendingThinking = "";

function flushThinking(
  set: (fn: (s: ZettelCreationState) => Partial<ZettelCreationState>) => void,
) {
  if (!pendingThinking) return;
  const chunk = pendingThinking;
  pendingThinking = "";
  set((s) => ({ thinkingBuffer: s.thinkingBuffer + chunk }));
}

// --- Store ---

export const useZettelCreationStore = create<
  ZettelCreationState & ZettelCreationActions
>((set) => ({
  ...initialState,

  startStream: () => {
    set({ ...initialState, phase: "streaming" });
  },

  handleEvent: (event, data) => {
    switch (event) {
      case "card_saved":
        set({
          cardId: data.id as number,
          cardTitle: data.title as string,
          steps: { ...initialState.steps, card_saved: true },
        });
        break;

      case "thinking":
        pendingThinking += (data.content as string) || "";
        if (!thinkingFlushTimer) {
          thinkingFlushTimer = setTimeout(() => {
            thinkingFlushTimer = null;
            flushThinking(set);
          }, 80);
        }
        break;

      case "embedding_done":
        set((s) => ({ steps: { ...s.steps, embedding_done: true } }));
        break;

      case "tool_start":
        break;

      case "links_found":
        set((s) => ({
          linkSuggestions: data.suggestions as LinkSuggestion[],
          steps: { ...s.steps, links_searched: true },
        }));
        break;

      case "links_created":
        set({ createdLinks: data.links as CreatedLink[] });
        break;

      case "enrichment":
        set((s) => ({
          enrichment: data as unknown as Enrichment,
          steps: { ...s.steps, ai_complete: true },
        }));
        break;

      case "decomposition":
        set({ decomposition: data as unknown as Decomposition });
        break;

      case "gaps":
        set({ gaps: data as unknown as Gaps });
        break;

      case "done":
        if (pendingThinking) flushThinking(set);
        set({
          phase: "complete",
          finalCard: data.card as Record<string, unknown>,
        });
        break;

      case "error":
        set((s) => ({
          errors: [
            ...s.errors,
            {
              step: data.step as string,
              message: data.message as string,
            },
          ],
        }));
        break;
    }
  },

  toggleEnrichment: (key) => {
    set((s) => {
      const next = new Set(s.acceptedEnrichments);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return { acceptedEnrichments: next };
    });
  },

  toggleLink: (linkId) => {
    set((s) => {
      const next = new Set(s.rejectedLinkIds);
      if (next.has(linkId)) next.delete(linkId);
      else next.add(linkId);
      return { rejectedLinkIds: next };
    });
  },

  reset: () => {
    pendingThinking = "";
    if (thinkingFlushTimer) {
      clearTimeout(thinkingFlushTimer);
      thinkingFlushTimer = null;
    }
    set(initialState);
  },
}));
