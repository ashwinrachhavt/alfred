"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useExtendedGraph } from "@/features/universe/queries";
import { WebGLErrorBoundary } from "./_components/webgl-error-boundary";

const KnowledgeUniverse = dynamic(
  () => import("./_components/knowledge-universe").then((m) => m.KnowledgeUniverse),
  { ssr: false }
);

// Scene overrides the app theme: the universe is always a dark immersive
// backdrop regardless of light/dark mode. Token defined in globals.css.
const SCENE_CLASS = "bg-[var(--alfred-scene-bg)]";
const PRIMARY_BUTTON_CLASS = "bg-primary text-primary-foreground";

export default function UniversePage() {
  const { data, isLoading, error, refetch } = useExtendedGraph();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  if (isMobile) {
    return (
      <div className={`flex h-full items-center justify-center ${SCENE_CLASS} text-white/60`}>
        <p className="max-w-xs text-center font-sans text-base">
          The Knowledge Universe is best experienced on desktop.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`flex h-full flex-col items-center justify-center gap-3 ${SCENE_CLASS}`}>
        <p className="font-sans text-base text-white/60">Couldn&apos;t load your universe.</p>
        <button
          onClick={() => refetch()}
          className={`rounded-md ${PRIMARY_BUTTON_CLASS} px-4 py-2 font-sans text-base`}
        >
          Retry
        </button>
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className={`flex h-full items-center justify-center ${SCENE_CLASS}`}>
        <div className="h-3 w-3 animate-pulse rounded-full bg-primary" />
        <span className="ml-3 font-mono text-base text-white/40">Loading your universe...</span>
      </div>
    );
  }

  if (data.nodes.length === 0) {
    return (
      <div className={`flex h-full flex-col items-center justify-center gap-4 ${SCENE_CLASS}`}>
        <p className="font-sans text-base text-white/60">Your universe is empty.</p>
        <p className="font-sans text-base text-white/30">
          Start by creating your first knowledge card.
        </p>
        <a
          href="/knowledge"
          className={`rounded-md ${PRIMARY_BUTTON_CLASS} px-4 py-2 font-sans text-base`}
        >
          Go to Knowledge Hub
        </a>
      </div>
    );
  }

  return (
    <div className={`relative h-full w-full ${SCENE_CLASS}`}>
      <WebGLErrorBoundary>
        <KnowledgeUniverse data={data} />
      </WebGLErrorBoundary>
    </div>
  );
}
