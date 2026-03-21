import { create } from "zustand";

type ViewFilter = "all" | "documents" | "concepts" | "zettels";

type CanvasState = {
  activeCanvasId: string | null;
  aiSuggestEnabled: boolean;
  selectedNodeIds: string[];
  viewFilter: ViewFilter;
  setActiveCanvas: (id: string) => void;
  toggleAiSuggest: () => void;
  setViewFilter: (f: ViewFilter) => void;
  selectNodes: (ids: string[]) => void;
};

export const useCanvasStore = create<CanvasState>((set) => ({
  activeCanvasId: null,
  aiSuggestEnabled: false,
  selectedNodeIds: [],
  viewFilter: "all",
  setActiveCanvas: (id) => set({ activeCanvasId: id }),
  toggleAiSuggest: () => set((s) => ({ aiSuggestEnabled: !s.aiSuggestEnabled })),
  setViewFilter: (f) => set({ viewFilter: f }),
  selectNodes: (ids) => set({ selectedNodeIds: ids }),
}));
