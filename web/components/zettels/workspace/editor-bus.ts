"use client";

/**
 * Tiny pub/sub so the AmbientIntelligencePanel can insert content into the
 * active WritingSurface editor without having to thread refs through the
 * workspace tree.
 */

type InsertListener = (text: string) => void;

const listeners = new Set<InsertListener>();

export function subscribeEditorInsert(fn: InsertListener): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function publishEditorInsert(text: string): void {
  for (const fn of listeners) fn(text);
}
