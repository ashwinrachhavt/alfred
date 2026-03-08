"use client";

import type { RefObject } from "react";

import { useEffect, useMemo } from "react";

import { useFrame, useThree } from "@react-three/fiber";
import { Vector3 } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

function damp(current: number, target: number, lambda: number, delta: number): number {
  const t = 1 - Math.exp(-lambda * delta);
  return current + (target - current) * t;
}

function dampVector3(current: Vector3, target: Vector3, lambda: number, delta: number): void {
  current.set(
    damp(current.x, target.x, lambda, delta),
    damp(current.y, target.y, lambda, delta),
    damp(current.z, target.z, lambda, delta),
  );
}

export function GalaxyCameraRig({
  controlsRef,
  focus,
}: {
  controlsRef: RefObject<OrbitControlsImpl | null>;
  focus: [number, number, number] | null;
}) {
  const { camera } = useThree();
  const target = useMemo(() => new Vector3(0, 0, 0), []);
  const desiredCameraPos = useMemo(() => new Vector3(0, 0, 3), []);

  useEffect(() => {
    if (!focus) return;

    target.set(focus[0], focus[1], focus[2]);

    const dir = camera.position.clone().sub(target);
    if (dir.lengthSq() < 1e-6) {
      dir.set(0.4, 0.25, 1);
    }
    dir.normalize();

    desiredCameraPos.copy(target).add(dir.multiplyScalar(1.8));
  }, [camera.position, focus, target, desiredCameraPos]);

  useFrame((_state, delta) => {
    if (!focus) return;
    const controls = controlsRef.current;
    if (!controls) return;

    dampVector3(controls.target, target, 12, delta);
    dampVector3(camera.position, desiredCameraPos, 8, delta);
    controls.update();
  });

  return null;
}
