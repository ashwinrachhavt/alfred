"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import type {
  ExtendedGraphData,
  GraphNode,
  GraphEdge,
} from "@/features/universe/queries";
import { useUniverseStore } from "@/lib/stores/universe-store";
import { CardPreviewOverlay } from "./card-preview-overlay";
import { UniverseControls } from "./universe-controls";
import { AIDiscoveryPanel } from "./ai-discovery-panel";
import { CreateCardForm } from "./create-card-form";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const PARTICLE_COUNT = 1500;
const PARTICLE_SPHERE_RADIUS = 500;
const NEBULA_SETTLE_MS = 6000;
const LARGE_GRAPH_THRESHOLD = 2000;
const HUGE_GRAPH_THRESHOLD = 5000;

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Create a soft radial-gradient sprite texture for cluster nebulae. */
function createNebulaTexture(color: string): THREE.Texture {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, color + "40");
  gradient.addColorStop(0.5, color + "15");
  gradient.addColorStop(1, "transparent");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}

/** Compute heat-glow emissive boost from updated_at recency. */
function recencyBoost(updatedAt: string | null): number {
  if (!updatedAt) return 0;
  const age = Date.now() - new Date(updatedAt).getTime();
  const ONE_DAY = 86_400_000;
  if (age < ONE_DAY) return 0.3;
  if (age < ONE_DAY * 7) return 0.15;
  return 0;
}

/** Check spaced-rep urgency from due_at. */
function dueUrgency(dueAt: string | null): "overdue" | "soon" | null {
  if (!dueAt) return null;
  const diff = new Date(dueAt).getTime() - Date.now();
  if (diff < 0) return "overdue";
  if (diff < 86_400_000) return "soon";
  return null;
}

type Props = { data: ExtendedGraphData };

