"use client";

/**
 * WorkspaceShell (T10)
 *
 * Composes the three-zone Zettel workspace layout. Seeds the Zustand store
 * from server-side hydration, ensures an active draft is present, and mounts
 * the DecompositionReviewUI inside <WorkspaceProvider>.
 */

import { useEffect } from "react";

import { cn } from "@/lib/utils";
import {
  useZettelWorkspaceStore,
  type BloomLevel as StoreBloomLevel,
  type BloomSource,
  type SavedCardState,
} from "@/lib/stores/zettel-workspace-store";
import type {
  HydrateResponse,
  ZettelCardOut,
  ZettelCardStub,
} from "@/lib/api/workspace";

import { SessionHeader } from "@/components/zettels/workspace/session-header";
import { SessionRail } from "@/components/zettels/workspace/session-rail";
import { WritingSurface } from "@/components/zettels/workspace/writing-surface";
import { AmbientIntelligencePanel } from "@/components/zettels/workspace/ambient-intelligence-panel";
import { WorkspaceProvider } from "@/components/zettels/workspace/workspace-context";
import { DecompositionReviewUI } from "@/components/zettels/workspace/decomposition-review";

type Props = {
  sessionId: number;
  initialHydration: HydrateResponse;
};

function clampBloom(value: number | null | undefined): StoreBloomLevel {
  const n = Number(value);
  if (n >= 1 && n <= 6) return n as StoreBloomLevel;
  return 1;
}

function coerceBloomSource(value: unknown): BloomSource {
  if (
    value === "backfill" ||
    value === "ai_inferred" ||
    value === "user_set" ||
    value === "review_updated"
  ) {
    return value;
  }
  return "ai_inferred";
}

function buildSavedState(card: ZettelCardOut): SavedCardState {
  const lastSavedSource = card.updated_at ?? card.created_at;
  const lastSavedAt = lastSavedSource ? Date.parse(lastSavedSource) : Date.now();
  return {
    id: card.id,
    phase: "ready",
    content: card.content ?? "",
    title: card.title,
    bloom: {
      inferredLevel: clampBloom(card.bloom_level ?? 1),
      source: coerceBloomSource(card.bloom_source),
    },
    analysis: {
      generatedAtWordCount: 0,
      connections: [],
      enrichment: null,
      decomposition: null,
      bloomQuestions: [],
    },
    enrichmentLastError: card.enrichment_last_error ?? null,
    archivedAt: null,
    lastSavedAt: Number.isFinite(lastSavedAt) ? lastSavedAt : Date.now(),
  };
}

function buildStubState(stub: ZettelCardStub): SavedCardState {
  const lastSavedSource = stub.updated_at ?? stub.created_at;
  const lastSavedAt = lastSavedSource ? Date.parse(lastSavedSource) : Date.now();
  return {
    id: stub.id,
    phase: "ready",
    content: "",
    title: stub.title,
    bloom: {
      inferredLevel: clampBloom(stub.bloom_level),
      source: "backfill",
    },
    analysis: {
      generatedAtWordCount: 0,
      connections: [],
      enrichment: null,
      decomposition: null,
      bloomQuestions: [],
    },
    enrichmentLastError: null,
    archivedAt: stub.is_archived
      ? (stub.updated_at ?? new Date().toISOString())
      : null,
    lastSavedAt: Number.isFinite(lastSavedAt) ? lastSavedAt : Date.now(),
  };
}

export function WorkspaceShell({ sessionId, initialHydration }: Props) {
  const setSession = useZettelWorkspaceStore((s) => s.setSession);
  const addSavedCard = useZettelWorkspaceStore((s) => s.addSavedCard);
  const startDraft = useZettelWorkspaceStore((s) => s.startDraft);
  const updateDraftContent = useZettelWorkspaceStore(
    (s) => s.updateDraftContent,
  );
  const updateDraftTitle = useZettelWorkspaceStore((s) => s.updateDraftTitle);
  const reset = useZettelWorkspaceStore((s) => s.reset);

  // Seed the store from initial hydration once per session.
  useEffect(() => {
    const { session, full_cards, stub_cards } = initialHydration;
    setSession(sessionId, {
      topic: session.shared_topic ?? undefined,
      tags: session.shared_tags ?? [],
      sourceContext: session.source_context ?? undefined,
    });
    for (const card of full_cards) addSavedCard(buildSavedState(card));
    for (const stub of stub_cards) addSavedCard(buildStubState(stub));

    // Ensure an active draft exists after seeding.
    const { activeDraft } = useZettelWorkspaceStore.getState();
    if (!activeDraft) startDraft();

    // One-shot seed hand-off (e.g. from the inbox "Create More" flow).
    // Consume the key once so a refresh doesn't re-seed.
    if (typeof window !== "undefined") {
      const seedKey = `workspace.seedForSession:${sessionId}`;
      const raw = window.sessionStorage.getItem(seedKey);
      if (raw) {
        try {
          const parsed = JSON.parse(raw) as {
            title?: string;
            content?: string;
          };
          if (parsed.title) updateDraftTitle(parsed.title);
          if (parsed.content) updateDraftContent(parsed.content);
        } catch {
          // malformed seed — ignore
        }
        window.sessionStorage.removeItem(seedKey);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Reset on unmount so navigating away doesn't leak state into the next sitting.
  useEffect(() => {
    return () => {
      reset();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <WorkspaceProvider>
      <div className="flex min-h-screen flex-col">
        <SessionHeader session={initialHydration.session} />
        <div className="flex flex-1 overflow-hidden">
          <SessionRail
            className={cn(
              "w-60 border-r border-[var(--alfred-ruled-line)]",
            )}
          />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[720px] px-8 py-10">
              <WritingSurface />
            </div>
          </main>
          <AmbientIntelligencePanel
            className={cn(
              "w-80 border-l border-[var(--alfred-ruled-line)]",
            )}
          />
        </div>
        <DecompositionReviewUI />
      </div>
    </WorkspaceProvider>
  );
}

export default WorkspaceShell;
