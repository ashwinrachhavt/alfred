/**
 * /knowledge/session/[sessionId] — server component that hydrates the session
 * on the backend and hands off to the <WorkspaceShell> client component.
 *
 * No auth forwarding yet: Clerk is disabled in this branch and the backend
 * trusts the dev proxy. Wire headers() cookie forwarding when auth returns.
 */

import { notFound, redirect } from "next/navigation";

import type { HydrateResponse } from "@/lib/api/workspace";
import { WorkspaceShell } from "@/components/zettels/workspace/workspace-shell";

type Props = {
  params: Promise<{ sessionId: string }>;
};

function resolveBackendBase(): string {
  // Prefer the server-side var used by next.config rewrites, fall back to the
  // public URL, then to localhost for dev.
  const configured =
    process.env.ALFRED_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://localhost:8000";
  return configured.replace(/\/+$/, "");
}

async function fetchHydration(id: number): Promise<HydrateResponse | null> {
  const base = resolveBackendBase();
  try {
    const response = await fetch(
      `${base}/api/zettels/sessions/${id}/hydrate`,
      { cache: "no-store" },
    );
    if (!response.ok) return null;
    return (await response.json()) as HydrateResponse;
  } catch {
    return null;
  }
}

export default async function WorkspaceSessionPage({ params }: Props) {
  const { sessionId } = await params;
  const id = Number(sessionId);
  if (!Number.isFinite(id) || id <= 0) {
    notFound();
  }

  if (process.env.NEXT_PUBLIC_ZETTEL_WORKSPACE_V2 === "false") {
    redirect("/knowledge");
  }

  const hydration = await fetchHydration(id);
  if (!hydration) {
    notFound();
  }

  return <WorkspaceShell sessionId={id} initialHydration={hydration} />;
}
