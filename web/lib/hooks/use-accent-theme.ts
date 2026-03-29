"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

export const ACCENT_THEMES = [
  { id: "terracotta", label: "Terracotta", color: "#E8590C" },
  { id: "sage", label: "Sage", color: "#5B8A72" },
  { id: "amber", label: "Amber", color: "#C28B2D" },
  { id: "crimson", label: "Crimson", color: "#B83A3A" },
  { id: "indigo", label: "Indigo", color: "#5B6ABF" },
  { id: "copper", label: "Copper", color: "#B87343" },
] as const;

export type AccentThemeId = (typeof ACCENT_THEMES)[number]["id"];

const STORAGE_KEY = "alfred-accent-theme";
const DEFAULT_ACCENT: AccentThemeId = "terracotta";

let listeners: Array<() => void> = [];

function getSnapshot(): AccentThemeId {
  if (typeof window === "undefined") return DEFAULT_ACCENT;
  return (document.documentElement.getAttribute("data-accent") as AccentThemeId) || DEFAULT_ACCENT;
}

function getServerSnapshot(): AccentThemeId {
  return DEFAULT_ACCENT;
}

function subscribe(listener: () => void): () => void {
  listeners.push(listener);
  return () => {
    listeners = listeners.filter((l) => l !== listener);
  };
}

function emitChange() {
  for (const listener of listeners) listener();
}

export function setAccentTheme(accent: AccentThemeId) {
  if (accent === "terracotta") {
    document.documentElement.removeAttribute("data-accent");
  } else {
    document.documentElement.setAttribute("data-accent", accent);
  }
  try {
    localStorage.setItem(STORAGE_KEY, accent);
  } catch {
    // localStorage unavailable
  }
  emitChange();
}

export function useAccentTheme() {
  const accent = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // Initialize from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as AccentThemeId | null;
      if (stored && ACCENT_THEMES.some((t) => t.id === stored)) {
        setAccentTheme(stored);
      }
    } catch {
      // localStorage unavailable
    }
  }, []);

  const set = useCallback((id: AccentThemeId) => {
    setAccentTheme(id);
  }, []);

  return { accent, setAccent: set, themes: ACCENT_THEMES };
}
