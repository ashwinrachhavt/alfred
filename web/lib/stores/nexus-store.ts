"use client";

import { create } from "zustand";

type PathMode = "idle" | "picking-start" | "picking-end" | "showing";
type FocusMode = "all" | "neighborhood";

type PathState = {
  mode: PathMode;
  fromId: number | null;
  toId: number | null;
  result: number[] | null;
};

export type NexusUIState = {
  selectedId: number | null;
  hoveredId: number | null;
  activeEdgeTypes: Set<string>;
  activeTopic: string | null;
  focusMode: FocusMode;
  minDegree: number;
  showClusterHulls: boolean;
  path: PathState;

  setSelected: (id: number | null) => void;
  setHovered: (id: number | null) => void;
  toggleEdgeType: (t: string) => void;
  setEdgeTypes: (types: string[]) => void;
  setActiveTopic: (topic: string | null) => void;
  setFocusMode: (mode: FocusMode) => void;
  setMinDegree: (degree: number) => void;
  clearGraphFilters: () => void;
  toggleClusterHulls: () => void;
  startPathPick: () => void;
  pickPathNode: (id: number) => void;
  setPathResult: (ids: number[] | null) => void;
  resetPath: () => void;
};

export const useNexusStore = create<NexusUIState>((set, get) => ({
  selectedId: null,
  hoveredId: null,
  activeEdgeTypes: new Set(),
  activeTopic: null,
  focusMode: "all",
  minDegree: 0,
  showClusterHulls: true,
  path: { mode: "idle", fromId: null, toId: null, result: null },

  setSelected: (id) => set({ selectedId: id }),
  setHovered: (id) => set({ hoveredId: id }),

  toggleEdgeType: (t) =>
    set((s) => {
      const next = new Set(s.activeEdgeTypes);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return { activeEdgeTypes: next };
    }),

  setEdgeTypes: (types) => set({ activeEdgeTypes: new Set(types) }),

  setActiveTopic: (topic) => set({ activeTopic: topic }),
  setFocusMode: (mode) => set({ focusMode: mode }),
  setMinDegree: (degree) => set({ minDegree: degree }),
  clearGraphFilters: () =>
    set({
      activeEdgeTypes: new Set(),
      activeTopic: null,
      focusMode: "all",
      minDegree: 0,
    }),

  toggleClusterHulls: () =>
    set((s) => ({ showClusterHulls: !s.showClusterHulls })),

  startPathPick: () =>
    set({
      path: { mode: "picking-start", fromId: null, toId: null, result: null },
    }),

  pickPathNode: (id) => {
    const { path } = get();
    if (path.mode === "picking-start") {
      set({ path: { ...path, mode: "picking-end", fromId: id } });
    } else if (path.mode === "picking-end") {
      set({ path: { ...path, mode: "showing", toId: id } });
    }
  },

  setPathResult: (ids) =>
    set((s) => ({
      path: { ...s.path, result: ids, mode: ids ? "showing" : "idle" },
    })),

  resetPath: () =>
    set({
      path: { mode: "idle", fromId: null, toId: null, result: null },
    }),
}));
