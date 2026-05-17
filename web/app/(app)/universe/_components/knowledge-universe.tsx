"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d";
import * as THREE from "three";
import type {
  ExtendedGraphData,
  GraphNode,
  GraphEdge,
} from "@/features/universe/queries";

/**
 * Minimal shape of three.js OrbitControls (no types shipped with our install).
 * We only touch the properties used in this component.
 */
type OrbitControlsLike = {
  enableDamping: boolean;
  dampingFactor: number;
  rotateSpeed: number;
  zoomSpeed: number;
  panSpeed: number;
  autoRotate: boolean;
  autoRotateSpeed: number;
  minDistance: number;
  maxDistance: number;
  target: THREE.Vector3;
  update: () => void;
} | null | undefined;

function asOrbitControls(controls: unknown): OrbitControlsLike {
  return controls as OrbitControlsLike;
}
import { useUniverseStore } from "@/lib/stores/universe-store";
import { CardPreviewOverlay } from "./card-preview-overlay";
import { UniverseControls } from "./universe-controls";
import { AIDiscoveryPanel } from "./ai-discovery-panel";
import { CreateCardForm } from "./create-card-form";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const PARTICLE_COUNT = 600;
const PARTICLE_SPHERE_RADIUS = 500;
const NEBULA_SETTLE_MS = 1800;
const LARGE_GRAPH_THRESHOLD = 2000;
const HUGE_GRAPH_THRESHOLD = 5000;

/* ------------------------------------------------------------------ */
/*  Shared geometry cache — avoids per-node GPU allocations            */
/* ------------------------------------------------------------------ */
const geoCache = new Map<number, THREE.SphereGeometry>();
function getSharedGeometry(size: number): THREE.SphereGeometry {
  // Quantize to 0.5 increments to maximise sharing
  const key = Math.round(size * 2) / 2;
  let geo = geoCache.get(key);
  if (!geo) {
    geo = new THREE.SphereGeometry(key, 10, 8);
    geoCache.set(key, geo);
  }
  return geo;
}

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

/** Compute material properties for a node (pure function, no allocations). */
function computeNodeVisuals(gn: GraphNode, isSelected: boolean) {
  const urgency = dueUrgency(gn.due_at);
  const heatBoost = recencyBoost(gn.updated_at);
  const isStub = gn.status === "stub";

  let emissiveIntensity = isSelected ? 0.6 : 0.15;
  let emissiveColor = isSelected ? 0xe8590c : 0x331100;
  if (urgency === "overdue") {
    emissiveIntensity = 0.8;
    emissiveColor = 0xffaa33;
  } else if (urgency === "soon") {
    emissiveIntensity = 0.4;
    emissiveColor = 0xffaa33;
  }
  emissiveIntensity += heatBoost;

  return {
    color: isStub ? 0x555555 : 0xe8590c,
    wireframe: isStub,
    opacity: isSelected ? 1.0 : 0.75,
    emissiveColor,
    emissiveIntensity,
  };
}

type Props = { data: ExtendedGraphData };
type PositionedGraphNode = GraphNode & { x?: number; y?: number; z?: number };

