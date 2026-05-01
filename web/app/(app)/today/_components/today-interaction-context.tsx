"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/**
 * What the drawer is currently showing:
 *   - ``null`` — closed
 *   - ``"create"`` — create-mode for a brand-new entry
 *   - ``number`` — edit-mode for a persisted DailyEntry row id
 *
 * Synthetic (artifact_ref) ids are strings like ``"zettel:123"`` — those rows
 * are not editable, so the drawer never opens for them.
 */
export type DrawerTarget = null | "create" | number;

export interface TodayInteractionValue {
  drawerTarget: DrawerTarget;
  commandBarOpen: boolean;
  openEntry: (id: number) => void;
  openCreate: () => void;
  closeDrawer: () => void;
  openCommandBar: () => void;
  closeCommandBar: () => void;
  toggleCommandBar: () => void;
}

const TodayInteractionContext = createContext<TodayInteractionValue | null>(null);

export function TodayInteractionProvider({ children }: { children: ReactNode }) {
  const [drawerTarget, setDrawerTarget] = useState<DrawerTarget>(null);
  const [commandBarOpen, setCommandBarOpen] = useState(false);

  const value = useMemo<TodayInteractionValue>(
    () => ({
      drawerTarget,
      commandBarOpen,
      openEntry: (id) => setDrawerTarget(id),
      openCreate: () => setDrawerTarget("create"),
      closeDrawer: () => setDrawerTarget(null),
      openCommandBar: () => setCommandBarOpen(true),
      closeCommandBar: () => setCommandBarOpen(false),
      toggleCommandBar: () => setCommandBarOpen((v) => !v),
    }),
    [drawerTarget, commandBarOpen],
  );

  return (
    <TodayInteractionContext.Provider value={value}>{children}</TodayInteractionContext.Provider>
  );
}

export function useTodayInteraction(): TodayInteractionValue {
  const ctx = useContext(TodayInteractionContext);
  if (!ctx) {
    throw new Error("useTodayInteraction must be used inside <TodayInteractionProvider>");
  }
  return ctx;
}
