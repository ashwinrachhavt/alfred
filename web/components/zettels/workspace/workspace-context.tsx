"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

/**
 * Tiny context used by the workspace so the AmbientIntelligencePanel's
 * "Review split" CTA can open the DecompositionReviewUI, and so the
 * WritingSurface's paste-heuristic can also toggle it.
 */
type DecompositionPayload = {
  rawText: string;
};

type WorkspaceContextValue = {
  decomposition: DecompositionPayload | null;
  openDecomposition: (payload: DecompositionPayload) => void;
  closeDecomposition: () => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [decomposition, setDecomposition] = useState<DecompositionPayload | null>(null);

  const openDecomposition = useCallback((payload: DecompositionPayload) => {
    setDecomposition(payload);
  }, []);
  const closeDecomposition = useCallback(() => setDecomposition(null), []);

  const value = useMemo<WorkspaceContextValue>(
    () => ({ decomposition, openDecomposition, closeDecomposition }),
    [decomposition, openDecomposition, closeDecomposition],
  );

  return (
    <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext(): WorkspaceContextValue {
  const v = useContext(WorkspaceContext);
  if (!v) {
    throw new Error("useWorkspaceContext must be used inside <WorkspaceProvider>");
  }
  return v;
}
