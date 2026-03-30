"use client";

import { useRef, useState } from "react";

import { OrbitControls, Stars } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import { getSemanticMap } from "@/lib/api/documents";
import type { SemanticMapPoint } from "@/lib/api/types/documents";
import { cn } from "@/lib/utils";
import { useSemanticMap, semanticMapQueryKey } from "@/features/documents/queries";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { GalaxyCameraRig } from "./galaxy-camera-rig";
import { GalaxyStarField } from "./galaxy-starfield";

function GalaxyWarpLoading() {
 return (
 <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl">
 <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/60 to-black/80" />
 <div className="absolute inset-0 [mask-image:radial-gradient(circle_at_center,black,transparent_65%)]">
 <div className="absolute -inset-24 opacity-60">
 <div className="h-[200%] w-full animate-[atheneum-warp_1.15s_linear_infinite] bg-[repeating-linear-gradient(90deg,rgba(255,255,255,0.10)_0,rgba(255,255,255,0.10)_1px,transparent_1px,transparent_18px)]" />
 </div>
 </div>
 <div className="absolute inset-0 flex items-center justify-center">
 <div className="bg-background/20 text-foreground/90 border-border/30 rounded-full border px-4 py-2 text-sm backdrop-blur">
 Entering hyperspace…
 </div>
 </div>
 </div>
 );
}

export function GalaxyView({
 active,
 onOpenDocument,
 className,
}: {
 active: boolean;
 onOpenDocument: (id: string) => void;
 className?: string;
}) {
 const queryClient = useQueryClient();
 const [focused, setFocused] = useState<SemanticMapPoint | null>(null);
 const [hovered, setHovered] = useState<SemanticMapPoint | null>(null);
 const [refreshing, setRefreshing] = useState(false);

 const semanticQuery = useSemanticMap({ enabled: active, limit: 5000 });
 const points = semanticQuery.data?.points ?? [];

 const controlsRef = useRef<OrbitControlsImpl | null>(null);

 const hasPoints = points.length > 0;
 const focusPos = focused ? focused.pos : null;

 return (
 <div
 className={cn(
 "relative overflow-hidden rounded-xl border bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900",
 "min-h-[70vh]",
 className,
 )}
 >
 {semanticQuery.isLoading ? <GalaxyWarpLoading /> : null}

 <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between gap-3 p-4">
 <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-2 text-xs backdrop-blur">
 <span className="text-white/80">Semantic Galaxy</span>
 <Badge variant="secondary" className="bg-white/10 text-white">
 {hasPoints ?`${points.length.toLocaleString()} stars` : "—"}
 </Badge>
 </div>

 <div className="pointer-events-auto flex items-center gap-2">
 <Button
 type="button"
 size="sm"
 variant="outline"
 className="border-white/15 bg-black/20 text-white hover:bg-black/35"
 disabled={!active || semanticQuery.isLoading || refreshing}
 onClick={async () => {
 try {
 setRefreshing(true);
 const data = await getSemanticMap({ limit: 5000, refresh: true });
 queryClient.setQueryData(semanticMapQueryKey(5000), data);
 } finally {
 setRefreshing(false);
 }
 }}
 >
 <RefreshCw className={cn("h-4 w-4", refreshing ? "animate-spin" : "")} />
 Refresh
 </Button>
 </div>
 </div>

 <div className="absolute inset-0">
 {active ? (
 <Canvas
 dpr={[1, 1.5]}
 gl={{ antialias: false, powerPreference: "high-performance" }}
 camera={{ position: [0, 0, 3], fov: 58, near: 0.01, far: 100 }}
 >
 <color attach="background" args={["#020617"]} />
 <fog attach="fog" args={["#020617", 2, 10]} />

 <ambientLight intensity={0.9} />

 <Stars radius={50} depth={40} count={2000} factor={4} saturation={0} fade speed={1} />

 {hasPoints ? (
 <GalaxyStarField
 points={points}
 focusedId={focused?.id ?? null}
 onFocus={(p) => setFocused(p)}
 onHover={(p) => setHovered(p)}
 />
 ) : null}

 <OrbitControls
 ref={(instance) => {
 controlsRef.current = instance;
 }}
 enableDamping
 dampingFactor={0.12}
 rotateSpeed={0.55}
 zoomSpeed={0.8}
 panSpeed={0.8}
 minDistance={0.7}
 maxDistance={12}
 />
 <GalaxyCameraRig controlsRef={controlsRef} focus={focusPos} />
 </Canvas>
 ) : null}
 </div>

 <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-4">
 <div className="pointer-events-auto flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-white/85 backdrop-blur">
 <div className="min-w-0">
 <p className="truncate">
 {hovered
 ? hovered.label
 : focused
 ? focused.label
 : "Hover a star to reveal its title."}
 </p>
 <p className="text-white/60">Drag to orbit • Scroll to zoom • Click to focus</p>
 </div>

 {focused ? (
 <div className="flex shrink-0 items-center gap-2">
 <Badge variant="secondary" className="bg-white/10 text-white">
 {focused.primary_topic || "untagged"}
 </Badge>
 <Button
 type="button"
 size="sm"
 className="pointer-events-auto"
 onClick={() => onOpenDocument(focused.id)}
 >
 Quick Look
 </Button>
 </div>
 ) : null}
 </div>
 </div>

 {semanticQuery.isError ? (
 <div className="absolute inset-0 grid place-items-center p-6">
 <div className="bg-background/70 text-foreground border-border/40 w-full max-w-md rounded-xl border p-4 backdrop-blur">
 <p className="text-sm font-medium">Failed to load the semantic map.</p>
 <p className="text-muted-foreground mt-1 text-xs">
 {semanticQuery.error instanceof Error ? semanticQuery.error.message : "Unknown error"}
 </p>
 </div>
 </div>
 ) : null}
 </div>
 );
}