export function KnowledgeUniverse({ data }: Props) {
  const fgRef = useRef<ForceGraphMethods<PositionedGraphNode, GraphEdge> | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Mesh cache: node id → THREE.Mesh (survives re-renders, only update materials)
  const meshCacheRef = useRef<Map<number, THREE.Mesh>>(new Map());

  // Navigation state refs (survive re-renders, no React overhead)
  const navKeysRef = useRef(new Set<string>());
  const navVelocityRef = useRef({ theta: 0, phi: 0, zoom: 0 });
  const cycleIndexRef = useRef(-1);
  const hoveredIdRef = useRef<number | null>(null);
  const flyToNodeRef = useRef<(node: PositionedGraphNode, distance?: number, duration?: number) => void>(() => {});
  const graphNodesRef = useRef<PositionedGraphNode[]>([]);

  /** Pause auto-rotate during interaction, resume after idle. */
  const autoRotateTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const pauseAutoRotate = useCallback(() => {
    const controls = asOrbitControls(fgRef.current?.controls());
    if (controls) controls.autoRotate = false;
    clearTimeout(autoRotateTimerRef.current);
    autoRotateTimerRef.current = setTimeout(() => {
      const c = asOrbitControls(fgRef.current?.controls());
      if (c) c.autoRotate = true;
    }, 8000); // Resume after 8s idle
  }, []);

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
  const effectiveTimeLapseDate = isTimeLapsePlaying ? timeLapseDate : null;

  /** Whether to skip heavy visual effects (particles / nebulae). */
  const isLargeGraph = data.nodes.length > LARGE_GRAPH_THRESHOLD;
  const isHugeGraph = data.nodes.length > HUGE_GRAPH_THRESHOLD;
  const nodeById = useMemo(
    () => new Map(data.nodes.map((node) => [node.id, node])),
    [data.nodes],
  );

  /* ---------------------------------------------------------------- */
  /*  Update cached mesh materials on selection change (no re-create)  */
  /* ---------------------------------------------------------------- */
  const selectedNodeIdsRef = useRef(selectedNodeIds);
  useEffect(() => {
    selectedNodeIdsRef.current = selectedNodeIds;
  }, [selectedNodeIds]);

  useEffect(() => {
    const cache = meshCacheRef.current;
    cache.forEach((mesh, nodeId) => {
      const mat = mesh.material as THREE.MeshPhongMaterial;
      const node = nodeById.get(nodeId);
      if (!node) return;
      const isSelected = selectedNodeIds.includes(nodeId);
      const vis = computeNodeVisuals(node, isSelected);
      mat.opacity = vis.opacity;
      mat.emissive.setHex(vis.emissiveColor);
      mat.emissiveIntensity = vis.emissiveIntensity;
    });
  }, [selectedNodeIds, nodeById]);

  /* ---------------------------------------------------------------- */
  /*  Audio refs                                                       */
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

  // Measure container with debounced ResizeObserver + pause auto-rotate on interact
  useEffect(() => {
    if (!containerRef.current) return;
    let rafId = 0;
    const ro = new ResizeObserver(([entry]) => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      });
    });
    ro.observe(containerRef.current);

    // Pause auto-rotate on any manual orbit/pan/zoom
    const el = containerRef.current;
    const onInteract = () => pauseAutoRotate();
    el.addEventListener("mousedown", onInteract);
    el.addEventListener("wheel", onInteract);
    el.addEventListener("touchstart", onInteract);

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      el.removeEventListener("mousedown", onInteract);
      el.removeEventListener("wheel", onInteract);
      el.removeEventListener("touchstart", onInteract);
    };
  }, [pauseAutoRotate]);

  // Configure force simulation after mount
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;
    fg.d3Force("charge")?.strength(-120);
    fg.d3Force("link")?.distance(50);
  }, [data]);

  // Controls + lighting — run once after first mount
  useEffect(() => {
    if (!fgRef.current) return;
    const fg = fgRef.current;

    // Smooth orbit controls — low damping for long, momentum-like glide
    const controls = asOrbitControls(fg.controls());
    if (controls) {
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.rotateSpeed = 0.5;
      controls.zoomSpeed = 1.2;
      controls.panSpeed = 0.4;
      // Subtle auto-rotate so the universe feels alive when idle
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.3;
      controls.minDistance = 20;
      controls.maxDistance = 600;
    }

    // Scene setup — force opaque dark background.
    // three-forcegraph has a bug: parseFloat("ff", 16) returns NaN, making
    // the WebGL clear alpha 0 (transparent).  The library re-applies this
    // broken setClearColor on every frame, so one-time fixes get overridden.
    // Nuclear fix: CSS background on the <canvas> element itself.  WebGL
    // transparent pixels composite over this CSS background — un-overridable.
    const renderer = fg.renderer();
    renderer.domElement.style.background = "#0F0E0D";
    renderer.setClearColor(0x0f0e0d, 1);
    const scene = fg.scene();
    scene.background = new THREE.Color(0x0f0e0d);

    // Remove default lights
    const existingLights = scene.children.filter(
      (c: THREE.Object3D) => c instanceof THREE.Light,
    );
    existingLights.forEach((l: THREE.Object3D) => scene.remove(l));

    // Hemisphere light — warm from above (like distant starlight), cool from below
    const hemi = new THREE.HemisphereLight(0x1a1510, 0x080810, 0.4);
    scene.add(hemi);

    // Key light — neutral, gentle directional from upper-right
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.35);
    keyLight.position.set(150, 250, 200);
    scene.add(keyLight);

    // Subtle accent — dim orange point light to catch sphere edges
    const accentLight = new THREE.PointLight(0xe8590c, 0.15, 500);
    accentLight.position.set(-100, -150, -200);
    scene.add(accentLight);
  }, []);

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
    const fg = fgRef.current;
    if (!fg || isLargeGraph || !data.clusters.length) return;

    let sprites: THREE.Sprite[] = [];
    let cancelled = false;

    const timeout = setTimeout(() => {
      if (cancelled) return;
      const scene = fg.scene();
      const fgNodes = graphNodesRef.current;

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
    }, NEBULA_SETTLE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timeout);
      const scene = fg.scene();
      sprites.forEach((s) => {
        scene.remove(s);
        (s.material as THREE.SpriteMaterial).map?.dispose();
        s.material.dispose();
      });
      sprites = [];
    };
  }, [data.clusters, data.edges, data.nodes, isLargeGraph, effectiveTimeLapseDate]);

  /* ---------------------------------------------------------------- */
  /*  Keyboard shortcuts (non-navigation)                              */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Cmd/Ctrl+K focuses search from anywhere
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        const searchInput = containerRef.current?.querySelector<HTMLInputElement>(
          'input[placeholder*="Search"]',
        );
        searchInput?.focus();
        return;
      }

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

      if (e.key === " ") {
        e.preventDefault();
        setTimeLapsePlaying(!isTimeLapsePlaying);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection, showCreateForm, isTimeLapsePlaying, setTimeLapsePlaying]);

  /* ---------------------------------------------------------------- */
  /*  Smooth keyboard navigation — orbit, zoom, node cycling           */
  /*                                                                    */
  /*  Uses a requestAnimationFrame loop with velocity + friction for    */
  /*  silky momentum.  Arrow keys orbit the camera in spherical coords, */
  /*  +/- zoom along the camera axis, [ ] cycle through nodes,          */
  /*  Home resets the view via zoom-to-fit.                              */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    const NAV_KEYS = new Set([
      "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown",
      "+", "=", "-", "_",
      "[", "]", "Home",
    ]);
    const ACCEL = 0.0012;
    const MAX_SPEED = 0.035;
    const FRICTION = 0.91;
    const ZOOM_ACCEL = 0.8;
    const ZOOM_MAX = 4;
    const ZOOM_FRICTION = 0.88;

    const keys = navKeysRef.current;
    const vel = navVelocityRef.current;
    let rafId = 0;
    let hasActiveMotion = false;

    function onKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (!NAV_KEYS.has(e.key)) return;

      e.preventDefault();
      keys.add(e.key);

      // One-shot actions: node cycling and view reset
      if (e.key === "]" || e.key === "[") {
        const nodes = graphNodesRef.current;
        if (nodes.length === 0) return;
        const dir = e.key === "]" ? 1 : -1;
        cycleIndexRef.current = ((cycleIndexRef.current + dir) % nodes.length + nodes.length) % nodes.length;
        const node = nodes[cycleIndexRef.current];
        clearSelection();
        selectNode(node.id);
        flyToNodeRef.current(node, 80, 500);
        keys.delete(e.key);
      }

      if (e.key === "Home") {
        fgRef.current?.zoomToFit(600, 50);
        vel.theta = 0;
        vel.phi = 0;
        vel.zoom = 0;
        keys.delete("Home");
      }
    }

    function onKeyUp(e: KeyboardEvent) {
      keys.delete(e.key);
    }

    function tick() {
      const fg = fgRef.current;
      const controls = asOrbitControls(fg?.controls());

      if (fg && controls?.target) {
        // Accumulate velocity from held keys
        if (keys.has("ArrowLeft"))  vel.theta += ACCEL;
        if (keys.has("ArrowRight")) vel.theta -= ACCEL;
        if (keys.has("ArrowUp"))    vel.phi -= ACCEL;
        if (keys.has("ArrowDown"))  vel.phi += ACCEL;
        if (keys.has("+") || keys.has("=")) vel.zoom += ZOOM_ACCEL;
        if (keys.has("-") || keys.has("_")) vel.zoom -= ZOOM_ACCEL;

        // Clamp
        vel.theta = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, vel.theta));
        vel.phi   = Math.max(-MAX_SPEED, Math.min(MAX_SPEED, vel.phi));
        vel.zoom  = Math.max(-ZOOM_MAX, Math.min(ZOOM_MAX, vel.zoom));

        const moving = Math.abs(vel.theta) > 0.00005
                    || Math.abs(vel.phi) > 0.00005
                    || Math.abs(vel.zoom) > 0.01;

        if (moving) {
          // Pause auto-rotate during keyboard nav
          if (!hasActiveMotion) {
            hasActiveMotion = true;
            if (controls) controls.autoRotate = false;
            clearTimeout(autoRotateTimerRef.current);
          }

          // Orbit: modify camera in spherical coordinates around target
          const camera = fg.camera();
          const target = controls.target as THREE.Vector3;
          const offset = new THREE.Vector3().subVectors(camera.position, target);
          const spherical = new THREE.Spherical().setFromVector3(offset);

          spherical.theta += vel.theta;
          spherical.phi = THREE.MathUtils.clamp(
            spherical.phi + vel.phi, 0.15, Math.PI - 0.15,
          );

          // Zoom: change radius
          if (Math.abs(vel.zoom) > 0.01) {
            const minDist = controls.minDistance || 20;
            const maxDist = controls.maxDistance || 600;
            spherical.radius = THREE.MathUtils.clamp(
              spherical.radius - vel.zoom, minDist, maxDist,
            );
          }

          offset.setFromSpherical(spherical);
          camera.position.copy(target).add(offset);
          camera.lookAt(target);
        }

        // Friction — decay velocity when keys aren't held
        if (!keys.has("ArrowLeft") && !keys.has("ArrowRight")) vel.theta *= FRICTION;
        if (!keys.has("ArrowUp") && !keys.has("ArrowDown"))    vel.phi *= FRICTION;
        if (!keys.has("+") && !keys.has("=") && !keys.has("-") && !keys.has("_")) vel.zoom *= ZOOM_FRICTION;

        // Resume auto-rotate after motion fully decays
        if (hasActiveMotion && !moving) {
          hasActiveMotion = false;
          autoRotateTimerRef.current = setTimeout(() => {
            const c = asOrbitControls(fgRef.current?.controls());
            if (c) c.autoRotate = true;
          }, 5000);
        }
      }

      rafId = requestAnimationFrame(tick);
    }

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    rafId = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      cancelAnimationFrame(rafId);
    };
  }, [clearSelection, selectNode, pauseAutoRotate]);

  /* ---------------------------------------------------------------- */
  /*  Zoom-to-fit on initial load (after simulation settles)           */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!fgRef.current) return;
    const timer = setTimeout(() => {
      fgRef.current?.zoomToFit(800, 60);
    }, 3500);
    return () => clearTimeout(timer);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Time-Lapse Mode                                                  */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    if (!isTimeLapsePlaying) return;

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

    const initialTimer = window.setTimeout(() => setTimeLapseDate(new Date(current)), 0);

    const interval = setInterval(() => {
      current += ONE_DAY;
      if (current > endTime) {
        setTimeLapsePlaying(false);
        clearInterval(interval);
        return;
      }
      setTimeLapseDate(new Date(current));
    }, 200);

    return () => {
      window.clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [isTimeLapsePlaying, data.nodes, setTimeLapsePlaying]);

  /* ---------------------------------------------------------------- */
  /*  Node rendering — cached meshes, shared geometry                  */
  /* ---------------------------------------------------------------- */
  const nodeThreeObject = useCallback(
    (node: GraphNode) => {
      const gn = node as GraphNode & { x?: number; y?: number; z?: number };
      const cache = meshCacheRef.current;

      // Return cached mesh if it exists (material already updated by selection effect)
      const cached = cache.get(gn.id);
      if (cached) return cached;

      const size = Math.max(2, Math.log2((gn.degree || 0) + 1) * 2.5);
      const isSelected = selectedNodeIdsRef.current.includes(gn.id);
      const vis = computeNodeVisuals(gn, isSelected);

      const geometry = getSharedGeometry(size);
      const material = new THREE.MeshPhongMaterial({
        color: vis.color,
        wireframe: vis.wireframe,
        transparent: true,
        opacity: vis.opacity,
        emissive: vis.emissiveColor,
        emissiveIntensity: vis.emissiveIntensity,
      });
      const mesh = new THREE.Mesh(geometry, material);
      cache.set(gn.id, mesh);
      return mesh;
    },
    // No dependency on selectedNodeIds — selection updates via the effect above
    [],
  );

  /* ---------------------------------------------------------------- */
  /*  Wormhole edge styling                                            */
  /* ---------------------------------------------------------------- */
  const linkColor = useCallback((link: GraphEdge) => {
    if (link.type === "auto_high") return "#FFAA33";
    if (link.type === "ai-suggested") return "#E8590C";
    return "#ffffff20";
  }, []);

  const linkWidth = useCallback((link: GraphEdge) => {
    if (link.type === "auto_high") return 2;
    if (link.type === "ai-suggested") return 1.5;
    return 0.4;
  }, []);

  const linkParticles = useCallback((link: GraphEdge) => {
    if (link.type === "auto_high") return 4;
    if (link.type === "ai-suggested") return 3;
    return 0;
  }, []);

  const linkParticleWidth = useCallback((link: GraphEdge) => {
    if (link.type === "auto_high") return 2;
    if (link.type === "ai-suggested") return 1.5;
    return 0;
  }, []);

  const effectiveLinkParticles = useCallback(
    (link: GraphEdge) => (isLargeGraph ? 0 : linkParticles(link)),
    [isLargeGraph, linkParticles],
  );

  const effectiveLinkParticleWidth = useCallback(
    (link: GraphEdge) => (isLargeGraph ? 0 : linkParticleWidth(link)),
    [isLargeGraph, linkParticleWidth],
  );

  /* ---------------------------------------------------------------- */
  /*  Hover glow — brighten + scale on hover for instant feedback      */
  /* ---------------------------------------------------------------- */
  const handleNodeHover = useCallback(
    (node: GraphNode | null) => {
      const newId = node?.id ?? null;
      const prevId = hoveredIdRef.current;
      if (newId === prevId) return;

      const cache = meshCacheRef.current;

      // Restore previous hovered node
      if (prevId !== null) {
        const prevMesh = cache.get(prevId);
        if (prevMesh) {
          const mat = prevMesh.material as THREE.MeshPhongMaterial;
          const prevNode = nodeById.get(prevId);
          if (prevNode) {
            const isSelected = selectedNodeIdsRef.current.includes(prevId);
            const vis = computeNodeVisuals(prevNode, isSelected);
            mat.emissiveIntensity = vis.emissiveIntensity;
            mat.opacity = vis.opacity;
          }
          prevMesh.scale.setScalar(1.0);
        }
      }

      // Highlight new hovered node
      if (newId !== null) {
        const mesh = cache.get(newId);
        if (mesh) {
          const mat = mesh.material as THREE.MeshPhongMaterial;
          mat.emissiveIntensity = 0.6;
          mat.opacity = 1.0;
          mesh.scale.setScalar(1.2);
        }
      }

      hoveredIdRef.current = newId;
      setHoveredNode(newId);
    },
    [nodeById, setHoveredNode],
  );

  /** Smooth fly-to a positioned node. */
  const flyToNode = useCallback(
    (node: PositionedGraphNode, distance = 80, duration = 600) => {
      if (
        !fgRef.current ||
        node.x === undefined ||
        node.y === undefined ||
        node.z === undefined
      )
        return;
      pauseAutoRotate();
      // Kill any keyboard nav momentum so fly-to isn't fighting the orbit
      navVelocityRef.current.theta = 0;
      navVelocityRef.current.phi = 0;
      navVelocityRef.current.zoom = 0;
      // Offset camera from the node along the current camera direction
      const cam = fgRef.current.camera();
      const dir = new THREE.Vector3()
        .subVectors(cam.position, new THREE.Vector3(node.x, node.y, node.z))
        .normalize();
      fgRef.current.cameraPosition(
        {
          x: node.x + dir.x * distance,
          y: node.y + dir.y * distance,
          z: node.z + dir.z * distance,
        },
        { x: node.x, y: node.y, z: node.z },
        duration,
      );
    },
    [pauseAutoRotate],
  );
  // Keep ref in sync so navigation loop can call flyToNode without a dep cycle.
  useEffect(() => {
    flyToNodeRef.current = flyToNode;
  }, [flyToNode]);

  // Double-click detection via timing
  const lastClickRef = useRef<{ id: number; time: number }>({ id: -1, time: 0 });

  // Click handler — select + fly-to; double-click for close-up
  const handleNodeClick = useCallback(
    (node: GraphNode, event: MouseEvent) => {
      playClickSound();
      const now = Date.now();
      const last = lastClickRef.current;
      const isDoubleClick = node.id === last.id && now - last.time < 350;
      lastClickRef.current = { id: node.id, time: now };

      if (event.shiftKey) {
        selectNode(node.id);
        return;
      }

      clearSelection();
      selectNode(node.id);

      const distance = isDoubleClick ? 35 : 80;
      const duration = isDoubleClick ? 400 : 600;
      flyToNode(node as PositionedGraphNode, distance, duration);
    },
    [selectNode, clearSelection, playClickSound, flyToNode],
  );

  /* ---------------------------------------------------------------- */
  /*  Graph data — apply time-lapse filter if active                   */
  /* ---------------------------------------------------------------- */
  const graphData = useMemo(() => {
    let filteredNodes = data.nodes;

    // Time-lapse: only show nodes created before the playback date
    if (effectiveTimeLapseDate) {
      const cutoff = effectiveTimeLapseDate.getTime();
      filteredNodes = data.nodes.filter((n) => {
        if (!n.created_at) return true; // show nodes without dates
        return new Date(n.created_at).getTime() <= cutoff;
      });
    }

    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    // force-graph hydrates source/target into node objects after first render;
    // accept either a raw id or a resolved node and read .id off it.
    const endpointId = (ref: number | { id: number }): number =>
      typeof ref === "number" ? ref : ref.id;
    const filteredEdges = data.edges.filter(
      (e) => nodeIds.has(endpointId(e.source)) && nodeIds.has(endpointId(e.target)),
    );

    return {
      nodes: filteredNodes.map((n) => ({ ...n })),
      links: filteredEdges.map((e) => ({ ...e })),
    };
  }, [data, effectiveTimeLapseDate]);

  const graphNodeIds = useMemo(
    () => new Set(graphData.nodes.map((node) => node.id)),
    [graphData.nodes],
  );

  useEffect(() => {
    const cache = meshCacheRef.current;
    for (const id of cache.keys()) {
      if (!graphNodeIds.has(id)) {
        const mesh = cache.get(id);
        if (mesh) {
          (mesh.material as THREE.Material).dispose();
          cache.delete(id);
        }
      }
    }
  }, [graphNodeIds]);

  useEffect(() => {
    graphNodesRef.current = graphData.nodes as PositionedGraphNode[];
  }, [graphData.nodes]);

  /* ---------------------------------------------------------------- */
  /*  Huge graph bail-out                                              */
  /* ---------------------------------------------------------------- */
  if (isHugeGraph) {
    return (
      <div className="scene-container flex h-full flex-col items-center justify-center gap-4 bg-[var(--alfred-scene-bg)]">
        <p className="font-sans text-sm text-white/60">
          Too many cards ({data.nodes.length}) for the 3D view.
        </p>
        <Link
          href="/knowledge"
          className="rounded-md bg-primary px-4 py-2 font-sans text-sm text-primary-foreground"
        >
          View in Knowledge Hub
        </Link>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="scene-container relative h-full w-full overflow-hidden">
      {/* Large graph warning banner */}
      {isLargeGraph && (
        <div className="absolute left-1/2 top-4 z-20 -translate-x-1/2 rounded-full border border-white/10 bg-black/60 px-4 py-1.5 backdrop-blur-sm">
          <span className="font-mono text-sm text-white/50">
            Large graph — some visual effects reduced
          </span>
        </div>
      )}

      {/* Time-lapse date display */}
      {effectiveTimeLapseDate && (
        <div className="absolute left-1/2 top-14 z-20 -translate-x-1/2 rounded-full border border-primary/30 bg-black/60 px-4 py-1.5 backdrop-blur-sm">
          <span className="font-mono text-sm text-primary">
            {effectiveTimeLapseDate.toLocaleDateString("en-US", {
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
        controlType="orbit"
        nodeThreeObject={nodeThreeObject}
        nodeThreeObjectExtend={false}
        onNodeClick={handleNodeClick}
        onNodeHover={handleNodeHover}
        onBackgroundClick={clearSelection}
        nodeLabel={(node: GraphNode) =>
          `${node.title} (${node.degree} connections)`
        }
        linkColor={linkColor}
        linkWidth={linkWidth}
        linkDirectionalParticles={effectiveLinkParticles}
        linkDirectionalParticleWidth={effectiveLinkParticleWidth}
        linkDirectionalParticleColor={linkColor}
        warmupTicks={isLargeGraph ? 6 : 14}
        cooldownTime={isLargeGraph ? 900 : 1600}
        showNavInfo={false}
        enableNavigationControls={true}
      />

      {/* Overlay layer — pointer-events-none so clicks pass through to 3D */}
      <div className="pointer-events-none absolute inset-0 z-10">
        <UniverseControls nodes={graphData.nodes as PositionedGraphNode[]} flyToNode={flyToNode} />
        <AIDiscoveryPanel nodes={data.nodes} />
        <CreateCardForm
          open={showCreateForm}
          onClose={() => setShowCreateForm(false)}
        />
      </div>

      {/* Card modal — outside the pointer-events-none wrapper so fixed positioning works */}
      <CardPreviewOverlay nodes={graphData.nodes} />

      {/* Accessibility: list view link */}
      <Link
        href="/knowledge"
        className="pointer-events-auto absolute bottom-4 right-4 z-10 font-sans text-sm text-white/30 underline decoration-white/10 hover:text-white/50"
      >
        View as list
      </Link>
    </div>
  );
}
