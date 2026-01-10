"use client";

import { useEffect, useMemo, useRef } from "react";

import type { ThreeEvent } from "@react-three/fiber";
import { Color, type InstancedMesh, Object3D } from "three";

import type { SemanticMapPoint } from "@/lib/api/types/documents";

export function GalaxyStarField({
  points,
  focusedId,
  onFocus,
  onHover,
}: {
  points: SemanticMapPoint[];
  focusedId: string | null;
  onFocus: (point: SemanticMapPoint) => void;
  onHover: (point: SemanticMapPoint | null) => void;
}) {
  const meshRef = useRef<InstancedMesh | null>(null);
  const hoveredIndexRef = useRef<number | null>(null);
  const focusedIndex = useMemo(
    () => points.findIndex((p) => p.id === focusedId),
    [focusedId, points],
  );

  useEffect(() => {
    const mesh = meshRef.current;
    if (!mesh || points.length === 0) return;

    const dummy = new Object3D();
    const color = new Color();

    for (let i = 0; i < points.length; i += 1) {
      const p = points[i];
      dummy.position.set(p.pos[0], p.pos[1], p.pos[2]);
      const scale = i === focusedIndex ? 1.9 : 1.0;
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      color.set(p.color);
      mesh.setColorAt(i, color);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [focusedIndex, points]);

  useEffect(() => {
    return () => {
      document.body.style.cursor = "default";
    };
  }, []);

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, points.length]}
      frustumCulled={false}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        if (typeof event.instanceId !== "number") return;
        const idx = event.instanceId;
        const p = points[idx];
        if (!p) return;
        onFocus(p);
      }}
      onPointerMove={(event: ThreeEvent<PointerEvent>) => {
        if (typeof event.instanceId !== "number") return;
        const idx = event.instanceId;
        if (hoveredIndexRef.current === idx) return;
        hoveredIndexRef.current = idx;
        onHover(points[idx] ?? null);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        hoveredIndexRef.current = null;
        onHover(null);
        document.body.style.cursor = "default";
      }}
    >
      <octahedronGeometry args={[0.02, 0]} />
      <meshBasicMaterial vertexColors transparent opacity={0.92} depthWrite={false} />
    </instancedMesh>
  );
}
