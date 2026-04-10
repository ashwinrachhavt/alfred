import { create } from "zustand";

export type UniverseState = {
  selectedNodeIds: number[];
  hoveredNodeId: number | null;
  cameraTarget: { x: number; y: number; z: number } | null;
  searchQuery: string;
  audioEnabled: boolean;
  isTimeLapsePlaying: boolean;

  selectNode: (id: number) => void;
  deselectNode: (id: number) => void;
  clearSelection: () => void;
  setHoveredNode: (id: number | null) => void;
  setCameraTarget: (pos: { x: number; y: number; z: number } | null) => void;
  setSearchQuery: (q: string) => void;
  toggleAudio: () => void;
  setTimeLapsePlaying: (playing: boolean) => void;
};

export const useUniverseStore = create<UniverseState>((set, get) => ({
  selectedNodeIds: [],
  hoveredNodeId: null,
  cameraTarget: null,
  searchQuery: "",
  audioEnabled: false,
  isTimeLapsePlaying: false,

  selectNode: (id) => {
    const { selectedNodeIds } = get();
    if (selectedNodeIds.includes(id)) return;
    if (selectedNodeIds.length >= 5) return;
    set({ selectedNodeIds: [...selectedNodeIds, id] });
  },
  deselectNode: (id) => {
    set((s) => ({ selectedNodeIds: s.selectedNodeIds.filter((n) => n !== id) }));
  },
  clearSelection: () => set({ selectedNodeIds: [], hoveredNodeId: null, cameraTarget: null }),
  setHoveredNode: (id) => set({ hoveredNodeId: id }),
  setCameraTarget: (pos) => set({ cameraTarget: pos }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  toggleAudio: () => set((s) => ({ audioEnabled: !s.audioEnabled })),
  setTimeLapsePlaying: (playing) => set({ isTimeLapsePlaying: playing }),
}));
