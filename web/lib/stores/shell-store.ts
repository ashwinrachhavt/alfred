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
  openToolPanel: (type: ToolPanelType, props?: Record<string, unknown>) => void;
  closeToolPanel: () => void;
};

export const useShellStore = create<ShellState>((set) => ({
  aiPanelOpen: false,
  toolPanel: null,
  toggleAiPanel: () => set((s) => ({ aiPanelOpen: !s.aiPanelOpen })),
  openToolPanel: (type, props = {}) => set({ toolPanel: { type, props } }),
  closeToolPanel: () => set({ toolPanel: null }),
}));
