import { create } from "zustand";

export type ToolPanelType = "notes" | "document" | "connectors" | "quiz" | "writing";

type ToolPanel = {
  type: ToolPanelType;
  props: Record<string, unknown>;
};

type ShellState = {
  aiPanelOpen: boolean;
  toolPanel: ToolPanel | null;
  toggleAiPanel: () => void;
  setAiPanelOpen: (open: boolean) => void;
  openToolPanel: (type: ToolPanelType, props?: Record<string, unknown>) => void;
  closeToolPanel: () => void;
};

export const useShellStore = create<ShellState>((set) => ({
  aiPanelOpen: false,
  toolPanel: null,
  toggleAiPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen })),
  setAiPanelOpen: (open) => set({ aiPanelOpen: open }),
  openToolPanel: (type, props = {}) => set({ toolPanel: { type, props } }),
  closeToolPanel: () => set({ toolPanel: null }),
}));
