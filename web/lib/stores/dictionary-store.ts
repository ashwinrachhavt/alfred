import { create } from "zustand";

import type { DictionaryResult, SaveIntent } from "@/lib/api/dictionary";

type DictionaryState = {
  searchQuery: string;
  currentResult: DictionaryResult | null;
  isLooking: boolean;
  activeTab: "search" | "collection";
  filterIntent: SaveIntent | null;
  filterDomain: string | null;

  setSearchQuery: (query: string) => void;
  setCurrentResult: (result: DictionaryResult | null) => void;
  setIsLooking: (loading: boolean) => void;
  setActiveTab: (tab: "search" | "collection") => void;
  setFilterIntent: (intent: SaveIntent | null) => void;
  setFilterDomain: (domain: string | null) => void;
  reset: () => void;
};

const initialState = {
  searchQuery: "",
  currentResult: null,
  isLooking: false,
  activeTab: "search" as const,
  filterIntent: null,
  filterDomain: null,
};

export const useDictionaryStore = create<DictionaryState>((set) => ({
  ...initialState,
  setSearchQuery: (query) => set({ searchQuery: query }),
  setCurrentResult: (result) => set({ currentResult: result }),
  setIsLooking: (loading) => set({ isLooking: loading }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setFilterIntent: (intent) => set({ filterIntent: intent }),
  setFilterDomain: (domain) => set({ filterDomain: domain }),
  reset: () => set(initialState),
}));