export function KnowledgeUniverse({ data }: Props) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [showCreateForm, setShowCreateForm] = useState(false);

  /* ---- Time-lapse state ---- */
  const {
    selectedNodeIds,
    selectNode,
    clearSelection,
    setHoveredNode,
    audioEnabled,
    isTimeLapsePlaying,
    setTimeLapsePlaying,
  } = useUniverseStore();

  const [timeLapseDate, setTimeLapseDate] = useState<Date | null>(null);

  /** Whether to skip heavy visual effects (particles / nebulae). */
  const isLargeGraph = data.nodes.length > LARGE_GRAPH_THRESHOLD;
  const isHugeGraph = data.nodes.length > HUGE_GRAPH_THRESHOLD;

  /* ---------------------------------------------------------------- */
  /*  Audio refs (Task 14)                                             */
  /* ---------------------------------------------------------------- */
  const audioCtxRef = useRef<AudioContext | null>(null);
  const oscillatorRef = useRef<OscillatorNode | null>(null);

  // Persist audioEnabled to localStorage
  useEffect(() => {
    localStorage.setItem("universe-audio", audioEnabled ? "on" : "off");
  }, [audioEnabled]);

  // Ambient drone
  useEffect(() => {
    if (!audioEnabled) {
      if (oscillatorRef.current) {
        try {
          oscillatorRef.current.stop();
        } catch {
          /* already stopped */
        }
        oscillatorRef.current = null;
      }
      return;
    }

    if (!audioCtxRef.current) {
      audioCtxRef.current = new AudioContext();
    }
    const ctx = audioCtxRef.current;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 60;
    gain.gain.value = 0.03;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    oscillatorRef.current = osc;

    return () => {
      try {
        osc.stop();
      } catch {
        /* already stopped */
      }
      oscillatorRef.current = null;
    };
  }, [audioEnabled]);

  /** Play a short click blip when a node is selected. */
  const playClickSound = useCallback(() => {
    if (!audioEnabled) return;
    if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
    const ctx = audioCtxRef.current;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 800;
    gain.gain.value = 0.1;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
    osc.stop(ctx.currentTime + 0.06);
  }, [audioEnabled]);

  // Measure container with ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      setDimensions({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Configure force simulation after mount
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;
    fg.d3Force("charge")?.strength(-120);
    fg.d3Force("link")?.distance(50);
  }, [data]);

  /* ---------------------------------------------------------------- */
  /*  Ambient Particle System (skip for large graphs)                  */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!fgRef.current || isLargeGraph) return;
    const scene = fgRef.current.scene();
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT * 3; i++) {
      positions[i] = (Math.random() - 0.5) * PARTICLE_SPHERE_RADIUS * 2;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.3,
      transparent: true,
      opacity: 0.4,
    });
    const pts = new THREE.Points(geo, mat);
    scene.add(pts);
    return () => {
      scene.remove(pts);
      geo.dispose();
      mat.dispose();
    };
  }, [isLargeGraph]);

  /* ---------------------------------------------------------------- */
  /*  Cluster Nebulae (skip for large graphs)                          */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!fgRef.current || isLargeGraph || !data.clusters.length) return;

    const timeout = setTimeout(() => {
      if (!fgRef.current) return;
      const scene = fgRef.current.scene();
      const fgNodes = fgRef.current.graphData().nodes as (GraphNode & {
        x?: number;
        y?: number;
        z?: number;
      })[];

      const sprites: THREE.Sprite[] = [];

      data.clusters.forEach((cluster) => {
        const clusterNodes = fgNodes.filter((n) =>
          cluster.card_ids.includes(n.id),
        );
        if (clusterNodes.length < 2) return;

        // Compute centroid
        let cx = 0,
          cy = 0,
          cz = 0;
        clusterNodes.forEach((n) => {
          cx += n.x ?? 0;
          cy += n.y ?? 0;
          cz += n.z ?? 0;
        });
        cx /= clusterNodes.length;
        cy /= clusterNodes.length;
        cz /= clusterNodes.length;

        // Compute radius as max distance from centroid
        let maxDist = 0;
        clusterNodes.forEach((n) => {
          const dx = (n.x ?? 0) - cx;
          const dy = (n.y ?? 0) - cy;
          const dz = (n.z ?? 0) - cz;
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          if (dist > maxDist) maxDist = dist;
        });

        const tex = createNebulaTexture(cluster.color);
        const spriteMat = new THREE.SpriteMaterial({
          map: tex,
          transparent: true,
          opacity: 0.6,
          depthWrite: false,
        });
        const sprite = new THREE.Sprite(spriteMat);
        sprite.position.set(cx, cy, cz);
        const scale = maxDist * 2.5 || 40;
        sprite.scale.set(scale, scale, 1);
        scene.add(sprite);
        sprites.push(sprite);
      });

      return () => {
        sprites.forEach((s) => {
          s.material.dispose();
          if ((s.material as THREE.SpriteMaterial).map)
            (s.material as THREE.SpriteMaterial).map!.dispose();
          scene.remove(s);
        });
      };
    }, NEBULA_SETTLE_MS);

    return () => clearTimeout(timeout);
  }, [data.clusters, isLargeGraph]);

  /* ---------------------------------------------------------------- */
  /*  Keyboard shortcuts                                               */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;

      if (e.key === "Escape") {
        if (showCreateForm) {
          setShowCreateForm(false);
        } else {
          clearSelection();
        }
      }

      if (e.key === "n" || e.key === "N") {
        setShowCreateForm((prev) => !prev);
      }

      // Space bar toggles time-lapse
      if (e.key === " ") {
        e.preventDefault();
        setTimeLapsePlaying(!isTimeLapsePlaying);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection, showCreateForm, isTimeLapsePlaying, setTimeLapsePlaying]);

  /* ---------------------------------------------------------------- */
  /*  Time-Lapse Mode (Task 13)                                        */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!isTimeLapsePlaying) {
      setTimeLapseDate(null);
      return;
    }

    // Determine date range from nodes
    const dates = data.nodes
      .map((n) => (n.created_at ? new Date(n.created_at).getTime() : null))
      .filter((d): d is number => d !== null)
      .sort((a, b) => a - b);

    if (dates.length === 0) {
      setTimeLapsePlaying(false);
      return;
    }

    const startTime = dates[0];
    const endTime = dates[dates.length - 1];
    const ONE_DAY = 86_400_000;
    let current = startTime;

    setTimeLapseDate(new Date(current));

    const interval = setInterval(() => {
      current += ONE_DAY;
      if (current > endTime) {
        setTimeLapsePlaying(false);
        setTimeLapseDate(null);
        clearInterval(interval);
        return;
      }
      setTimeLapseDate(new Date(current));
    }, 200);

    return () => clearInterval(interval);
  }, [isTimeLapsePlaying, data.nodes, setTimeLapsePlaying]);

  /* ---------------------------------------------------------------- */
  /*  Node rendering with visual polish                                */
  /* ---------------------------------------------------------------- */
  const nodeThreeObject = useCallback(
    (node: any) => {
      const gn = node as GraphNode & { x?: number; y?: number; z?: number };
      const size = Math.max(2, Math.log2((gn.degree || 0) + 1) * 2.5);
      const isStub = gn.status === "stub";
      const isSelected = selectedNodeIds.includes(gn.id);

      // Spaced rep urgency
      const urgency = dueUrgency(gn.due_at);
      // Heat glow from recency
      const heatBoost = recencyBoost(gn.updated_at);

      // Base emissive intensity
      let emissiveIntensity = isSelected ? 0.6 : 0.15;

      // Spaced rep pulse (overdue = warm amber glow, soon = moderate)
      let emissiveColor = isSelected ? 0xe8590c : 0x331100;
      if (urgency === "overdue") {
        emissiveIntensity = 0.8;
        emissiveColor = 0xffaa33; // warm amber
      } else if (urgency === "soon") {
        emissiveIntensity = 0.4;
        emissiveColor = 0xffaa33;
      }

      // Heat glow additive
      emissiveIntensity += heatBoost;

      const geometry = new THREE.SphereGeometry(size, 16, 12);
      const material = new THREE.MeshPhongMaterial({
        color: isStub ? 0x555555 : 0xe8590c,
        wireframe: isStub,
        transparent: true,
        opacity: isSelected ? 1.0 : 0.75,
        emissive: emissiveColor,
        emissiveIntensity,
      });
      return new THREE.Mesh(geometry, material);
    },
    [selectedNodeIds],
  );

  /* ---------------------------------------------------------------- */
  /*  Wormhole edge styling                                            */
  /* ---------------------------------------------------------------- */
  const linkColor = useCallback((link: any) => {
    const edge = link as GraphEdge;
    return edge.type === "ai-suggested" ? "#E8590C" : "#ffffff30";
  }, []);

  const linkWidth = useCallback((link: any) => {
    const edge = link as GraphEdge;
    return edge.type === "ai-suggested" ? 1.5 : 0.5;
  }, []);

  /** For 3D, dashes aren't natively supported — use link particles instead
   *  to distinguish AI-suggested links visually. */
  const linkParticles = useCallback((link: any) => {
    const edge = link as GraphEdge;
    return edge.type === "ai-suggested" ? 3 : 0;
  }, []);

  const linkParticleWidth = useCallback((link: any) => {
    const edge = link as GraphEdge;
    return edge.type === "ai-suggested" ? 1.5 : 0;
  }, []);

  // Click handlers (with sound)
  const handleNodeClick = useCallback(
    (node: any, event: MouseEvent) => {
      playClickSound();
      if (event.shiftKey) {
        selectNode(node.id);
      } else {
        clearSelection();
        selectNode(node.id);
      }
    },
    [selectNode, clearSelection, playClickSound],
  );

  /* ---------------------------------------------------------------- */
  /*  Graph data — apply time-lapse filter if active                   */
  /* ---------------------------------------------------------------- */
  const graphData = useMemo(() => {
    let filteredNodes = data.nodes;

    // Time-lapse: only show nodes created before the playback date
    if (timeLapseDate) {
      const cutoff = timeLapseDate.getTime();
      filteredNodes = data.nodes.filter((n) => {
        if (!n.created_at) return true; // show nodes without dates
        return new Date(n.created_at).getTime() <= cutoff;
      });
    }

    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = data.edges.filter(
      (e) => nodeIds.has(e.source as any) && nodeIds.has(e.target as any),
    );

    return {
      nodes: filteredNodes.map((n) => ({ ...n })),
      links: filteredEdges.map((e) => ({ ...e })),
    };
  }, [data, timeLapseDate]);

  /* ---------------------------------------------------------------- */
  /*  Huge graph bail-out                                              */
  /* ---------------------------------------------------------------- */
  if (isHugeGraph) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 bg-[#0F0E0D]">
        <p className="font-sans text-sm text-white/60">
          Too many cards ({data.nodes.length}) for the 3D view.
        </p>
        <a
          href="/knowledge"
          className="rounded-md bg-[#E8590C] px-4 py-2 font-sans text-xs text-white"
        >
          View in Knowledge Hub
        </a>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden">
      {/* Large graph warning banner */}
      {isLargeGraph && (
        <div className="absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full border border-white/10 bg-black/60 px-4 py-1.5 backdrop-blur-sm">
          <span className="font-mono text-[10px] text-white/50">
            Large graph — some visual effects reduced
          </span>
        </div>
      )}

      {/* Time-lapse date display */}
      {timeLapseDate && (
        <div className="absolute left-1/2 top-14 z-20 -translate-x-1/2 rounded-full border border-[#E8590C]/30 bg-black/60 px-4 py-1.5 backdrop-blur-sm">
          <span className="font-mono text-[10px] text-[#E8590C]">
            {timeLapseDate.toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}{" "}
            — {graphData.nodes.length} / {data.nodes.length} cards
          </span>
        </div>
      )}

      {/* 3D Force Graph */}
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0F0E0D"
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        onNodeClick={handleNodeClick}
        onNodeHover={(node: any) => setHoveredNode(node?.id ?? null)}
        nodeLabel={(node: any) =>
          `${node.title} (${node.degree} connections)`
        }
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalParticles={linkParticles}
        linkDirectionalParticleWidth={linkParticleWidth}
        linkDirectionalParticleColor={linkColor}
        warmupTicks={100}
        cooldownTime={5000}
        showNavInfo={false}
        enableNavigationControls={true}
      />

      {/* Overlay layer — pointer-events-none so clicks pass through to 3D */}
      <div className="pointer-events-none absolute inset-0 z-10">
        <UniverseControls nodes={data.nodes} graphRef={fgRef} />
        <CardPreviewOverlay nodes={data.nodes} graphRef={fgRef} />
        <AIDiscoveryPanel nodes={data.nodes} />
        <CreateCardForm
          open={showCreateForm}
          onClose={() => setShowCreateForm(false)}
        />
      </div>

      {/* Accessibility: list view link */}
      <a
        href="/knowledge"
        className="pointer-events-auto absolute bottom-4 right-4 z-10 font-sans text-[10px] text-white/30 underline decoration-white/10 hover:text-white/50"
      >
        View as list
      </a>
    </div>
  );
}
